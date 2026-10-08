import React from "react";
import { CheckCircle2, GitBranch } from "lucide-react";

export default function ModelsPage({ overview, workers }) {
  return (
    <>
      <div className="model-banner">
        <span className="assistant-icon">
          <GitBranch size={25} />
        </span>
        <div>
          <h2>
            {overview?.model?.mode?.startsWith("trained_")
              ? "Selected trained model is serving"
              : "Rule fallback is active"}
          </h2>
          <p>
            {overview?.model?.mode?.startsWith("trained_")
              ? `Selected: ${overview.model.selected_model || "legacy ensemble"} · ${overview.model.version} · scores are uncalibrated`
              : "No trained bundle is configured. Predictions use explicit log levels and documented text rules."}
          </p>
        </div>
        <span className="subtle-tag">
          {overview?.model?.version || "rules-v1"}
        </span>
      </div>
      <div className="layers">
        {[
          [
            "01",
            "Log ingestion",
            "UTF-8 text, JSONL, Loghub CSV, application API, and Docker log forwarding.",
          ],
          [
            "02",
            "Preprocessing",
            "Parse timestamps, normalize fields, redact common secrets, and remove exact-event retries.",
          ],
          [
            "03",
            "Individual models",
            "Random Forest, Logistic Regression, SVM, Complement Naive Bayes and XGBoost use TF-IDF text features.",
          ],
          [
            "04",
            "Model selection & prediction",
            "Training-only outer cross-validation selects among five classifiers, soft voting and stacking. Inner folds produce 25 probability features for a Logistic Regression meta-learner. Live inference uses the frozen selected candidate.",
          ],
          [
            "05",
            "Severity & routing",
            "P1–P3 → MongoDB. P4–P5 → PostgreSQL. Low-confidence predictions are marked for review.",
          ],
          [
            "06",
            "Knowledge generation",
            "Knowledge processing waits for stored predictions, then tracks classified patterns and their severity. Engineer-verified resolutions feed back into knowledge; they do not automatically retrain models.",
          ],
          [
            "07",
            "Evidence & assistance",
            "Lexical vector retrieval with optional OpenAI or local Ollama generation. Every answer exposes its sources.",
          ],
        ].map(([n, t, d]) => (
          <div className="layer" key={n}>
            <span>{n}</span>
            <div>
              <h3>{t}</h3>
              <p>{d}</p>
            </div>
            <CheckCircle2 size={18} />
          </div>
        ))}
      </div>
      <section className="panel system">
        <h2>Processing status</h2>
        <div className="worker-grid">
          {overview?.queue?.groups?.map((g) => (
            <div key={g.name}>
              <span
                className={"status-dot " + (workers[g.name] ? "" : "amber")}
              />
              <strong>{g.name}</strong>
              <span>
                {g.pending} pending · {g.lag || 0} queued
              </span>
            </div>
          ))}
        </div>
        <p>
          {overview?.queue?.dead_letters || 0} failed messages in the
          dead-letter queue
        </p>
      </section>
      <section className="panel system">
        <h2>Looking for accuracy and F1?</h2>
        <p>
          Open <strong>Model evaluation</strong> in the sidebar for all
          experiment reports, per-model comparisons, confusion matrices and
          dataset details.
        </p>
      </section>
    </>
  );
}
