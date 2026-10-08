import test from "node:test";
import assert from "node:assert/strict";
import { readFileSync } from "node:fs";
import { modelForRun } from "../src/lib/evaluation.js";
const readRun = (id) => ({run_id:id, ...JSON.parse(readFileSync(new URL(`../../experiments/runs/${id}/report.json`, import.meta.url)))});
const current = readRun("loghub-grouped-selection");
const legacy = readRun("loghub-80-20");
function assertRenderable(run, selection) {
  const model = modelForRun(run, selection);
  assert.ok(run.test_metrics[model]);
  for (const dataset of Object.values(run.per_dataset_metrics)) {
    assert.ok(Number.isFinite(dataset.models[model].accuracy));
  }
  return model;
}
test("new report is renderable on its first render without the retired ensemble", () => {
  assert.equal(assertRenderable(current, null), "logistic_regression");
});
test("switching between legacy and selected-model reports never carries an invalid model", () => {
  assert.equal(assertRenderable(current, {runId:legacy.run_id,model:"ensemble"}), "logistic_regression");
  assert.equal(assertRenderable(legacy, {runId:current.run_id,model:"xgboost"}), "ensemble");
});
test("a valid user choice survives refresh while missing choices fall back", () => {
  assert.equal(assertRenderable(current, {runId:current.run_id,model:"stacking"}), "stacking");
  assert.equal(assertRenderable(current, {runId:current.run_id,model:"ensemble"}), "logistic_regression");
  assert.equal(modelForRun(undefined, null), "");
});
