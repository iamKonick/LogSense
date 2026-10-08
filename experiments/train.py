"""Select a severity pipeline with nested training-only CV, then evaluate once."""

import argparse
import csv
import hashlib
import json
import platform
import sys
import time
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "backend"))
import joblib
import numpy as np
import sklearn
from app.classification.estimators import SeverityXGBoost
from app.classification.predictor import decide
from app.domain.models import PRIORITIES
from app.preprocessing.parser import redact, template
from sklearn.base import clone
from sklearn.ensemble import RandomForestClassifier, StackingClassifier
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.linear_model import LogisticRegression
from sklearn.metrics import (
    accuracy_score,
    classification_report,
    confusion_matrix,
    f1_score,
    matthews_corrcoef,
)
from sklearn.model_selection import StratifiedGroupKFold, StratifiedKFold, train_test_split
from sklearn.naive_bayes import ComplementNB
from sklearn.pipeline import make_pipeline
from sklearn.svm import SVC


def report(y, pred):
    return {
        "accuracy": accuracy_score(y, pred),
        "macro_f1": f1_score(y, pred, labels=PRIORITIES, average="macro", zero_division=0),
        "weighted_f1": f1_score(y, pred, average="weighted", zero_division=0),
        "mcc": matthews_corrcoef(y, pred),
        "per_class": classification_report(
            y, pred, labels=PRIORITIES, output_dict=True, zero_division=0
        ),
        "confusion_matrix": confusion_matrix(y, pred, labels=PRIORITIES).tolist(),
    }


def split_data(messages, labels, groups, seed, strategy="stratified"):
    indices = np.arange(len(messages))
    if strategy == "grouped":
        train, test = next(
            StratifiedGroupKFold(n_splits=5, shuffle=True, random_state=seed).split(
                messages, labels, groups
            )
        )
        assert not set(groups[train]) & set(groups[test])
    elif strategy == "stratified":
        train, test = train_test_split(indices, test_size=0.2, stratify=labels, random_state=seed)
    else:
        raise ValueError("Unknown split strategy")
    for name, ids in [("train", train), ("test", test)]:
        if set(labels[ids]) != set(PRIORITIES):
            raise ValueError(f"{name} lacks a severity class; provide more labeled examples")
    return train, test


def train(csv_path, output, label_provenance, seed=42, split_strategy="grouped"):
    if Path(output).exists():
        raise ValueError("Output run already exists; use a new directory")
    started = time.monotonic()
    with Path(csv_path).open(encoding="utf-8-sig") as stream:
        rows = list(csv.DictReader(stream))
    if not rows or not {"message", "priority"}.issubset(rows[0]):
        raise ValueError("CSV requires message and priority columns, with optional group column")
    if any(r["priority"] not in PRIORITIES or not r["message"].strip() for r in rows):
        raise ValueError("Every row needs a nonempty message and a P1–P5 priority")
    messages = np.array([redact(r["message"]) for r in rows])
    labels = np.array([r["priority"] for r in rows])
    groups = np.array([r.get("group") or template(m).lower() for r, m in zip(rows, messages)])
    # User groups may be broader than a template, but must never divide a template.
    template_groups = {}
    for message, group in zip(messages, groups):
        key = template(message).lower()
        if key in template_groups and template_groups[key] != group:
            raise ValueError("The same normalized template appears in multiple user groups")
        template_groups[key] = group
    train_ids, test_ids = split_data(messages, labels, groups, seed, split_strategy)
    X, y = messages[train_ids], labels[train_ids]

    def folds_for(text, target, grouping):
        splitter = (StratifiedGroupKFold if split_strategy == "grouped" else StratifiedKFold)(
            n_splits=3, shuffle=True, random_state=seed
        )
        folds = list(
            splitter.split(text, target, grouping)
            if split_strategy == "grouped"
            else splitter.split(text, target)
        )
        for fit, validation in folds:
            if set(target[fit]) != set(PRIORITIES):
                raise ValueError(
                    "A CV fitting fold lacks a class; provide more independent labeled groups"
                )
            if split_strategy == "grouped":
                assert not set(grouping[fit]) & set(grouping[validation])
        return folds

    estimators = [
        (
            "random_forest",
            RandomForestClassifier(
                n_estimators=160, class_weight="balanced", random_state=seed, n_jobs=1
            ),
        ),
        (
            "logistic_regression",
            LogisticRegression(max_iter=1500, class_weight="balanced", random_state=seed),
        ),
        ("svm", SVC(kernel="linear", probability=True, class_weight="balanced", random_state=seed)),
        ("naive_bayes", ComplementNB(alpha=0.5)),
        ("xgboost", SeverityXGBoost(random_state=seed)),
    ]
    pipelines = [
        (
            name,
            make_pipeline(
                TfidfVectorizer(ngram_range=(1, 2), max_features=30000, sublinear_tf=True),
                estimator,
            ),
        )
        for name, estimator in estimators
    ]
    names = [name for name, _ in pipelines] + ["soft_voting", "stacking"]

    def fit_stack(text, target, grouping):
        folds = folds_for(text, target, grouping)
        stack = StackingClassifier(
            estimators=pipelines,
            final_estimator=LogisticRegression(max_iter=1500, random_state=seed),
            cv=folds,
            stack_method="predict_proba",
            passthrough=False,
            n_jobs=1,
        )
        stack.fit(text, target)
        return stack, folds

    def predictions(stack, text):
        # Internal base classifiers use encoded 0..4 labels in public P1..P5 order.
        base = {
            name: estimator.predict_proba(text)
            for (name, _), estimator in zip(pipelines, stack.estimators_)
        }
        return base | {
            "soft_voting": np.mean(list(base.values()), axis=0),
            "stacking": stack.predict_proba(text),
        }

    outer_folds = folds_for(X, y, groups[train_ids])
    validation_probabilities = {name: np.zeros((len(X), len(PRIORITIES))) for name in names}
    fold_audit = []
    print("Training-only model selection: 3 outer folds, 3 inner stacking folds", flush=True)
    for number, (fit, validation) in enumerate(outer_folds, 1):
        print(f"Outer fold {number}/3: fit {len(fit)}, validation {len(validation)}", flush=True)
        stack, inner = fit_stack(X[fit], y[fit], groups[train_ids][fit])
        for name, values in predictions(stack, X[validation]).items():
            validation_probabilities[name][validation] = values
        fold_audit.append(
            {
                "fit": train_ids[fit].tolist(),
                "validation": train_ids[validation].tolist(),
                "stacking_inner_folds": [
                    {"fit": train_ids[fit[a]].tolist(), "validation": train_ids[fit[b]].tolist()}
                    for a, b in inner
                ],
            }
        )
    validation_metrics = {
        name: report(y, [decide(dict(zip(PRIORITIES, row))) for row in values])
        for name, values in validation_probabilities.items()
    }
    # Deterministic predefined tie-break: macro F1, then mean P4/P5 recall, then candidate order.
    selected = max(
        names,
        key=lambda name: (
            validation_metrics[name]["macro_f1"],
            np.mean([validation_metrics[name]["per_class"][p]["recall"] for p in ("P4", "P5")]),
            -names.index(name),
        ),
    )
    print(
        f"Selected from training CV: {selected}. Refitting on all {len(X)} training records.",
        flush=True,
    )
    stacking, final_folds = fit_stack(X, y, groups[train_ids])
    # Public-label standalone copies preserve inspectable outputs for all candidates.
    models = {name: clone(pipeline).fit(X, y) for name, pipeline in pipelines}
    print("Selection frozen. Evaluating held-out test partition once.", flush=True)
    all_probabilities = predictions(stacking, messages[test_ids])
    metrics = {
        name: report(labels[test_ids], [decide(dict(zip(PRIORITIES, row))) for row in probs])
        for name, probs in all_probabilities.items()
    }
    version = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    metadata = {
        "version": version,
        "seed": seed,
        "label_provenance": label_provenance,
        "dataset_sha256": hashlib.sha256(Path(csv_path).read_bytes()).hexdigest(),
        "class_counts": dict(Counter(labels)),
        "classes": PRIORITIES,
        "split_counts": {
            "train": len(train_ids),
            "test": len(test_ids),
        },
        "split_strategy": split_strategy,
        "split_description": "80/20 stratified train/test split"
        if split_strategy == "stratified"
        else "Approximately 80/20 stratified template-group split",
        "train_fraction": len(train_ids) / len(rows),
        "test_fraction": len(test_ids) / len(rows),
        "split_class_counts": {
            "train": dict(Counter(labels[train_ids])),
            "test": dict(Counter(labels[test_ids])),
        },
        "template_overlap_count": len(set(groups[train_ids]) & set(groups[test_ids])),
        "exact_text_overlap_count": len(set(messages[train_ids]) & set(messages[test_ids])),
        "interpretation": "Scores measure agreement with source-level weak labels. Template groups are separated when grouped splitting is selected; this is not an unseen-source test. This corpus has been examined in prior experiments, so a new external dataset is needed for confirmatory research.",
        "stacking": "3-fold OOF within each outer training fold; fold-local TF-IDF; 25 probability meta-features; Logistic Regression meta-learner",
        "selected_model": selected,
        "selection_metric": "macro_f1",
        "selection_policy": "Training-only 3-fold outer CV; ties use mean P4/P5 recall then fixed candidate order",
        "validation_metrics": validation_metrics,
        "meta_feature_count": 25,
        "candidate_order": names,
        "methodology": "nested-selection-v2",
        "ensemble_policy": "Deploy the selected individual, soft-voting or stacking candidate; no fixed blend",
        "test_metrics": metrics,
        "training_seconds": time.monotonic() - started,
        "sklearn_version": sklearn.__version__,
        "python_version": platform.python_version(),
        "feature_representation": "text TF-IDF 1–2 grams; source metadata excluded",
        "confidence_calibrated": False,
        "hyperparameters": {name: str(pipeline.get_params()) for name, pipeline in pipelines},
    }
    manifest_path = Path(csv_path).with_name("manifest.json")
    if manifest_path.exists():
        metadata["data_source"] = json.loads(manifest_path.read_text())
    metadata["dataset_counts"] = dict(Counter(r.get("dataset") or "custom" for r in rows))
    test_datasets = np.array([rows[i].get("dataset") or "custom" for i in test_ids])
    metadata["per_dataset_metrics"] = {
        dataset: {
            "support": int(np.sum(test_datasets == dataset)),
            "models": {
                name: report(
                    labels[test_ids][test_datasets == dataset],
                    [decide(dict(zip(PRIORITIES, row))) for row in probs[test_datasets == dataset]],
                )
                for name, probs in all_probabilities.items()
            },
        }
        for dataset in sorted(set(test_datasets))
    }
    output = Path(output)
    output.mkdir(parents=True, exist_ok=False)
    joblib.dump(
        {
            "format": "logsense-v2",
            "metadata": metadata,
            "models": models,
            "stacking": stacking,
        },
        output / "model.joblib",
    )
    (output / "report.json").write_text(json.dumps(metadata, indent=2))
    (output / "split-indices.json").write_text(
        json.dumps(
            {
                "train": train_ids.tolist(),
                "test": test_ids.tolist(),
                "outer_cv": fold_audit,
                "final_stacking_folds": [
                    {"fit": train_ids[a].tolist(), "validation": train_ids[b].tolist()}
                    for a, b in final_folds
                ],
            }
        )
    )
    print(
        json.dumps(
            {
                "output": str(output),
                "selected_model": selected,
                "test_macro_f1": metrics[selected]["macro_f1"],
                "label_provenance": label_provenance,
            },
            indent=2,
        )
    )


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("csv")
    parser.add_argument("--output", required=True)
    parser.add_argument("--label-provenance", required=True)
    parser.add_argument("--seed", type=int, default=42)
    parser.add_argument("--split-strategy", choices=["stratified", "grouped"], default="grouped")
    args = parser.parse_args()
    train(args.csv, args.output, args.label_provenance, args.seed, args.split_strategy)
