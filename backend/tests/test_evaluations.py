import json

from app.classification.evaluations import list_evaluations
from app.domain.models import RawLog
from app.preprocessing.parser import normalize


def test_evaluation_reports_are_independent_and_reject_invalid_files(tmp_path):
    valid = tmp_path / "completed"
    valid.mkdir()
    (valid / "report.json").write_text(json.dumps({"test_metrics": {}, "version": "v1"}))
    invalid = tmp_path / "broken"
    invalid.mkdir()
    (invalid / "report.json").write_text("{")
    assert [r["run_id"] for r in list_evaluations(tmp_path)] == ["completed"]
    assert list_evaluations(tmp_path / "missing") == []


def test_dataset_identity_and_separate_reference_label():
    data = {
        "message": '{"message":"Service started", "level":"INFO"}',
        "timestamp": "2026-10-01T00:00:00Z",
    }
    a = normalize(RawLog(**data, dataset="A", reference_priority="P4"))
    b = normalize(RawLog(**data, dataset="B"))
    assert a.id != b.id
    assert a.message == b.message == "Service started"
    assert a.source_level == "INFO"
    assert a.reference_priority == "P4"
