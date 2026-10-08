import csv
import json
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent))
from app.classification.predictor import Predictor
from app.domain.models import PRIORITIES, RawLog
from app.preprocessing.parser import normalize
from train import train


def test_training_bundle_serves_public_labels_and_disjoint_splits(tmp_path):
    source = tmp_path / "fixture.csv"
    with source.open("w") as f:
        writer = csv.writer(f)
        writer.writerow(["message", "priority"])
        for p, text in zip(
            PRIORITIES,
            [
                "debug trace",
                "information successful",
                "warning degraded",
                "error refused",
                "critical panic",
            ],
        ):
            for word in [
                "alpha",
                "beta",
                "gamma",
                "delta",
                "epsilon",
                "zeta",
                "eta",
                "theta",
                "iota",
                "kappa",
                "lambda",
                "mu",
            ]:
                for verb in ["reading", "writing", "opening", "checking", "loading"]:
                    writer.writerow([f"{text} {word} {verb}", p])
    output = tmp_path / "run"
    train(
        source,
        output,
        "Synthetic software fixture; not research evidence",
        split_strategy="grouped",
    )
    predictor = Predictor(str(output / "model.joblib"))
    prediction = predictor.predict(normalize(RawLog(message="critical panic alpha reading")))
    assert prediction.mode == "trained_selected"
    assert len(prediction.individual) == 5
    assert set(prediction.voting) == set(prediction.stacking) == set(PRIORITIES)
    assert sum(prediction.probabilities.values()) == pytest.approx(1)
    assert prediction.priority == "P5"
    splits = json.loads((output / "split-indices.json").read_text())
    assert not set(splits["train"]) & set(splits["test"])
    assert len(splits["train"]) + len(splits["test"]) == 300
    report = json.loads((output / "report.json").read_text())
    assert report["split_strategy"] == "grouped"
    assert "voting_weight" not in report
    assert report["template_overlap_count"] == 0
    assert report["meta_feature_count"] == 25
    assert len(report["validation_metrics"]) == 7
    assert predictor.bundle["stacking"].final_estimator_.n_features_in_ == 25
    expected = max(
        report["candidate_order"],
        key=lambda n: (
            report["validation_metrics"][n]["macro_f1"],
            sum(report["validation_metrics"][n]["per_class"][p]["recall"] for p in ("P4", "P5"))
            / 2,
            -report["candidate_order"].index(n),
        ),
    )
    assert report["selected_model"] == expected
    options = {n: v["probabilities"] for n, v in prediction.individual.items()} | {
        "soft_voting": prediction.voting,
        "stacking": prediction.stacking,
    }
    assert prediction.probabilities == options[expected]
    train_set, test_set = set(splits["train"]), set(splits["test"])
    validation_seen = []
    for fold in splits["outer_cv"]:
        fit, val = set(fold["fit"]), set(fold["validation"])
        assert not fit & val
        assert fit | val == train_set
        assert not (fit | val) & test_set
        validation_seen.extend(fold["validation"])
        for inner in fold["stacking_inner_folds"]:
            assert not set(inner["fit"]) & set(inner["validation"])
            assert set(inner["fit"]) | set(inner["validation"]) == fit
    assert sorted(validation_seen) == sorted(train_set)

    for source, level in [("loghub", "INFO"), ("static", "DEBUG"), ("docker", "ERROR")]:
        event = normalize(
            RawLog(
                message=json.dumps({"message": "critical panic alpha reading", "level": level}),
                source=source,
                reference_priority="P1",
            )
        )
        result = predictor.predict(event)
        assert result.probabilities == prediction.probabilities
        assert event.reference_priority == "P1"
