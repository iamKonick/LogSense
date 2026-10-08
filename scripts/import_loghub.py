"""Send a prepared Loghub partition through the same API as static/Docker logs."""

import argparse
import csv
import json
import os
from datetime import datetime, timedelta, timezone
from pathlib import Path
from urllib.request import Request, urlopen


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--data", default="data/loghub/labeled.csv")
    parser.add_argument("--run", required=True)
    parser.add_argument("--partition", choices=["train", "test", "all"], default="test")
    parser.add_argument("--url", default="http://127.0.0.1:8010")
    parser.add_argument("--limit", type=int)
    args = parser.parse_args()
    with Path(args.data).open(encoding="utf-8") as f:
        rows = list(csv.DictReader(f))
    run = Path(args.run)
    report = json.loads((run / "report.json").read_text())
    import hashlib

    if hashlib.sha256(Path(args.data).read_bytes()).hexdigest() != report["dataset_sha256"]:
        raise ValueError("Data file does not match the experiment hash")
    split = json.loads((run / "split-indices.json").read_text())
    indices = list(range(len(rows))) if args.partition == "all" else split[args.partition]
    if args.limit is not None:
        if args.limit < 1:
            raise ValueError("Limit must be positive")
        indices = indices[: args.limit]
    # Stable import identity makes rerunning this partition idempotent. This is
    # an import timestamp, not a claim to preserve historical event timestamps.
    base = (
        datetime.strptime(report["version"], "%Y%m%dT%H%M%SZ").replace(tzinfo=timezone.utc)
        if report.get("methodology") == "nested-selection-v2"
        else datetime.fromisoformat(report["data_source"]["downloaded_at"])
    )
    records = []
    for index in indices:
        row = rows[index]
        records.append(
            {
                "message": json.dumps({"message": row["message"], "level": row["source_level"]}),
                "source": "loghub",
                "dataset": row["dataset"],
                "service": row["dataset"],
                "timestamp": (base + timedelta(microseconds=index)).isoformat(),
                "reference_priority": row["priority"],
                "reference_provenance": f"Loghub source-level weak label; {args.partition} partition of {run.name}; timestamp represents import",
            }
        )
    receipts = []
    for start in range(0, len(records), 100):
        request = Request(
            args.url.rstrip("/") + "/api/ingest",
            data=json.dumps({"logs": records[start : start + 100]}).encode(),
            headers={
                "Content-Type": "application/json",
                "X-API-Key": os.getenv("LOGSENSE_API_KEY", ""),
            },
        )
        with urlopen(request, timeout=60) as response:
            result = json.load(response)
        receipts.extend(result["receipts"])
        print(
            f"Batch {start // 100 + 1}: {result['accepted']} accepted; {result['duplicates']} duplicates",
            flush=True,
        )
    (run / f"import-{args.partition}-receipts.json").write_text(json.dumps(receipts, indent=2))
    print(f"Queued {len(receipts)} records through the shared pipeline.")


if __name__ == "__main__":
    main()
