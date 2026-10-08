"""Run inside the isolated Compose API container: LOGSENSE_TEST_LIVE=1 pytest."""

import os
import time
from uuid import uuid4

import pytest
from app.api.main import app
from app.classification.predictor import Predictor
from app.config import settings
from app.domain.models import Event, Prediction, RawLog
from app.preprocessing.parser import normalize
from fastapi.testclient import TestClient

pytestmark = pytest.mark.skipif(
    os.getenv("LOGSENSE_TEST_LIVE") != "1", reason="Requires LogSense Docker services"
)


def test_full_pipeline_and_incident_feedback():
    source = "integration-" + uuid4().hex
    headers = {"X-API-Key": settings.api_key}
    with TestClient(app, headers=headers) as client:
        batch = {
            "logs": [
                {
                    "message": f"{level} quartz database connection refused",
                    "source": source,
                    "service": "quartz-db",
                    "timestamp": "2026-09-30T12:00:00Z",
                }
                for level in ["DEBUG", "INFO", "WARN", "ERROR", "CRITICAL"]
            ]
        }
        first = client.post("/api/ingest", json=batch)
        assert first.status_code == 202, first.text
        ids = [r["id"] for r in first.json()["receipts"]]
        assert client.post("/api/ingest", json=batch).json()["duplicates"] == 5
        for _ in range(40):
            statuses = [client.get("/api/ingest/" + i).json() for i in ids]
            if all(s == {"classification": "done", "knowledge": "done"} for s in statuses):
                break
            time.sleep(0.5)
        else:
            pytest.fail(str(statuses))
        predictor = Predictor(settings.model_path)
        for i, event_id in enumerate(ids):
            event = client.get("/api/events/" + event_id).json()
            expected = predictor.predict(normalize(RawLog(**batch["logs"][i])))
            assert event["prediction"]["priority"] == expected.priority
            low = expected.priority in ("P1", "P2", "P3")
            assert event["storage"] == ("MongoDB" if low else "PostgreSQL")
            with app.state.repo.pool.connection() as conn:
                count = conn.execute(
                    "SELECT count(*) AS n FROM events WHERE id=%s", (event_id,)
                ).fetchone()["n"]
            assert app.state.repo.logs.count_documents({"_id": event_id}) == (1 if low else 0)
            assert count == (0 if low else 1)
        # Reprocessing after a model change must preserve the original route.
        event = client.get("/api/events/" + ids[0]).json()
        original_storage = event["storage"]
        app.state.repo.save_event(
            Event.model_validate(event), Prediction(priority="P5", mode="test")
        )
        assert app.state.repo.event(ids[0])["storage"] == original_storage
        # Independent knowledge worker is idempotent too.
        app.state.repo.observe(Event.model_validate(event))
        with app.state.repo.pool.connection() as conn:
            assert (
                conn.execute(
                    "SELECT count(*) AS n FROM knowledge_observations WHERE event_id=%s",
                    (ids[0],),
                ).fetchone()["n"]
                == 1
            )
        fixture = normalize(
            RawLog(
                message="quartz database connection pool exhausted",
                source=source,
                service="quartz-db",
            )
        )
        app.state.repo.save_event(fixture, Prediction(priority="P4", mode="test_fixture"))
        event_id = fixture.id
        assert (
            client.patch(
                "/api/incidents/" + event_id,
                json={
                    "status": "resolved",
                    "actor": "Test engineer",
                    "note": "Done",
                    "root_cause": "Pool limit",
                    "resolution": "Increased pool",
                },
            ).status_code
            == 409
        )
        assert (
            client.patch(
                "/api/incidents/" + event_id,
                json={
                    "status": "investigating",
                    "actor": "Test engineer",
                    "note": "Inspecting connection pool",
                },
            ).status_code
            == 200
        )
        assert (
            client.patch(
                "/api/incidents/" + event_id,
                json={"status": "resolved", "actor": "Test engineer", "note": "Done"},
            ).status_code
            == 409
        )
        assert (
            client.patch(
                "/api/incidents/" + event_id,
                json={
                    "status": "resolved",
                    "actor": "Test engineer",
                    "note": "Verified recovery",
                    "root_cause": "Quartz database connection pool exhausted",
                    "resolution": "Increased pool limit after checking database capacity",
                },
            ).status_code
            == 200
        )
        response = client.post(
            "/api/assistant",
            json={
                "question": "quartz database connection pool exhausted",
                "event_id": event_id,
            },
        )
        assert response.status_code == 200
        assert any(
            s["verified"] and s["source"] == "incident:" + event_id
            for s in response.json()["sources"]
        )
        assert len(client.get("/api/incidents/" + event_id).json()["history"]) == 2
        # Invalid files, malformed requests, missing IDs are explicit client errors.
        assert client.post("/api/ingest", json={"logs": []}).status_code == 422
        assert client.get("/api/events?priority=P9").status_code == 422
        assert client.get("/api/events/missing").status_code == 404
        assert (
            client.post("/api/ingest/file", files={"file": ("bad.txt", b"\xff")}).status_code == 422
        )


def test_stream_recovery_and_independent_acknowledgements(monkeypatch):
    from app.domain.models import RawLog
    from app.ingestion import queue as module
    from app.preprocessing.parser import normalize

    stream = "logsense:test:" + uuid4().hex
    monkeypatch.setattr(module, "STREAM", stream)
    queue = module.Queue(settings.redis_uri)
    queue.initialize()
    event = normalize(RawLog(message="INFO test recovery", source=stream))
    try:
        assert queue.publish(event)
        assert not queue.publish(event)
        first = queue.next("classification", "crashed-worker")
        assert len(first) == 1
        entry_id = first[0][0]
        queue.redis.xclaim(stream, "classification", "crashed-worker", 0, [entry_id], idle=61000)
        recovered = queue.next("classification", "replacement-worker")
        assert recovered[0][0] == entry_id
        queue.finish("classification", entry_id, event.id)
        assert queue.redis.xlen(stream) == 1
        assert queue.status(event.id)["knowledge"] == "queued"
        second = queue.next("knowledge", "knowledge-worker")
        assert second[0][0] == entry_id
        queue.finish("knowledge", entry_id, event.id)
        assert queue.redis.xlen(stream) == 0
        assert queue.status(event.id) == {"classification": "done", "knowledge": "done"}
    finally:
        queue.redis.delete(stream, "logsense:status:" + event.id)


def test_explorer_filters_both_stores_before_limit():
    source = "integration-" + uuid4().hex
    with TestClient(app, headers={"X-API-Key": settings.api_key}) as client:
        for i, priority in enumerate(["P1", "P2", "P3", "P4", "P5"]):
            event = normalize(
                RawLog(
                    message=f"filter record {i}",
                    source=source,
                    service="quartz-db",
                    dataset="filter-fixture",
                    timestamp=f"2026-10-01T00:00:0{i}Z",
                )
            )
            app.state.repo.save_event(event, Prediction(priority=priority, mode="test_fixture"))
        result = client.get(
            "/api/explorer",
            params={
                "source": source,
                "dataset": "filter-fixture",
                "q": "QUARTZ-DB",
                "sort_by": "priority",
                "order": "desc",
                "limit": 2,
            },
        ).json()
        assert result["total"] == 5
        assert [r["prediction"]["priority"] for r in result["items"]] == ["P5", "P4"]
        result = client.get(
            "/api/explorer", params={"source": source, "priority": "P1", "limit": 1}
        ).json()
        assert result["total"] == 1
        assert result["items"][0]["storage"] == "MongoDB"
        assert (
            client.get("/api/explorer", params={"source": source, "q": "filter.*"}).json()["total"]
            == 0
        )
        assert "filter-fixture" in client.get("/api/events/facets").json()["datasets"]


def test_pdf_reference_is_searchable_cited_and_idempotent():
    from test_pdf import reference_pdf

    marker = "pdf-test-" + uuid4().hex
    text = f"{marker} Quartz connection pool exhausted. Inspect pool saturation and release idle connections after confirming they are unused."
    data = reference_pdf(text)
    with TestClient(app, headers={"X-API-Key": settings.api_key}) as client:
        document_id = None
        try:
            response = client.post(
                "/api/knowledge/pdf",
                data={"title": marker, "kind": "runbook"},
                files={"file": (marker + ".pdf", data, "application/pdf")},
            )
            assert response.status_code == 201, response.text
            result = response.json()
            document_id = result["document_id"]
            assert result["inserted"] == 1
            duplicate = client.post(
                "/api/knowledge/pdf",
                data={"title": marker, "kind": "runbook"},
                files={"file": (marker + ".pdf", data, "application/pdf")},
            ).json()
            assert duplicate["inserted"] == 0 and duplicate["duplicates"] == 1
            search = client.get(
                "/api/knowledge/search", params={"q": marker, "category": "references"}
            ).json()
            assert search["total"] == 1 and search["items"][0]["verified"] is False
            answer = client.post("/api/assistant", json={"question": text}).json()
            assert any(marker in s["source"] and "page 1" in s["source"] for s in answer["sources"])
            assert client.get("/api/storage").json()["postgres"]["relations_bytes"] > 0
        finally:
            if document_id:
                with app.state.repo.pool.connection() as conn:
                    conn.execute(
                        "DELETE FROM knowledge WHERE id LIKE %s", ("pdf:" + document_id + ":%",)
                    )
