# Verification record

Verified locally on 30 September–1 October 2026 using the independent LogSense Docker Compose stack.

## Checks performed

- Frontend production build and source formatting checks.
- Python linting and formatting checks.
- 19 backend unit tests: normalization, timestamp and event identity, source separation, malformed inputs, common-secret redaction, five severity routes, fallback disclosure, tie policy, retrieval abstention, pattern-versus-resolution distinction, vector normalization, CSV metadata preservation, generation failure fallback, and bounded retries.
- 3 live integration tests against MongoDB, PostgreSQL/pgvector and Redis: full ingestion-to-retrieval/incident workflow, exclusive persistence, duplicate submissions, retry routing after a model change, knowledge idempotence, lifecycle validation, historical feedback retrieval, abandoned-message recovery and independent branch acknowledgements.
- 1 training regression test: 80/20 stratified train/test split and source/reference-label independence, OOF stacking, bundle serialization/reload, named base-model outputs and normalized P1–P5 ensemble probabilities.
- Browser checks: new evaluation page and real metrics, explorer source/dataset/limit controls and filtered results; earlier baseline checks: dashboard rendering, synthetic demo ingestion, event inspector, assistant event context, evidence response and source trail.

Total: **23 distinct automated tests**, with the three live tests intentionally skipped outside the Docker environment. The synthetic training fixture is solely a software check and was not promoted to the running application's model registry.

## Running state

Seven independent containers: frontend, API, classifier worker, knowledge worker, MongoDB, PostgreSQL and Redis. Web port 3010; API port 8010. Existing project containers and volumes were not modified.

The running data contains 2,064 held-out Loghub records classified by the trained model, plus 12 historical events explicitly labeled `demo-synthetic`. Integration fixtures created during verification were removed before delivery. Normal live-test runs intentionally leave their `integration-...` fixtures for diagnosis.

## Limits of this verification

- No production-size load test, formal security review, human incident-response study or research generalization evaluation was performed.
- No local Ollama server was available. The generation adapter's offline fallback was tested, but live LLM generation was not.
- The Loghub ensemble is deployed for new events. Assistance remains evidence-only without Ollama.
- The test client emits an upstream Starlette warning about future replacement of its HTTPX transport. Tests pass; the warning does not indicate an application failure.

## Actual Loghub experiment

Official pinned 2k sample collection: 32,000 rows downloaded; 10,319 eligible deduplicated records from nine datasets. Split: 8,255 training / 2,064 testing, seed 42. Source levels provide explicitly documented weak labels. Missing or unrecognized labels are excluded from supervised training, not guessed. All ingested messages can still receive predictions.

The final ensemble achieved accuracy 0.9874031008 and macro F1 0.9253066273. Stacking alone performed better on this test (accuracy 0.9893410853); the predetermined blend was not changed using test results. Full results, class support and the 140 shared normalized templates are disclosed in `experiments/runs/loghub-80-20/report.json`. Exact text overlap is zero.

All 2,064 imported test records completed both processing branches. Both queue groups had zero pending/lag, no dead letters, and healthy worker heartbeats after completion. The running API exposes evaluation artifacts independently of model deployment.

Docker forwarding is supported through `scripts/collect.py`; no permanent collector for arbitrary user containers has been started. A regression check confirms identical message text receives identical ML probabilities across Loghub, static and Docker source tags even when source/reference severities disagree. These scores are not a labeled evaluation of the user's Docker workload.

## Sidebar update

Widened desktop navigation to 280px (260px at intermediate widths), kept labels on one line, and added an accessible hide/show control with browser-local preference persistence. Verified expanded rendering, hiding, refresh persistence and restoring in the browser. Frontend production build passed.

## Dashboard UI audit

Reviewed all seven pages at desktop and 390px phone width, ingestion paste/file tabs, knowledge and incident dialogs, settings, and an assistant question with five returned evidence sources. No records were changed by the dialog checks.

Fixed workspace-card overflow by removing the broad no-wrap rule from card text while retaining single-line menu labels. Corrected the recent-event badge to match the six displayed rows; introduced explicit overview/explorer loading states; added small-screen connection settings access; reset scroll on page navigation; locked background scrolling while dialogs are open; cleared stale incident-save errors before retry. Compact mobile breadcrumbs prevent header crowding. Production frontend builds passed.

## 2026-10-01: deployed methodology alignment and engineering UI

- Added SVM and XGBoost alongside random forest, logistic regression, and Complement Naïve Bayes. Compared all five, soft voting, and stacking using training-only nested cross-validation. Stacking uses 25 out-of-fold class probabilities with a logistic regression meta-learner.
- Grouped split: 8,319 training / 2,000 test records; no shared normalised templates across train and test. TF-IDF is fitted within training folds. Frozen selection policy chooses macro F1, then P4/P5 recall, then fixed candidate order. Held-out scores never choose the deployed model.
- Selected logistic regression, version `20261001T141901Z`. Held-out accuracy 0.987; macro F1 0.8938604171. Source severity remains a proxy reference; the previously inspected corpus means this is exploratory, not a fresh confirmatory experiment.
- Imported all 2,000 new held-out records through the common ingestion/classification/routing/knowledge pipeline. Every record uses the selected version. Live agreement with reference labels is exactly 0.987. Both consumer groups have zero pending/lag, zero dead letters, healthy workers. Historical events remain unchanged.
- Knowledge extraction waits for stored classification. Each new observation records predicted priority and model version.
- Workspace card now contains only Research Workspace. Explorer controls wrap at readable widths. Ingest logs is limited to Overview and Log explorer. Added Documentation and Storage findings menus. Connection settings explains the optional LogSense access key.
- Knowledge page separates references, verified resolutions, and patterns; supports server-side search and paging, full entry reading, and investigation handoff. PDF upload extracts redacted text passages with filename/page provenance and duplicate detection. It does not claim scanned-PDF OCR or automatic verification.
- Local suite: 24 passed, four service-dependent tests skipped. Container suite: 27 passed, including PDF upload → search → assistant citation and duplicate-upload checks. Frontend production build and Python lint pass. Browser inspection verified desktop and 390px mobile layouts, readable explorer controls, and PDF dialog. Temporary integration fixtures were removed.

### Storage experiment, 4,076-event sample

Measured at 2026-10-01 16:10:22 UTC in disposable databases. Sample hash and full methodology are in `experiments/storage-runs/latest.json`.

| Measurement | All PostgreSQL with event vectors | Hybrid |
|---|---:|---:|
| Event data + indexes | 14,565,376 bytes | 2,936,832 bytes |
| Load elapsed | 1.333 s | 0.142 s |
| 2,500 ID reads elapsed | 1.915 s | 2.104 s |
| Database CPU during workload | 0.541 s | 0.384 s |
| Observed database cgroup memory | 117,166,080 bytes | 202,448,896 bytes |

The event-storage reduction is about 79.8%; observed hybrid memory is higher and reads were slower. These are single-trial, local measurements. Memory includes cache and both hybrid database processes; it is not allocated RAM or a peak. Shared operational metadata, knowledge, WAL/journals, Redis, replicas, and backups are outside the event-only comparison. The baseline has per-event vector storage, unlike the hybrid implementation. Do not generalise these numbers into production server or total infrastructure savings.

### Model evaluation loading regression

Reproduced a blank page caused by looking up the removed `ensemble` candidate on the initial render of the new seven-model report. The deferred selection effect could not run because the dataset breakdown threw first. Model selection is now resolved synchronously against the active report, with run-scoped user choices and safe missing-dataset values. Three frontend regression checks pass using the real legacy and current reports, covering initial render, switching reports, and preserving a valid selection on refresh. Run them with `node --test tests/evaluation.test.js` from `frontend/`.
Browser verification after deployment confirmed that the current seven-model report renders its comparison, selected logistic-regression confusion matrix, per-class metrics, and dataset breakdown; switching to the legacy six-candidate report and back succeeds. The sidebar keeps connection settings visible at the bottom.
