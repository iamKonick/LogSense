from datetime import datetime, timezone
from typing import Literal

from pydantic import BaseModel, Field, field_validator

Priority = Literal["P1", "P2", "P3", "P4", "P5"]
PRIORITIES = ["P1", "P2", "P3", "P4", "P5"]


def now() -> str:
    return datetime.now(timezone.utc).isoformat()


class RawLog(BaseModel):
    message: str = Field(min_length=1, max_length=16000)
    source: str = Field(default="manual", min_length=1, max_length=200)
    dataset: str = Field(default="", max_length=100)
    service: str = Field(default="unknown", min_length=1, max_length=100)
    host: str = Field(default="unknown", min_length=1, max_length=100)
    reference_priority: Priority | None = None
    reference_provenance: str = Field(default="", max_length=500)
    timestamp: datetime | None = None

    @field_validator("message")
    @classmethod
    def not_blank(cls, value):
        if not value.strip():
            raise ValueError("Message must contain text")
        return value


class Batch(BaseModel):
    logs: list[RawLog] = Field(min_length=1, max_length=1000)


class Event(BaseModel):
    id: str
    message: str
    template: str
    source: str
    dataset: str = ""
    service: str
    host: str
    timestamp: str
    received_at: str
    source_level: str | None = None
    reference_priority: Priority | None = None
    reference_provenance: str = ""
    warnings: list[str] = Field(default_factory=list)


class Prediction(BaseModel):
    priority: Priority
    mode: str
    confidence: float | None = None
    individual: dict[str, dict] = Field(default_factory=dict)
    voting: dict[str, float] = Field(default_factory=dict)
    stacking: dict[str, float] = Field(default_factory=dict)
    probabilities: dict[str, float] = Field(default_factory=dict)
    needs_review: bool = False
    model_version: str = "rules-v1"


class Question(BaseModel):
    provider: Literal["openai", "ollama", "evidence"] | None = None
    model: str | None = Field(default=None, min_length=1, max_length=120, pattern=r"^[a-zA-Z0-9_.:/-]+$")
    question: str = Field(min_length=3, max_length=8000)
    event_id: str | None = Field(default=None, max_length=64)


class KnowledgeInput(BaseModel):
    title: str = Field(min_length=3, max_length=200)
    content: str = Field(min_length=10, max_length=20000)
    source: str = Field(min_length=1, max_length=500)
    kind: Literal["runbook", "troubleshooting", "root_cause"] = "runbook"


class IncidentUpdate(BaseModel):
    status: Literal["investigating", "resolved"]
    note: str = Field(min_length=3, max_length=4000)
    root_cause: str = Field(default="", max_length=2000)
    resolution: str = Field(default="", max_length=4000)
    actor: str = Field(min_length=1, max_length=100)

    @field_validator("actor", "note")
    @classmethod
    def nonempty(cls, value):
        if not value.strip():
            raise ValueError("Cannot be blank")
        return value.strip()
