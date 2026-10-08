# Reproducing LogSense

Run commands from the application directory containing `compose.yaml`, `backend/`, `frontend/`, `scripts/` and `experiments/`. The Compose file alone is not the application source. The thesis copy is identical to the application file. No private `.env`, API key or database export is needed.

## Prerequisites and startup

Use Docker Engine with Docker Compose v2, or a running Docker Desktop installation with Linux containers. Initial builds need internet access to the image and package registries; initial dataset preparation needs GitHub access. Unix shell commands below work in macOS/Linux terminals; on Windows use WSL2. Host Python is only needed for the optional host collector. No host Node.js or Python environment is required for the container training route below.

On a fresh checkout only, copy the public example (do not overwrite an existing configuration):

```sh
cp .env.example .env
docker compose config --quiet
docker compose up -d --build --wait
docker compose ps
```

Open http://localhost:3010. API health is http://localhost:8010/api/health and interactive documentation is http://localhost:8010/docs. With a nonempty `LOGSENSE_API_KEY`, enter that same administrator-chosen value in Connection settings and send it as the `X-API-Key` header. This is not an OpenAI key.

A fresh example configuration leaves `MODEL_PATH` empty: the dashboard runs in explicitly labelled rules-fallback mode until a trusted trained bundle is configured. Existing report files may populate Model evaluation without being the active deployed model. Do not describe fallback predictions as ML evaluation. Data is not seeded automatically; synthetic demo ingestion is available in the Overview and Log explorer.

## Seven services and persistence

- `frontend`: Node builds the React application using `npm ci`; NGINX serves it and proxies API requests. Only port 3010 is published to loopback.
- `api`: builds the Python backend, installs `requirements.lock`, validates input, initializes storage and exposes port 8010 on loopback.
- `classifier`: reuses the backend image and runs the classification stream consumer.
- `knowledge-worker`: runs the separate knowledge consumer, waiting for stored predictions before processing them.
- `mongodb`: lower-severity event payloads, persisted in `mongo-data`.
- `postgres`: high-severity payloads plus receipts, incidents and shared vector knowledge, persisted in `postgres-data`.
- `redis`: queues with append-only persistence in `redis-data`.

Database health checks gate API startup. API health gates workers and frontend. Workers have no separate Compose health check, so API health alone does not prove queue completion. Inspect Models & pipeline, ingestion receipts and worker logs. Internal service names resolve on the Compose network; database ports are not published. Read-only bind mounts expose trusted models, model reports and benchmark reports. Ollama is optional and is not started by this Compose file.

## Train inside the same backend environment

The next command uses the backend image's installed dependencies, with a writable project mount. It does not start a second API server. Choose an output path that does not already exist.

```sh
docker compose run --rm --no-deps \
  --user "$(id -u):$(id -g)" \
  -v "$PWD:/research" -w /research \
  api python scripts/train_loghub.py \
  --output experiments/runs/reproduction --seed 42
```

Preparation uses the pinned Loghub revision in `experiments/loghub.py`, caching official structured 2,000-line samples. It produces the manifest and labelled CSV, then fits fold-local TF-IDF, compares five classifiers and two ensembles using nested training-only selection, and writes `model.joblib`, `report.json` and `split-indices.json`. Stacking uses out-of-fold base probabilities. Inspect these artifacts before deployment. The thesis frozen split has 8,319 training / 2,000 test examples; retraining times and exact floating-point results depend on environment. Never overwrite the frozen `loghub-grouped-selection` run to make a new result appear historical.

Deploy your new trusted bundle:

```sh
mkdir -p models
cp experiments/runs/reproduction/model.joblib models/reproduction.joblib
```

Set `MODEL_PATH=/models/reproduction.joblib` in `.env`, then:

```sh
docker compose up -d --force-recreate api classifier knowledge-worker
```

Verify Models & pipeline shows trained-selected mode and the intended version/selected candidate. Existing events retain their first model decision; new events use the configured bundle. Model files use Python deserialization, so use only your own or otherwise trusted artifacts.

## Import the held-out partition

Use the internal API URL from a one-off container:

```sh
docker compose run --rm --no-deps \
  --user "$(id -u):$(id -g)" \
  -v "$PWD:/research" -w /research \
  api python scripts/import_loghub.py \
  --run experiments/runs/reproduction \
  --partition test --url http://api:8000
```

The importer checks the prepared data hash, queues records, preserves weak reference labels separately, and writes receipt IDs. Wait for classification and knowledge completion before comparing totals. Reimporting the same run uses stable identities; importing another run may add new events. On a fresh database with only this import, expect 2,000 events, not the 4,079 events visible in the thesis screenshots. Screenshots contain earlier imports and three audit fixtures. No new training or effectiveness evaluation was performed merely to take screenshots.

Static files can be uploaded through Log explorer. Docker logs require an explicit host-side forwarder (replace the two uppercase names):

```sh
docker logs --timestamps --follow YOUR_CONTAINER 2>&1 | \
  python3 scripts/collect.py --source docker \
  --service YOUR_SERVICE --batch-size 1
```

The collector defaults to localhost:8010 and reads `LOGSENSE_API_KEY` from the host environment. Adjust its `--url` for a changed port. No Docker socket is mounted into the application.

## Verification, benchmark and shutdown

```sh
docker compose logs --tail=100 api classifier knowledge-worker
docker compose exec -T api python -m pytest tests -q -p no:cacheprovider
```

The latter runs backend tests with live-only tests skipped unless enabled. Run live tests only in a disposable research deployment because they write fixtures:

```sh
docker compose exec -T -e LOGSENSE_TEST_LIVE=1 \
  api python -m pytest tests -q -p no:cacheprovider
```

The separate storage benchmark requires host Python dependencies from `backend/requirements.lock` and access to the host Docker CLI. In that prepared environment run `python scripts/benchmark_storage.py`. It snapshots current payloads and creates disposable benchmark databases; it does not benchmark through the API container, which has no Docker socket. It writes `experiments/storage-runs/latest.json`; reruns replace that latest report, so archive the frozen evidence first. Different payloads or machine state can produce different measurements.

Stop while preserving named database volumes:

```sh
docker compose down
```

Avoid `down -v` unless intentionally discarding that deployment's data. Restart with `docker compose up -d`. On an initialized PostgreSQL volume, editing `POSTGRES_PASSWORD` does not change the database role password; coordinate an actual database password change before changing application credentials. Common startup checks are Docker running, free ports, readable bind-mounted bundle, completed image build, and worker logs.

## Reproducibility limits and verification record

On 7 October 2026 the public example configuration passed `docker compose --env-file .env.example config --quiet`, all seven existing services were running (API and three databases healthy), and the container training command was checked in `--help` mode. This verifies configuration and command availability, not a new clean-machine build, retraining trial or repeated storage benchmark. Previously recorded build/test results are in the audit evidence.

Python and frontend package lock files are supplied. Image tags (`python:3.14-slim`, `node:22-alpine`, `nginx:1.28-alpine`, `mongo:8.0`, `pgvector/pgvector:pg17`, `redis:7.4-alpine`) are not immutable digests, and system packages are not snapshot-pinned. Record image digests, Docker versions, host architecture/resources, source checksums, dataset hash and run artifacts for any new experiment. These instructions provide procedural reproducibility, not bit-for-bit reproducibility or a validated production installation.
