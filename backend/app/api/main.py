import csv
import io
import logging
import secrets
from contextlib import asynccontextmanager
from typing import Annotated, Literal

from app.assistant.service import Assistant
from app.classification.evaluations import list_evaluations
from app.classification.predictor import Predictor
from app.config import settings
from app.domain.models import (
    PRIORITIES,
    Batch,
    IncidentUpdate,
    KnowledgeInput,
    Question,
    RawLog,
)
from app.ingestion.formats import csv_message
from app.ingestion.queue import Queue
from app.preprocessing.parser import normalize
from app.storage.repository import Repository
from fastapi import (
    Depends,
    FastAPI,
    File,
    Form,
    Header,
    HTTPException,
    Query,
    Request,
    UploadFile,
)
from fastapi.responses import JSONResponse
from pydantic import ValidationError


def authorize(x_api_key: str = Header(default="")):
    if settings.api_key and not secrets.compare_digest(x_api_key, settings.api_key):
        raise HTTPException(401, "A valid LogSense API key is required")


@asynccontextmanager
async def lifespan(app):
    repo = Repository(settings)
    try:
        repo.initialize()
        queue = Queue(settings.redis_uri)
        queue.initialize()
        app.state.repo = repo
        app.state.queue = queue
        app.state.predictor = Predictor(settings.model_path, settings.review_threshold)
        app.state.assistant = Assistant(repo, settings)
        yield
    finally:
        repo.close()


app = FastAPI(
    title="LogSense",
    version="0.1.0",
    lifespan=lifespan,
    dependencies=[Depends(authorize)],
)


@app.exception_handler(Exception)
async def unavailable(request, exc):
    logging.getLogger(__name__).exception("Request failed")
    return JSONResponse(
        status_code=503,
        content={
            "detail": "A required service is unavailable. Check the service status and retry."
        },
    )


@app.get("/api/health")
def health(request: Request):
    services = request.app.state.repo.health()
    request.app.state.queue.redis.ping()
    return {
        "status": "healthy",
        "services": services | {"Redis": "healthy"},
        "queue": request.app.state.queue.stats(),
    }


@app.get("/api/overview")
def overview(request: Request):
    return request.app.state.repo.stats() | {
        "queue": request.app.state.queue.stats(),
        "model": request.app.state.predictor.metadata,
    }


def enqueue(request, logs):
    # Validate every input before publishing any item in a request.
    try:
        events = [normalize(raw) for raw in logs]
    except ValueError as exc:
        raise HTTPException(422, str(exc)) from exc
    receipts = [
        {
            "id": event.id,
            "accepted": request.app.state.queue.publish(event),
            "warnings": event.warnings,
        }
        for event in events
    ]
    return {
        "accepted": sum(r["accepted"] for r in receipts),
        "duplicates": sum(not r["accepted"] for r in receipts),
        "receipts": receipts,
    }


@app.post("/api/ingest", status_code=202)
def ingest(batch: Batch, request: Request):
    return enqueue(request, batch.logs)


@app.post("/api/ingest/file", status_code=202)
async def ingest_file(
    request: Request,
    file: Annotated[UploadFile, File()],
    source: str = Form("file"),
    service: str = Form("unknown"),
    dataset: str = Form(""),
):
    data = await file.read(2_000_001)
    if len(data) > 2_000_000:
        raise HTTPException(
            413, "Files must be at most 2 MB; use the batch collector for larger files"
        )
    try:
        text = data.decode("utf-8-sig")
    except UnicodeDecodeError:
        raise HTTPException(422, "Upload a UTF-8 text, JSONL or CSV file")
    try:
        if (file.filename or "").lower().endswith(".csv"):
            records = list(csv.DictReader(io.StringIO(text)))
            logs = [
                RawLog(message=csv_message(r), source=source, service=service, dataset=dataset)
                for r in records
            ]
        else:
            logs = [
                RawLog(message=line, source=source, service=service, dataset=dataset)
                for line in text.splitlines()
                if line.strip()
            ]
        batch = Batch(logs=logs)
    except (ValidationError, ValueError):
        raise HTTPException(
            422,
            "Provide 1–1000 nonempty logs, each at most 16000 characters; CSV requires a Content or message column",
        )
    return enqueue(request, batch.logs)


@app.get("/api/ingest/{event_id}")
def receipt(event_id: str, request: Request):
    status = request.app.state.queue.status(event_id)
    if not status:
        raise HTTPException(404, "Receipt not found or expired")
    return status


@app.get("/api/events")
def events(
    request: Request,
    priority: str | None = None,
    q: str = Query("", max_length=200),
    limit: int = Query(100, ge=1, le=500),
):
    if priority and priority not in PRIORITIES:
        raise HTTPException(422, "Priority must be P1–P5")
    return request.app.state.repo.events(priority, q, limit)


@app.get("/api/explorer")
def explore(
    request: Request,
    priority: str | None = None,
    q: str = Query("", max_length=200),
    source: str | None = Query(None, max_length=200),
    dataset: str | None = Query(None, max_length=100),
    limit: int = Query(100, ge=1, le=1000),
    sort_by: Literal["received_at", "timestamp", "priority"] = "received_at",
    order: Literal["asc", "desc"] = "desc",
):
    if priority and priority not in PRIORITIES:
        raise HTTPException(422, "Priority must be P1–P5")
    return request.app.state.repo.explore(priority, q, limit, source, dataset, sort_by, order)


@app.get("/api/events/facets")
def event_facets(request: Request):
    return request.app.state.repo.event_facets()


@app.get("/api/evaluations")
def evaluations():
    return {"runs": list_evaluations(settings.evaluations_dir)}


@app.get("/api/events/{event_id}")
def event(event_id: str, request: Request):
    row = request.app.state.repo.event(event_id)
    if not row:
        raise HTTPException(404, "Event not found")
    return row


@app.get("/api/models")
def models(request: Request):
    return request.app.state.predictor.metadata


@app.get("/api/knowledge")
def knowledge(request: Request):
    return request.app.state.repo.knowledge()


@app.post("/api/knowledge", status_code=201)
def add_knowledge(body: KnowledgeInput, request: Request):
    asset_id = request.app.state.repo.add_knowledge(**body.model_dump())
    return {"id": asset_id}


@app.post("/api/assistant")
def assistant(body: Question, request: Request):
    try:
        return request.app.state.assistant.answer(body.question, body.event_id)
    except KeyError:
        raise HTTPException(404, "Event not found")


@app.get("/api/incidents")
def incidents(request: Request):
    return request.app.state.repo.incidents()


@app.get("/api/incidents/{event_id}")
def incident(event_id: str, request: Request):
    row = request.app.state.repo.incident(event_id)
    if not row:
        raise HTTPException(404, "Incident not found")
    return row


@app.patch("/api/incidents/{event_id}")
def update_incident(event_id: str, body: IncidentUpdate, request: Request):
    try:
        return request.app.state.repo.update_incident(event_id, body)
    except KeyError:
        raise HTTPException(404, "Incident not found")
    except ValueError as exc:
        raise HTTPException(409, str(exc))


@app.get("/api/knowledge/search")
def search_knowledge(
    request: Request,
    q: str = Query("", max_length=200),
    category: Literal["references", "patterns", "resolutions", "all"] = "references",
    offset: int = Query(0, ge=0),
    limit: int = Query(24, ge=1, le=100),
):
    return request.app.state.repo.search_knowledge(q, category, offset, limit)


@app.post("/api/knowledge/pdf", status_code=201)
def upload_reference(
    request: Request,
    file: Annotated[UploadFile, File()],
    title: str = Form("", max_length=200),
    kind: Literal["runbook", "troubleshooting", "root_cause"] = Form("runbook"),
):
    from app.knowledge.pdf import extract_reference

    data = file.file.read(10_000_001)
    try:
        extracted = extract_reference(data, file.filename or "reference.pdf", title, kind)
    except ValueError as exc:
        raise HTTPException(422, str(exc)) from exc
    return request.app.state.repo.add_pdf_reference(extracted)


@app.get("/api/storage")
def storage_findings(request: Request):
    import json
    from pathlib import Path

    result = request.app.state.repo.storage_findings()
    path = Path("/benchmarks/latest.json")
    result["benchmark"] = json.loads(path.read_text()) if path.exists() else None
    return result
