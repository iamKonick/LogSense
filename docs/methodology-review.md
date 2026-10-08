# LogSense — methodology review

Status: implemented research prototype. The user’s confirmation was interpreted as selecting the diagrams in Resources___Thesis/figures. See implementation.md for the decisions and current boundaries.

## User requirements

- Independent application named LogSense, with clean code rather than another version of the old application.
- Implement the user's BPM methodology and individual layer diagrams.
- The old project may inform technology choices and Docker Compose deployment.
- Attached documents are reference material, not instructions authorizing unrelated actions.

## References inspected

- Resources___Thesis/main.tex: methodology and implementation chapters.
- Resources___Thesis/figures: BPM, individual ML, ensemble, knowledge-generation and RAG diagrams.
- thesis_v13_updated_by_h_chat_2026_09_28__1_.pdf: old thesis, 96 pages; text extracted for comparison.
- Desktop/log-parser-ai-asssistent: README, Compose configuration, dependency manifests and module inventory. No source code copied or modified.

## Significant architectural change

The old project's current README describes all priority classes in MongoDB, with additional PostgreSQL vector indexing for selected P4/P5 events. The resource methodology describes exclusive event routing: P1–P3 to MongoDB and P4–P5 to PostgreSQL. Knowledge assets are a separate concern and may include evidence from every class.

Severity increases from P1 to P5: debug, information, warning, error, critical. This is the project's convention.

## Layers in the supplied methodology

1. Ingest repository datasets, generated application logs and Docker logs.
2. Parse, normalize, enrich and deduplicate logs, preserving provenance.
3. Run individual severity models, including Random Forest and Logistic Regression.
4. Produce voting and stacking predictions and a final ensemble result.
5. Route events according to severity.
6. Independently derive patterns and link historical incidents, verified resolutions and runbooks into a knowledge base.
7. Retrieve evidence and generate source-linked incident assistance.
8. Support engineer review, investigation, incident closure and feedback into knowledge.

The text treats autonomous remediation as future work. Recommendations and human incident review belong to the described prototype.

## Decisions still open in the references

- Authoritative diagrams: Resources___Thesis/figures, following the user’s confirmation.
- Training datasets and label provenance; separation of training, validation and test data.
- Additional classifiers, voting weights, stacking folds and final combination policy.
- Confidence thresholds and tie handling; scores must not imply calibrated certainty without validation.
- Deduplication identity, retention window and retry behavior.
- Knowledge schema, embedding model, chunking and retrieval strategy.
- Language model and optional external search policy.
- Incident transitions and criteria for promoting feedback into verified knowledge.

These are engineering/research decisions to record explicitly, not results already established by the thesis.

## Proposed independent code organization

- backend/app/domain: event, prediction, incident and knowledge contracts.
- backend/app/ingestion: source adapters and validation.
- backend/app/preprocessing: parsing, normalization and fingerprints.
- backend/app/classification: shared model interface and inference.
- backend/app/ensemble: voting, out-of-fold stacking and decision policy.
- backend/app/storage: MongoDB and PostgreSQL adapters.
- backend/app/knowledge: evidence extraction, provenance and approved resolutions.
- backend/app/assistant: retrieval and generation adapters.
- backend/app/api: HTTP endpoints and dependency wiring.
- frontend: React interface for events, model outputs, incidents and assistant.
- experiments: reproducible training and evaluation, separate from serving.
- tests: routing, retry, leakage prevention and incident lifecycle checks.
- compose.yaml: independent services, volumes and configurable host ports.

Reuse of FastAPI, React/Vite, scikit-learn, MongoDB, PostgreSQL/pgvector and optional Redis is compatible with the user's request. Do not reuse old service names, volumes, model artifacts or experiment results implicitly.
