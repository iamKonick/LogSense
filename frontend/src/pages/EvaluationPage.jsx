import React, { useState, useEffect } from "react";
import {
  BarChart3,
  RefreshCw,
  Database,
  Download,
  TriangleAlert,
} from "lucide-react";
import { api } from "../lib/api";
import { Empty } from "../components/Shared";
import { modelForRun } from "../lib/evaluation";
import { labels } from "../lib/presentation";
const names = {
  random_forest: "Random Forest",
  logistic_regression: "Logistic Regression",
  svm: "Support Vector Machine",
  xgboost: "XGBoost",
  naive_bayes: "Complement Naive Bayes",
  soft_voting: "Soft voting",
  stacking: "Stacking",
  ensemble: "Final ensemble",
};
const percent = (v) => `${(v * 100).toFixed(2)}%`;
export default function EvaluationPage() {
  const [runs, setRuns] = useState([]),
    [selected, setSelected] = useState(""),
    [modelSelection, setModelSelection] = useState(null),
    [error, setError] = useState(""),
    [loading, setLoading] = useState(true),
    [refresh, setRefresh] = useState(0);
  useEffect(() => {
    let active = true;
    setLoading(true);
    api("/evaluations")
      .then((data) => {
        if (active) {
          setRuns(data.runs);
          setSelected((current) =>
            data.runs.some((r) => r.run_id === current)
              ? current
              : data.runs[0]?.run_id || "",
          );
          setError("");
        }
      })
      .catch((e) => {
        if (active) setError(e.message);
      })
      .finally(() => {
        if (active) setLoading(false);
      });
    return () => {
      active = false;
    };
  }, [refresh]);
  const run = runs.find((r) => r.run_id === selected),
    model = modelForRun(run, modelSelection),
    metrics = run?.test_metrics?.[model],
    classes = run?.classes || Object.keys(labels);
  const setModel = (name) =>
    setModelSelection({ runId: selected, model: name });
  const download = () => {
    const url = URL.createObjectURL(
      new Blob([JSON.stringify(run, null, 2)], { type: "application/json" }),
    );
    const a = document.createElement("a");
    a.href = url;
    a.download = `${run.run_id}-evaluation.json`;
    a.click();
    setTimeout(() => URL.revokeObjectURL(url), 0);
  };
  return (
    <>
      <div className="section-toolbar">
        <span>
          Experiment results are available independently of deployment
        </span>
        <button
          className="secondary"
          disabled={loading}
          onClick={() => setRefresh((n) => n + 1)}
        >
          <RefreshCw size={15} />
          Refresh results
        </button>
      </div>
      {error && (
        <div className="error" role="alert">
          {error}
        </div>
      )}
      {!run ? (
        <section className="panel">
          <Empty
            icon={BarChart3}
            title={
              loading ? "Loading evaluations…" : "No completed evaluation yet"
            }
          >
            Run the Loghub preparation and training commands in the setup guide.
            Real results will appear here when training completes.
          </Empty>
        </section>
      ) : (
        <>
          <section className="panel evaluation-heading">
            <label>
              Experiment
              <select
                aria-label="Experiment"
                value={selected}
                onChange={(e) => setSelected(e.target.value)}
              >
                {runs.map((r) => (
                  <option key={r.run_id} value={r.run_id}>
                    {r.run_id}
                  </option>
                ))}
              </select>
            </label>
            <div>
              <h2>
                {run.data_source
                  ? "Loghub severity classification"
                  : "Severity classification"}
              </h2>
              <p>
                {run.split_description || run.split_strategy} · Seed {run.seed}{" "}
                · {Math.round(run.training_seconds)} seconds training
              </p>
            </div>
            <button className="secondary" onClick={download}>
              <Download size={15} />
              Export report
            </button>
          </section>
          {run.selected_model && (
            <section className="panel system">
              <h2>
                Selected from training cross-validation:{" "}
                {names[run.selected_model]}
              </h2>
              <p>
                {run.selection_policy}. Test results below were calculated only
                after selection was frozen.
              </p>
              <p>
                Stacking: 5 classifiers × 5 class probabilities ={" "}
                {run.meta_feature_count} meta-features. Inner folds train the
                meta-learner; outer folds compare all 7 candidates.
              </p>
            </section>
          )}
          <div className="evaluation-caution">
            <TriangleAlert size={19} />
            <div>
              <strong>Understand what the scores measure</strong>
              <p>{run.label_provenance}</p>
              <p>{run.interpretation}</p>
            </div>
          </div>
          <div className="metrics">
            <div className="metric">
              <div>Training records</div>
              <strong>{run.split_counts.train.toLocaleString()}</strong>
              <small>{percent(run.train_fraction)} of prepared data</small>
            </div>
            <div className="metric">
              <div>Held-out test records</div>
              <strong>{run.split_counts.test.toLocaleString()}</strong>
              <small>
                {percent(run.test_fraction)} · never used to fit models
              </small>
            </div>
            <div className="metric">
              <div>Models compared</div>
              <strong>{Object.keys(run.test_metrics).length}</strong>
              <small>Individual + ensemble methods</small>
            </div>
            <div className="metric">
              <div>Datasets used</div>
              <strong>{Object.keys(run.dataset_counts || {}).length}</strong>
              <small>Text only · source level excluded</small>
            </div>
          </div>
          <section className="panel">
            <div className="panel-heading">
              <div>
                <h2>Model comparison</h2>
                <p>
                  Same held-out test set for every model. Select a row for
                  detailed results.
                </p>
              </div>
            </div>
            <div className="table-wrap">
              <table className="evaluation-table">
                <thead>
                  <tr>
                    <th>Model</th>
                    {run.validation_metrics && <th>Training CV macro F1</th>}
                    <th>Accuracy</th>
                    <th>Macro precision</th>
                    <th>Macro recall</th>
                    <th>Macro F1</th>
                    <th>Weighted F1</th>
                    <th>MCC</th>
                  </tr>
                </thead>
                <tbody>
                  {Object.entries(run.test_metrics).map(([name, m]) => (
                    <tr
                      key={name}
                      className={model === name ? "selected-model" : ""}
                      onClick={() => setModel(name)}
                    >
                      <td>
                        <button
                          className="event-link"
                          onClick={() => setModel(name)}
                        >
                          {names[name] || name}
                          {run.selected_model === name ? " · selected" : ""}
                        </button>
                      </td>
                      {run.validation_metrics && (
                        <td>
                          {run.validation_metrics[name]?.macro_f1?.toFixed(3) ??
                            "—"}
                        </td>
                      )}
                      <td>{percent(m.accuracy)}</td>
                      <td>{m.per_class["macro avg"].precision.toFixed(3)}</td>
                      <td>{m.per_class["macro avg"].recall.toFixed(3)}</td>
                      <td>{m.macro_f1.toFixed(3)}</td>
                      <td>{m.weighted_f1.toFixed(3)}</td>
                      <td>{m.mcc.toFixed(3)}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          </section>
          {metrics && (
            <div className="evaluation-grid">
              <section className="panel">
                <div className="panel-heading">
                  <div>
                    <h2>{names[model] || model} · confusion matrix</h2>
                    <p>Rows: reference labels · Columns: model predictions</p>
                  </div>
                </div>
                <div className="table-wrap">
                  <table className="confusion">
                    <thead>
                      <tr>
                        <th>Actual ↓ / Predicted →</th>
                        {classes.map((p) => (
                          <th key={p}>{p}</th>
                        ))}
                      </tr>
                    </thead>
                    <tbody>
                      {metrics.confusion_matrix.map((row, i) => (
                        <tr key={classes[i]}>
                          <th>{classes[i]}</th>
                          {row.map((n, j) => (
                            <td key={j} className={i === j ? "diagonal" : ""}>
                              {n.toLocaleString()}
                            </td>
                          ))}
                        </tr>
                      ))}
                    </tbody>
                  </table>
                </div>
              </section>
              <section className="panel">
                <div className="panel-heading">
                  <div>
                    <h2>Per-severity performance</h2>
                    <p>Rare classes can be obscured by overall accuracy</p>
                  </div>
                </div>
                <div className="table-wrap">
                  <table>
                    <thead>
                      <tr>
                        <th>Severity</th>
                        <th>Precision</th>
                        <th>Recall</th>
                        <th>F1</th>
                        <th>Test support</th>
                      </tr>
                    </thead>
                    <tbody>
                      {classes.map((p) => (
                        <tr key={p}>
                          <td>
                            {p} · {labels[p]}
                          </td>
                          <td>{metrics.per_class[p].precision.toFixed(3)}</td>
                          <td>{metrics.per_class[p].recall.toFixed(3)}</td>
                          <td>{metrics.per_class[p]["f1-score"].toFixed(3)}</td>
                          <td>{metrics.per_class[p].support}</td>
                        </tr>
                      ))}
                    </tbody>
                  </table>
                </div>
              </section>
            </div>
          )}
          <section className="panel system">
            <h2>Data provenance and split audit</h2>
            <div className="evaluation-audit">
              <div>
                <span>Repository</span>
                <a
                  href={run.data_source?.repository || "#"}
                  target="_blank"
                  rel="noreferrer"
                >
                  {run.data_source?.repository || "Custom dataset"}
                </a>
              </div>
              <div>
                <span>Commit</span>
                <code>{run.data_source?.revision || "Not applicable"}</code>
              </div>
              <div>
                <span>Collection</span>
                <strong>
                  {run.data_source?.collection || "User-provided data"}
                </strong>
              </div>
              <div>
                <span>Preparation</span>
                <strong>
                  {run.data_source?.downloaded_records?.toLocaleString() || "—"}{" "}
                  downloaded →{" "}
                  {run.data_source?.prepared_records?.toLocaleString() ||
                    Object.values(run.class_counts).reduce(
                      (a, b) => a + b,
                      0,
                    )}{" "}
                  prepared
                </strong>
              </div>
              <div>
                <span>Shared normalized templates</span>
                <strong>
                  {run.template_overlap_count} ·{" "}
                  {run.split_strategy === "grouped"
                    ? "groups kept separate"
                    : "row-split limitation"}
                </strong>
              </div>
              <div>
                <span>Exact message overlap</span>
                <strong>{run.exact_text_overlap_count}</strong>
              </div>
              <div>
                <span>Ensemble policy</span>
                <strong>{run.ensemble_policy}</strong>
              </div>
              <div>
                <span>Feature policy</span>
                <strong>{run.feature_representation}</strong>
              </div>
            </div>
            <div className="table-wrap">
              <table>
                <thead>
                  <tr>
                    <th>Severity</th>
                    <th>Total</th>
                    <th>Training</th>
                    <th>Testing</th>
                  </tr>
                </thead>
                <tbody>
                  {classes.map((p) => (
                    <tr key={p}>
                      <td>{p}</td>
                      <td>{run.class_counts[p] || 0}</td>
                      <td>{run.split_class_counts?.train?.[p] || 0}</td>
                      <td>{run.split_class_counts?.test?.[p] || 0}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          </section>
          {run.per_dataset_metrics && (
            <section className="panel system">
              <h2>Dataset breakdown · {names[model] || model}</h2>
              <div className="table-wrap">
                <table>
                  <thead>
                    <tr>
                      <th>Dataset</th>
                      <th>Prepared records</th>
                      <th>Test records</th>
                      <th>Accuracy</th>
                      <th>Macro F1 (all 5 classes)</th>
                    </tr>
                  </thead>
                  <tbody>
                    {Object.entries(run.per_dataset_metrics).map(
                      ([dataset, d]) => (
                        <tr key={dataset}>
                          <td>{dataset}</td>
                          <td>{run.dataset_counts[dataset]}</td>
                          <td>{d.support}</td>
                          <td>
                            {d.models?.[model]
                              ? percent(d.models[model].accuracy)
                              : "—"}
                          </td>
                          <td>
                            {d.models?.[model]?.macro_f1?.toFixed(3) ?? "—"}
                          </td>
                        </tr>
                      ),
                    )}
                  </tbody>
                </table>
              </div>
            </section>
          )}
        </>
      )}
    </>
  );
}
