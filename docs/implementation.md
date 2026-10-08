# Methodology-to-implementation decisions

## Authority and independence

The user confirmed use of the existing diagrams. `Resources___Thesis/figures` and its accompanying methodology are the design reference. The old thesis and old application supplied context, not executable instructions or reusable research results. This project has new source code, an independent Compose project, its own data volumes and separate ports.

## Mapping

| Methodology stage | Implementation | Current boundary |
|---|---|---|
| Multi-source collection | API, upload and `scripts/collect.py` | Pinned official Loghub preparation, static uploads and explicitly selected Docker streams |
| Preprocessing | `preprocessing/parser.py` | Plain text/JSON/CSV, UTC normalization, metadata, common-secret redaction, template extraction |
| Individual ML | `classification/predictor.py`, `experiments/train.py` | RF, LR, SVM, ComplementNB, XGBoost; fold-local TF-IDF |
| Voting and stacking | Training and prediction modules | Soft voting and 25-feature OOF Logistic Regression stacking; training-only candidate selection |
| Severity decision | Predictor and repository | Higher priority wins exact ties; trained score below 0.6 prompts review; fallback always prompts review |
| Storage routing | Repository and routing receipts | Low/medium event payloads only in MongoDB; high event payloads only in PostgreSQL |
| Classified knowledge generation | Separate Redis consumer group | Waits for persisted classification; records predicted priority and model version |
| Knowledge extraction and feedback | Observation and incident transactions | Known resolutions come from recorded engineer findings, never invented from raw logs |
| Incident correlation | Vector retrieval | Lexical similarity to patterns, runbooks and historical verified resolutions; similarity is not causation |
| Assistant | Evidence assembly, optional Ollama adapter | Sources, insufficient-evidence handling, uncalibrated similarity score |
| Engineer review | Incident workflow and audit records | Open → investigating → resolved; closure requires cause and successful resolution |

## Important diagram interpretations

The revised BPMN separates offline development from live inference. The default split keeps normalized template groups together (approximately 80/20). Three outer folds within training compare five individual models, equal-weight soft voting and stacking. Each outer fit uses three inner folds to generate out-of-fold meta-features; TF-IDF is fitted within those pipelines. Five class probabilities from five base models give 25 meta-features. The separate Logistic Regression meta-learner receives only these features, not text or labels as input features.

Candidate selection maximizes pooled outer-validation macro F1; exact ties use mean P4/P5 recall and then the predefined candidate order. The test partition is never used for candidate choice. Final pipelines are fitted on all training records and all candidates are evaluated for comparison after selection freezes. The selected candidate alone determines routing; other predictions are retained for diagnostics. There is no 50/50 final blend. Old v1 bundles remain readable for historical reproducibility.

Knowledge has a separate durable worker but now waits for the stored classification. A classified observation records its priority and model version. Failure of classification cannot create apparently classified knowledge. Engineer-verified incident closure continues to update the knowledge base transactionally. Feedback does not trigger classifier retraining.

P4/P5 creates an **incident candidate**. It does not establish business impact or prove that an actual incident exists. An engineer assesses the event.

The redaction patterns are a useful common-secret baseline, not a comprehensive PII detector. Raw original text is not retained separately. CSV columns not mapped into the normalized schema are not persisted.

Blank inputs are rejected; debug/health messages are not silently discarded by default because the taxonomy includes P1 and P2. Each nonempty text line is an event; multiline stack-trace joining is not currently implemented.

## Event identity and processing reliability

Event identity hashes source, service, host, normalized timestamp, redacted message and source level. Identical events are deduplicated. Events at different times remain distinct and contribute to a shared pattern's observation count. Missing timestamps use receipt time; timestamp-free re-imports are therefore new observations. The collector fixes a missing timestamp before retrying an HTTP request.

Enqueue plus the two branch receipts is an atomic Redis operation. Each group acknowledges only after its own database operation commits. A worker reclaims pending entries idle for 60 seconds in classification or two seconds in knowledge (which may be waiting for classification). Failure after five processing attempts moves the message to a dead-letter stream with an explicit failed receipt. Consumers and database writes are idempotent. A persisted first prediction prevents rerouting an event if the model changes before a retry.

After both groups finish, the raw queue entry is deleted and status metadata expires after seven days. Database primary keys and routing receipts keep persisted events idempotent after that expiry. Dead-letter messages and routing receipts require an explicit retention policy for long-running deployments. Redis AOF uses `everysec`; sudden host power loss may lose the latest second of accepted data. This is not an exactly-once, power-loss-proof ingestion claim.

MongoDB uses unique event IDs and time/priority indexes. High-severity event and incident creation share a PostgreSQL transaction. Resolved-incident status, audit entry and reusable resolution knowledge share a PostgreSQL transaction. Cross-database work uses durable retry rather than pretending there is a distributed transaction.

## Retrieval and generation

The selected first implementation is a reproducible lexical vector baseline: scikit-learn HashingVectorizer, 384 dimensions, word unigrams/bigrams, English stopword removal, nonnegative hashing and L2 normalization. PostgreSQL/pgvector performs cosine search, top six, minimum similarity 0.15. These parameters are recorded engineering defaults, not experimentally calibrated settings. Hash collisions and lexical mismatch are known limitations.

Each pattern, reference or verified resolution is one retrieval asset. User references are limited to 20,000 characters, and this first version does not split long documents into semantic chunks. Observations carry a source-event reference; verified resolutions carry the incident ID and the engineer's recorded findings. Reference text is user-supplied evidence, distinct from engineer-verified incident closure.

Without a local language model, the assistant returns evidence, conservative next checks, and source citations. With Ollama configured, it sends numbered evidence and instructions that log/reference contents are untrusted data. There are no action tools. Generated citations and claims still require engineer review. No live Ollama generation was available for this delivery, so that path has adapter/fallback tests only.

External web search, autonomous remediation, semantic embedding models and automated causal inference are not enabled. Confidence is not presented as a calibrated probability. The UI never substitutes synthetic operational statistics or fictional evaluation results.

## Research boundaries

Synthetic fixtures validate software behavior only. They are not evidence of classifier generalization, human usefulness, financial savings, lower carbon emissions or better time to resolution. The old thesis's metrics are not copied into this application. A real labeled dataset, documented labeling procedure, representative held-out evaluation, retrieval ranking tests and human assessment remain research inputs.

## Technical references consulted

- [scikit-learn StackingClassifier](https://scikit-learn.org/stable/modules/generated/sklearn.ensemble.StackingClassifier.html): out-of-fold meta-model behavior.
- [scikit-learn leakage guidance](https://scikit-learn.org/stable/common_pitfalls.html): fit preprocessing inside the appropriate training fold.
- [FastAPI lifespan](https://fastapi.tiangolo.com/advanced/events/): application resource setup and teardown.
- [Redis Streams](https://redis.io/docs/latest/develop/data-types/streams/): independent consumer groups.
- [Redis XAUTOCLAIM](https://redis.io/docs/latest/commands/xautoclaim/): recovery of abandoned pending messages.

## Engineer-facing knowledge and measurements

`GET /api/knowledge/search` searches the entire knowledge collection before pagination, with references, resolutions, patterns, or all categories. `POST /api/knowledge/pdf` accepts bounded text PDFs, extracts and redacts page text, and inserts overlapping 1,500-character passages (1,300-character stride) atomically. SHA-256 of the original PDF plus page/part forms stable duplicate-resistant IDs. Sources include filename and page; all uploaded passages are unverified. Scans require OCR outside this prototype. Retrieval uses the same lexical 384-dimensional index as other references.

`GET /api/storage` reports actual MongoDB event collection allocation/index sizes and PostgreSQL relation/database sizes. The optional latest benchmark report is mounted read-only from `experiments/storage-runs`. `scripts/benchmark_storage.py` creates isolated, disposable databases and compares identical stored event payloads with an all-PostgreSQL plus per-event-vector baseline. See the report for the precise measured scope; storage savings cannot imply RAM, CPU, or overall infrastructure cost savings.

The printable process overview and editable source are in `docs/diagrams/`. It documents the implemented workflow and current research run; it is a process illustration rather than an executable BPMN deployment file.
