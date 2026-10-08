from types import SimpleNamespace
from unittest.mock import Mock

import numpy as np
import pytest
from app.assistant.service import Assistant
from app.classification.predictor import Predictor, decide
from app.domain.models import RawLog
from app.ingestion.formats import csv_message, has_timestamp
from app.knowledge.embedding import embed
from app.preprocessing.parser import normalize, redact
from app.storage.repository import destination


def test_timestamp_normalization_and_retry_identity():
    a = normalize(RawLog(message="2026-09-30T12:00:00+02:00 ERROR refused", source="app"))
    b = normalize(RawLog(message="2026-09-30T10:00:00Z ERROR refused", source="app"))
    assert a.id == b.id
    assert a.timestamp == "2026-09-30T10:00:00+00:00"
    assert a.source_level == "ERROR"
    assert a.message == "ERROR refused"


def test_different_sources_and_occurrences_remain_distinct():
    a = normalize(RawLog(message="2026-09-30T10:00:00Z ERROR refused", source="a"))
    b = normalize(RawLog(message="2026-09-30T10:00:00Z ERROR refused", source="b"))
    c = normalize(RawLog(message="2026-09-30T10:00:01Z ERROR refused", source="a"))
    assert len({a.id, b.id, c.id}) == 3
    assert a.template == b.template == c.template


def test_json_docker_wrapper_and_redaction():
    a = normalize(
        RawLog(
            message='{"log":"ERROR token=secret-value connection refused","time":"2026-09-30T10:00:00Z","stream":"stderr"}'
        )
    )
    assert "secret-value" not in a.model_dump_json()
    assert a.source_level == "ERROR"
    assert not a.warnings
    assert "hunter2" not in redact('postgres://user:hunter2@db password="hunter2" Bearer hunter2')


def test_bad_json_is_retained_with_warning():
    event = normalize(RawLog(message="{broken json"))
    assert "Malformed JSON retained as plain text" in event.warnings


def test_empty_parsed_message_is_rejected():
    with pytest.raises(ValueError):
        normalize(RawLog(message='{"message":""}'))


@pytest.mark.parametrize(
    "level,priority,target",
    [
        ("DEBUG", "P1", "MongoDB"),
        ("INFO", "P2", "MongoDB"),
        ("WARNING", "P3", "MongoDB"),
        ("ERROR", "P4", "PostgreSQL"),
        ("CRITICAL", "P5", "PostgreSQL"),
    ],
)
def test_every_severity_has_exclusive_destination(level, priority, target):
    prediction = Predictor().predict(normalize(RawLog(message=f"{level} service event")))
    assert prediction.priority == priority
    assert prediction.confidence is None
    assert prediction.mode == "rule_fallback"
    assert destination(priority) == target


def test_invalid_routing_and_tie_policy():
    with pytest.raises(ValueError):
        destination("P0")
    assert decide({"P1": 0.1, "P2": 0.1, "P3": 0.2, "P4": 0.3, "P5": 0.3}) == "P5"


def test_missing_evidence_abstains_without_inventing_a_cause():
    repo = Mock()
    repo.retrieve.return_value = []
    response = Assistant(repo, SimpleNamespace(ollama_model="")).answer("Why did it fail?")
    assert response["sources"] == []
    assert "cannot be established" in response["answer"]
    assert response["confidence"] is None


def test_patterns_do_not_become_verified_resolutions():
    repo = Mock()
    repo.retrieve.return_value = [
        {
            "id": "one",
            "kind": "pattern",
            "verified": False,
            "score": 0.7,
            "title": "Timeout",
            "content": "Connection timeout",
            "source": "log:a",
        }
    ]
    response = Assistant(repo, SimpleNamespace(ollama_model="")).answer("Timeout")
    assert "[1]" in response["answer"]
    assert "cause remains unconfirmed" in response["answer"]
    assert not response["generated"]


def test_lexical_vectors_are_deterministic_and_normalized():
    vector = embed("database connection timeout")
    assert len(vector) == 384
    assert vector == embed("database connection timeout")
    assert np.linalg.norm(vector) == pytest.approx(1)


def test_csv_preserves_level_and_timestamp_metadata():
    message = csv_message(
        {
            "Content": "Connection failed",
            "Level": "CRITICAL",
            "Timestamp": "2026-09-30T11:00:00Z",
            "Component": "database",
        }
    )
    event = normalize(RawLog(message=message))
    assert event.source_level == "CRITICAL"
    assert event.service == "database"
    assert has_timestamp(message)
    assert event.timestamp == "2026-09-30T11:00:00+00:00"


def test_local_generation_failure_returns_cited_evidence(monkeypatch):
    import httpx

    repo = Mock()
    repo.retrieve.return_value = [
        {
            "id": "one",
            "kind": "runbook",
            "verified": False,
            "score": 0.7,
            "title": "Database",
            "content": "Check connection settings",
            "source": "runbook:db",
        }
    ]
    monkeypatch.setattr(httpx.Client, "post", Mock(side_effect=httpx.ConnectError("offline")))
    response = Assistant(
        repo,
        SimpleNamespace(ollama_model="local-test", ollama_url="http://localhost:11434"),
    ).answer("database connection")
    assert response["mode"] == "evidence_only"
    assert "[1]" in response["answer"]
    assert "unavailable" in response["notice"]


def test_failed_processing_has_bounded_retries():
    from app.ingestion.queue import Queue

    queue = Queue.__new__(Queue)
    queue.redis = Mock()
    queue.finish = Mock()
    queue.redis.incr.return_value = 4
    queue.fail("classification", "entry", "event", "{}")
    queue.redis.xadd.assert_not_called()
    queue.finish.assert_not_called()
    queue.redis.incr.return_value = 5
    queue.fail("classification", "entry", "event", "{}")
    queue.redis.xadd.assert_called_once()
    queue.finish.assert_called_once_with("classification", "entry", "event", "failed")


def test_knowledge_waits_for_persisted_classification():
    from app.worker import knowledge_ready

    repo, queue = Mock(), Mock()
    event = normalize(RawLog(message="INFO service started"))
    repo.event.return_value = None
    queue.status.return_value = {"classification": "queued"}
    assert not knowledge_ready(repo, queue, "entry", event)
    queue.finish.assert_not_called()
    queue.status.return_value = {"classification": "failed"}
    assert not knowledge_ready(repo, queue, "entry", event)
    queue.finish.assert_called_once_with("knowledge", "entry", event.id, "failed")
    repo.event.return_value = {"prediction": {"priority": "P2"}}
    assert knowledge_ready(repo, queue, "entry", event)
