// Resolve synchronously: a report can change before an effect would run.
export function modelForRun(run, selection) {
  const metrics = run?.test_metrics || {};
  if (selection?.runId === run?.run_id && metrics[selection?.model]) {
    return selection.model;
  }
  if (metrics[run?.selected_model]) return run.selected_model;
  if (metrics.ensemble) return "ensemble";
  return Object.keys(metrics)[0] || "";
}
