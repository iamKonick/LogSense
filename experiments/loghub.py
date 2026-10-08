"""Fetch official Loghub 2k structured samples at a pinned Git commit."""

import argparse
import csv
import hashlib
import io
import json
import re
import sys
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path
from urllib.request import Request, urlopen

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "backend"))
from app.preprocessing.parser import redact, template

REPOSITORY = "https://github.com/logpai/loghub"
REVISION = "dd61d0952749ee7963bde24220d1be5ede023033"
DATASETS = [
    "Android",
    "Apache",
    "BGL",
    "HDFS",
    "HPC",
    "Hadoop",
    "HealthApp",
    "Linux",
    "Mac",
    "OpenSSH",
    "OpenStack",
    "Proxifier",
    "Spark",
    "Thunderbird",
    "Windows",
    "Zookeeper",
]
LEVEL_MAP = {
    "TRACE": "P1",
    "VERBOSE": "P1",
    "DEBUG": "P1",
    "V": "P1",
    "D": "P1",
    "INFO": "P2",
    "INFORMATION": "P2",
    "NOTICE": "P2",
    "I": "P2",
    "WARN": "P3",
    "WARNING": "P3",
    "W": "P3",
    "ERROR": "P4",
    "ERR": "P4",
    "E": "P4",
    "FATAL": "P5",
    "CRITICAL": "P5",
    "CRIT": "P5",
    "EMERG": "P5",
    "EMERGENCY": "P5",
    "ALERT": "P5",
    "F": "P5",
}


def fetch(url):
    with urlopen(
        Request(url, headers={"User-Agent": "LogSense-research/0.2"}), timeout=60
    ) as response:
        return response.read()


def prepare(output, revision=REVISION, datasets=None):
    if not re.fullmatch(r"[0-9a-f]{40}", revision):
        raise ValueError("Use a complete Git commit SHA for reproducibility")
    output = Path(output)
    output.mkdir(parents=True, exist_ok=True)
    candidates = []
    provenance = []
    for dataset in datasets or DATASETS:
        if dataset not in DATASETS:
            raise ValueError("Unsupported dataset name")
        path = f"{dataset}/{dataset}_2k.log_structured.csv"
        url = f"https://raw.githubusercontent.com/logpai/loghub/{revision}/{path}"
        cache = output / "raw" / revision / path
        cache.parent.mkdir(parents=True, exist_ok=True)
        if cache.exists():
            data = cache.read_bytes()
        else:
            data = fetch(url)
            cache.write_bytes(data)
        records = list(csv.DictReader(io.StringIO(data.decode("utf-8-sig"))))
        levels = Counter()
        selected = 0
        for row in records:
            level = (row.get("Level") or row.get("level") or "").strip().upper()
            levels[level or "(missing)"] += 1
            priority = LEVEL_MAP.get(level)
            content = redact((row.get("Content") or "").strip())
            if priority and content:
                candidates.append(
                    {
                        "message": content,
                        "priority": priority,
                        "dataset": dataset,
                        "source": "loghub",
                        "source_level": level,
                        "line_id": row.get("LineId", ""),
                        "template": template(content).lower(),
                    }
                )
                selected += 1
        provenance.append(
            {
                "dataset": dataset,
                "url": url,
                "sha256": hashlib.sha256(data).hexdigest(),
                "downloaded_records": len(records),
                "eligible_records": selected,
                "source_levels": dict(levels),
            }
        )
        print(
            f"{dataset}: {len(records)} records; {selected} with a recognized source level",
            flush=True,
        )
    # Eliminate exact text duplicates before row splitting; conflicting weak labels
    # are excluded instead of arbitrarily choosing a target for identical text.
    labels_by_text = {}
    for row in candidates:
        labels_by_text.setdefault(row["message"].casefold(), set()).add(row["priority"])
    conflicts = {text for text, labels in labels_by_text.items() if len(labels) > 1}
    seen = set()
    rows = []
    for row in candidates:
        key = row["message"].casefold()
        if key in seen or key in conflicts:
            continue
        seen.add(key)
        rows.append(row)
    if {row["priority"] for row in rows} != {"P1", "P2", "P3", "P4", "P5"}:
        raise ValueError("Selected datasets do not cover all five priorities")
    csv_path = output / "labeled.csv"
    with csv_path.open("w", newline="", encoding="utf-8") as stream:
        writer = csv.DictWriter(stream, fieldnames=list(rows[0]))
        writer.writeheader()
        writer.writerows(rows)
    manifest = {
        "repository": REPOSITORY,
        "revision": revision,
        "downloaded_at": datetime.now(timezone.utc).isoformat(),
        "collection": "Official 2,000-line structured samples, not the full Loghub archives",
        "label_provenance": "Weak labels: source Level mapped to project P1–P5. Not human-verified incident severity or Loghub ground-truth P1–P5 labels.",
        "mapping": LEVEL_MAP,
        "datasets": provenance,
        "downloaded_records": sum(r["downloaded_records"] for r in provenance),
        "eligible_records": len(candidates),
        "prepared_records": len(rows),
        "conflicting_texts_excluded": len(conflicts),
        "duplicates_or_conflicting_rows_excluded": len(candidates) - len(rows),
        "class_counts": dict(Counter(row["priority"] for row in rows)),
        "dataset_counts": dict(Counter(row["dataset"] for row in rows)),
        "labeled_sha256": hashlib.sha256(csv_path.read_bytes()).hexdigest(),
        "feature_policy": "Content only. Level, dataset, EventId and EventTemplate are excluded from model input.",
        "citation": "Zhu et al., Loghub: A Large Collection of System Log Datasets for AI-driven Log Analytics, ISSRE 2023.",
    }
    (output / "manifest.json").write_text(json.dumps(manifest, indent=2))
    print(
        json.dumps(
            {"prepared_records": len(rows), "class_counts": manifest["class_counts"]}, indent=2
        )
    )
    return manifest


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", default="data/loghub")
    parser.add_argument("--revision", default=REVISION)
    parser.add_argument("--datasets", nargs="+", choices=DATASETS)
    args = parser.parse_args()
    prepare(args.output, args.revision, args.datasets)
