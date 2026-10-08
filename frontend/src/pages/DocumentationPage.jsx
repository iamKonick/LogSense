import React from "react";
const sections = [
  [
    "Start an investigation",
    "Ingest logs from Overview or Log explorer. Wait for processing, filter events, and open an event to inspect its predictions and destination. Choose Investigate with assistant to retrieve supporting evidence. For high-severity incidents, record checks and close only after verifying a root cause and resolution.",
  ],
  [
    "Overview & Log explorer",
    "Overview summarises processed events and their destinations. Explorer searches message and service text and filters source, dataset, and predicted priority. Source identifies where a log came from; dataset identifies its collection. Priority is the model prediction, not necessarily the severity printed in the original log. Event details show reference labels, individual predictions, confidence, and destination. Confidence is not a guarantee.",
  ],
  [
    "Log sources",
    "Ingest logs accepts UTF-8 text, JSONL, or CSV (up to 2 MB and 1,000 records per upload). The batch collector supports larger files and Docker forwarding. Loghub is a static collection downloaded from a pinned repository revision, not a continuously connected database. Container logs require a configured collector; this dashboard does not automatically connect every container.",
  ],
  [
    "Incidents",
    "P4 and P5 events create incident candidates. An engineer determines what needs action. Record the investigation and move an incident to investigating or resolved. Closing requires a root cause and resolution. The recorded solution becomes an engineer-verified knowledge entry for future investigations.",
  ],
  [
    "Knowledge base",
    "Runbooks & references contain instructions supplied by people, including PDF passages. Verified resolutions preserve solutions from closed incidents. Observed patterns group recurring message templates and count occurrences; repetition alone does not establish a cause. Search titles, content, and sources, and choose Read full entry for complete text.",
  ],
  [
    "Add a PDF resolution",
    "Choose Add reference → Upload PDF. Include service names, symptoms, checks, and resolution steps. Upload a text-based PDF up to 10 MB and 100 pages. LogSense extracts and redacts text, splits it into searchable passages, and records filename/page citations. It stores passages, not the original PDF. Scanned pages need OCR first. Re-uploading identical PDF bytes skips existing passages. Uploading does not mark a solution as verified.",
  ],
  [
    "AI assistant & evidence",
    "Ask a specific question with service and error text, or start from an event. Retrieval uses lexical vector similarity: matching words and phrases, not semantic embeddings. It can miss differently worded issues. Read citations and verify applicability before applying a fix. Without a configured local language model, the assistant returns evidence-only results. A new reference is immediately searchable but is not guaranteed to appear for every similar issue.",
  ],
  [
    "Model evaluation",
    "Eligible Loghub records use mapped source severity as proxy reference labels, not independent expert judgements. A grouped split reserves approximately 20% for testing with identical normalised templates kept apart. Training-only nested cross-validation compares random forest, logistic regression, SVM, naïve Bayes, XGBoost, soft voting, and stacking. A logistic meta-learner uses 25 out-of-fold probability features: five models × five classes. The selected candidate is refitted on training data before held-out evaluation. Test scores do not select it. Review macro F1, per-class recall, confusion matrices, and sample counts. Previously examined data makes this exploratory research.",
  ],
  [
    "Models & pipeline",
    "Logs are parsed, normalised, and redacted. Fitted text vectorisers transform cleaned messages into numerical features. The selected model predicts P1–P5; P1–P3 payloads go to MongoDB and P4–P5 payloads to PostgreSQL. Knowledge extraction waits for the persisted classification. Training and live inference are separate. Existing events retain their original model version after deployment changes.",
  ],
  [
    "Storage findings",
    "Live measurements show actual relation and index allocation. A controlled benchmark compares identical payloads under hybrid routing against PostgreSQL with a 384-dimensional vector for every event. Shared knowledge and routing metadata are excluded from the event-only comparison. Per-event vector storage is an extra baseline capability; hybrid provides knowledge-level retrieval instead. Small datasets can make hybrid storage larger. Local CPU and memory results do not prove production savings. A storage price estimates disk-cost difference only, excluding compute, replication, backups, and minimum charges.",
  ],
  [
    "Connection settings",
    "This is the optional LogSense access key set by your administrator using LOGSENSE_API_KEY. It protects this application’s API and is not an OpenAI key. Leave it blank if your local instance has no key. The browser retains it only for this session. The administrator configures the local language-model connection separately.",
  ],
];
export default function DocumentationPage() {
  return (
    <div className="documentation">
      <section className="panel">
        <h2>Engineer’s guide</h2>
        <p>
          LogSense is a research prototype for severity classification, routing,
          and evidence-assisted investigation. Engineers remain responsible for
          diagnosis and resolution.
        </p>
        <nav aria-label="Guide contents">
          {sections.map(([title], i) => (
            <a key={title} href={`#guide-${i}`}>
              {title}
            </a>
          ))}
        </nav>
      </section>
      {sections.map(([title, body], i) => (
        <section className="panel" id={`guide-${i}`} key={title}>
          <h2>{title}</h2>
          <p>{body}</p>
        </section>
      ))}
    </div>
  );
}
