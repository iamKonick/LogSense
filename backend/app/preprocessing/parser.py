"""Normalize JSON/plain logs. Keep event identity separate from pattern identity."""

import hashlib
import json
import re
from datetime import datetime, timezone

from app.domain.models import Event, RawLog, now

LEVEL = re.compile(
    r"\b(TRACE|DEBUG|INFO|INFORMATION|NOTICE|WARN|WARNING|ERROR|ERR|CRITICAL|FATAL|EMERG|ALERT)\b",
    re.IGNORECASE,
)
ISO = re.compile(
    r"^\[?(\d{4}-\d{2}-\d{2}[T ]\d{2}:\d{2}:\d{2}(?:\.\d+)?(?:Z|[+-]\d{2}:?\d{2})?)\]?\s*"
)


def redact(text: str) -> str:
    text = re.sub(r"(?i)(bearer\s+)[\w.\-]+", r"\1[REDACTED]", text)
    text = re.sub(
        r"""(?i)(["']?(?:password|passwd|token|api[_-]?key|secret)["']?\s*[:=]\s*)(?:"[^"]*"|'[^']*'|[^\s,;]+)""",
        r"\1[REDACTED]",
        text,
    )
    return re.sub(r"(://[^:/\s]+:)[^@\s]+@", r"\1[REDACTED]@", text)


def template(text: str) -> str:
    text = re.sub(r"\b[0-9a-f]{8}-[0-9a-f-]{27,}\b", "<id>", text, flags=re.IGNORECASE)
    text = re.sub(r"\b(?:\d{1,3}\.){3}\d{1,3}\b", "<ip>", text)
    text = re.sub(r"\b(?:0x[0-9a-f]+|\d+(?:\.\d+)?)\b", "<n>", text, flags=re.IGNORECASE)
    return re.sub(r"\s+", " ", text).strip()


def normalize(raw: RawLog) -> Event:
    received = now()
    message = raw.message.strip()
    source, service, host = (redact(v) for v in (raw.source, raw.service, raw.host))
    dataset = redact(raw.dataset)
    timestamp = raw.timestamp
    level, warnings = None, []
    if message.startswith("{"):
        try:
            body = json.loads(message)
            if not isinstance(body, dict):
                raise TypeError("JSON record must be an object")
            message = str(body.get("message", body.get("msg", body.get("log", message)))).strip()
            service = redact(str(body.get("service", service)))[:100]
            dataset = redact(str(body.get("dataset", dataset)))[:100]
            host = redact(str(body.get("host", host)))[:100]
            candidate = str(body.get("level", body.get("severity", ""))).upper()
            level = candidate if LEVEL.fullmatch(candidate) else None
            if timestamp is None and (body.get("timestamp") or body.get("time")):
                try:
                    timestamp = datetime.fromisoformat(
                        str(body.get("timestamp") or body["time"]).replace("Z", "+00:00")
                    )
                except ValueError:
                    warnings.append("Invalid embedded timestamp; using receipt time")
        except (ValueError, TypeError):
            warnings.append("Malformed JSON retained as plain text")
    match = ISO.match(message)
    if match:
        if timestamp is None:
            try:
                timestamp = datetime.fromisoformat(match[1].replace("Z", "+00:00"))
            except ValueError:
                warnings.append("Invalid text timestamp; using receipt time")
        message = message[match.end() :]
    if timestamp is None:
        timestamp = datetime.fromisoformat(received)
        warnings.append("Missing timestamp; using receipt time")
    if timestamp.tzinfo is None:
        timestamp = timestamp.replace(tzinfo=timezone.utc)
        warnings.append("Timestamp has no timezone; assumed UTC")
    timestamp_text = timestamp.astimezone(timezone.utc).isoformat()
    match = LEVEL.search(message)
    level = level or (match[1].upper() if match else None)
    message = redact(message)
    if not message.strip():
        raise ValueError("Log message is empty after parsing")
    identity = json.dumps(
        [source, service, host, timestamp_text, message, level], ensure_ascii=False
    )
    if dataset:
        identity += "\n" + dataset
    return Event(
        id=hashlib.sha256(identity.encode()).hexdigest(),
        message=message,
        template=template(message),
        source=source,
        dataset=dataset,
        service=service,
        host=host,
        timestamp=timestamp_text,
        received_at=received,
        source_level=level,
        reference_priority=raw.reference_priority,
        reference_provenance=redact(raw.reference_provenance),
        warnings=warnings,
    )
