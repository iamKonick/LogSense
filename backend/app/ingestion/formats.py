"""Source-format helpers kept independent of the web and database layers."""

import json
import re

TIMESTAMP_PREFIX = re.compile(r"^\[?\d{4}-\d{2}-\d{2}[T ]\d{2}:\d{2}:\d{2}")


def csv_message(row):
    message = row.get("Content") or row.get("message") or row.get("Message")
    if not message or not message.strip():
        raise ValueError("CSV requires a nonempty Content or message column")
    payload = {"message": message}
    for target, candidates in {
        "level": ("Level", "level", "Severity"),
        "timestamp": ("timestamp", "Timestamp", "time"),
        "service": ("service", "Component"),
        "host": ("host", "Host"),
        "dataset": ("dataset", "Dataset"),
    }.items():
        value = next((row[k] for k in candidates if row.get(k)), None)
        if value:
            payload[target] = value
    return json.dumps(payload)


def has_timestamp(message):
    if TIMESTAMP_PREFIX.match(message):
        return True
    try:
        payload = json.loads(message)
        return isinstance(payload, dict) and bool(payload.get("timestamp") or payload.get("time"))
    except ValueError:
        return False
