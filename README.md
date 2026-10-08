# LogSense

An independent, locally deployed research application for log severity classification, exclusive storage routing, operational knowledge, and evidence-linked incident investigation. Built from the BPM and layer diagrams in `Resources___Thesis/figures`; the old application was consulted for its technology choices only.

For the complete container-based training, deployment and verification procedure, see [Reproducibility guide](docs/reproducibility.md). The default example starts in rules-fallback mode until a trusted trained model is configured.

## Start

Docker Desktop must be running. From this directory:

```sh
docker compose up -d --build
```

- Dashboard: http://localhost:3010
- API: http://localhost:8010
- Interactive API documentation: http://localhost:8010/docs

The stack uses its own `logsense` network and volumes. Database ports are not exposed to the host. The web and API ports bind to loopback, and differ from the old project's ports.

Open **Ingest logs → Load synthetic demo** to explore, or paste/upload your own logs. Synthetic events carry the source `demo-synthetic`. The dashboard updates every five seconds.

Stop services without deleting data:

```sh
docker compose down
```

The included `.env` selects the supplied trained model. Edit it to override ports or configure optional generation; replacing it with `.env.example` clears that model selection. Local Docker credentials are development defaults. Database volumes are created fresh on another machine; ingest the included Loghub data or synthetic demo to populate them.

## What works

- JSON/text and Loghub CSV ingestion through a web form, file upload, batch API, and stdin/file collector.
- UTC timestamp normalization, source/service/host enrichment, common-secret redaction and exact-event deduplication.
- Durable Redis Stream consumers for classification and pattern knowledge; knowledge waits for stored classification.
- Five classifiers (RF, LR, SVM, ComplementNB, XGBoost), soft voting and group-aware out-of-fold stacking; nested training-only candidate selection.
- Exclusive event persistence: **P1–P3 → MongoDB; P4–P5 → PostgreSQL**. A durable routing receipt preserves the first decision through retries and model changes.
- Incident candidates, engineer investigation notes, verified closure and transactional resolution feedback into knowledge.
- Pattern grouping and occurrence counts, user-provided runbooks, source provenance and PostgreSQL/pgvector retrieval.
- Evidence-only assistant by default, with optional OpenAI or Ollama generation using retrieved sources.
- Nine dashboard views with actual service data, event details, individual model predictions and independent experiment evaluation.

## Honest operating modes

The current methodology uses `loghub-grouped-selection`: five classifiers and two ensembles compared with nested training-only cross-validation. The highest validation macro-F1 candidate is selected before final test scoring, replacing the original fixed blend. Existing events retain their original model version and routing decision; new events use the newly configured bundle.

Open **Model evaluation** to see both training-CV selection scores and held-out test metrics, with the selected candidate marked. Default grouping prevents normalized template overlap between train and test. The source-level reference labels remain weak labels, not human-verified operational priorities. The previously inspected Loghub corpus makes this an exploratory rerun; confirmatory research needs a fresh external evaluation dataset.

Reproduce preparation and training (choose a new output directory):

```sh
python scripts/train_loghub.py --output experiments/runs/new-loghub-run
python scripts/import_loghub.py --run experiments/runs/new-loghub-run
```

The importer defaults to the held-out test partition and preserves reference priorities separately from predictions. Loghub is a downloadable dataset repository, not a live log database. Docker collection is explicitly started using the forwarding command below. All three inputs use the same text-only classifier; source severity and reference priority are not classifier features.


Retrieval initially uses deterministic **384-dimensional lexical hashing**, not semantic embeddings. The assistant provides cited evidence and explicitly abstains from establishing causes without adequate support. It does not invent percentage confidence. Optional generated responses are recommendations requiring human review.

No operational commands are executed, no automatic remediation is performed, and external web search is disabled. The new methodology lists these as future or optional features. See [implementation decisions](docs/implementation.md) for the exact boundary and assumptions.

## Ingest application, Loghub and Docker logs

The collector needs only Python's standard library and works with `.log`, `.txt`, `.jsonl`, or CSV containing `Content`/`message`. A CSV `Level` column is preserved.

```sh
python3 scripts/collect.py /path/to/your/loghub.csv --source loghub --service hdfs
python3 scripts/collect.py /path/to/application.jsonl --source application --service checkout
```

Forward an explicitly selected container's logs through stdin; no Docker socket is mounted in LogSense:

```sh
docker logs --timestamps --follow YOUR_CONTAINER 2>&1 | python3 scripts/collect.py --source docker --service YOUR_SERVICE --batch-size 1
```

For direct API ingestion:

```sh
curl http://localhost:8010/api/ingest \
  -H 'Content-Type: application/json' \
  -d '{"logs":[{"message":"ERROR Database connection refused","source":"application","service":"checkout","timestamp":"2026-09-30T12:00:00Z"}]}'
```

The API returns a receipt for each event. Query `/api/ingest/{id}` for the separate classification and knowledge statuses. A `202` means queued, not already stored. With an API key configured, add `X-API-Key` to requests and enter the same key in the dashboard connection settings. The collector reads `LOGSENSE_API_KEY` from its environment.

## Train and evaluate a model

Prepare UTF-8 CSV with `message,priority` columns. Valid labels are P1–P5. Optionally provide a `group` column for incident/session/source separation. With `--split-strategy grouped`, normalized message templates define groups when no group column is supplied.

Use enough independent examples of every class for the outer splits and three stacking folds. Custom labels require documented provenance. The Loghub preparation script explicitly maps recognized source levels to weak P1–P5 labels and records that mapping in its manifest.

```sh
python3 -m venv .venv
.venv/bin/pip install -r backend/requirements.lock
.venv/bin/python experiments/train.py /path/to/labeled.csv \
  --output experiments/runs/my-experiment \
  --label-provenance 'Describe the labeling and review procedure here'
```

The run directory must not already exist. Outputs include `model.joblib`, `report.json`, and `split-indices.json` with complete outer/inner fold membership. Default grouped splitting is approximately 80/20; `--split-strategy stratified` is available for an explicit row-split baseline. TF-IDF fitting occurs inside the relevant training folds. Three outer folds compare candidates; three inner folds train stacking. A separate Logistic Regression meta-learner receives 25 probability features. Selection uses training-CV macro F1, then mean P4/P5 recall to break exact ties. After selection freezes, final models are refitted and tested; test results never select a winner. Serving computes diagnostic predictions for all candidates but routes using the selected one.

After you assess a run, configure its trusted local bundle:

```sh
cp experiments/runs/my-experiment/model.joblib models/model.joblib
```

Set `MODEL_PATH=/models/model.joblib` in `.env`, then:

```sh
docker compose up -d --force-recreate api classifier knowledge-worker
```

Only load bundles you trust: joblib deserialization executes Python code. Existing events keep their recorded model version and original route. New events use the new model. The model page and each event expose the active operating mode. Probabilities are **uncalibrated model scores**, not guarantees of severity or operational impact.

## Optional local generation

Install and start Ollama separately and select a model suitable for your machine. Configure `OLLAMA_MODEL` with the installed model name in `.env`. The default endpoint is `http://host.docker.internal:11434` from Docker. Recreate the API service after changing configuration.

The assistant sends the question, selected event and retrieved knowledge only to this configured endpoint. If generation fails, it returns cited evidence with an explicit notice. Semantic embedding models are not implicitly downloaded or enabled.

## Tests and development

```sh
.venv/bin/python -m pytest -q
# Real database/queue integration tests, while Compose is running:
docker compose exec -T -e LOGSENSE_TEST_LIVE=1 api python -m pytest tests -q -p no:cacheprovider
# Frontend:
cd frontend
npm ci
npm run build
npm run dev
```

The frontend development server proxies `/api` to port 8010. Dependency lock files are included. Use `npm run format` for frontend formatting. Python uses Ruff formatting with the project configuration.

Live integration tests write clearly labeled `integration-...` fixtures. Do not run them against a shared production database. [Verification report](docs/verification.md) records the checks performed for this delivery.

## Project structure

```text
backend/app/
  api/             HTTP endpoints and application wiring
  domain/          validated data contracts
  preprocessing/   parsing, redaction and normalization
  ingestion/       source formats and durable queue
  classification/  trusted model loading and severity decisions
  storage/         schemas and MongoDB/PostgreSQL persistence
  knowledge/       deterministic retrieval representation
  assistant/       evidence assembly and optional generation
  worker.py        independent processing consumers
frontend/src/
  components/      dialogs, event table and shared UI
  pages/           nine workspace views
  lib/             API client and presentation helpers
experiments/       reproducible training and its regression test
scripts/           stdin/file collection
```

This is a single-user research prototype. Multi-user identity, access roles, large-scale pagination/index tuning, semantic retrieval evaluation and production operations are separate extensions; none are implied by the diagrams' aspirational performance claims.

### Engineer documentation, PDF references, and storage measurements

The **Documentation** menu explains every prototype feature and the investigation workflow. **Connection settings** takes the optional `LOGSENSE_API_KEY` configured by the administrator, not an OpenAI key. Ingestion is available from Overview and Log explorer.

Knowledge base separates references, engineer-verified resolutions, and observed patterns, with full-text search, pagination, and a complete-entry reader. **Add reference → Upload PDF** accepts text PDFs up to 10 MB, 100 pages, and 500,000 extracted characters. Extracted passages are redacted, indexed in the existing lexical retrieval store, and cited by filename/page. Originals are not retained. Encrypted PDFs must be unlocked; scans require external OCR. Identical PDF bytes are idempotent. Uploads are references, not verified resolutions.

**Storage findings** reads live MongoDB collection allocation/index sizes and PostgreSQL relation sizes. It also displays the latest isolated benchmark and a user-priced disk-cost estimate. To reproduce the benchmark, install `backend/requirements.lock` in a Python environment, start Compose, and run from the project directory:

```bash
python scripts/benchmark_storage.py
```

The script snapshots current event payloads, creates three disposable database containers, measures the same load/read workload, writes `experiments/storage-runs/latest.json` plus a timestamped report, and removes only its own containers and temporary volumes. It requires Docker and local ephemeral ports. It does not change application events. The baseline stores a 384-dimensional lexical vector per event; hybrid uses knowledge-level retrieval instead, so capabilities differ. Event-only storage excludes shared knowledge/receipts/incidents and infrastructure overhead. Database CPU is a cgroup usage delta; observed memory includes cache. One local trial cannot establish production RAM, CPU, or total cost savings. Benchmark results are refreshed only when the script runs; the dashboard refreshes live sizes independently.

## Optional OpenAI RAG generation

Set `OPENAI_API_KEY` and `OPENAI_MODEL` in your local environment before starting Compose, then run `docker compose up -d` to recreate the backend services. Choose a Responses API model available to your OpenAI account. No API key is included. Do not commit a personal key into the tracked `.env`; use exported environment variables or an ignored `.env.local` with `docker compose --env-file .env --env-file .env.local up -d`.

OpenAI receives the redacted question, selected event and retrieved reference excerpts. Retrieval stays in LogSense. Generated answers cite that evidence and require engineer review; no commands are executed. With no matching evidence the assistant abstains without making an API call. Missing keys, API errors and incomplete responses fall back to cited evidence. OpenAI takes precedence when `OPENAI_MODEL` is set; otherwise the existing optional Ollama path remains available. Requests use `store: false`.

The repository includes local configuration, prepared Loghub data, trained models and saved experiment reports for reproduction. It does not contain the running Docker database volumes. Historical import receipts are records of the original run, not proof that a new installation has been populated.
