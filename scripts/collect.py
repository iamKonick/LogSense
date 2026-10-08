"""Stream stdin or a local Loghub/text/JSONL/CSV file to LogSense."""

import argparse
import csv
import json
import os
import sys
import time
from contextlib import nullcontext
from pathlib import Path
from urllib.error import URLError
from urllib.request import Request, urlopen

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "backend"))
from app.ingestion.formats import csv_message, has_timestamp


def send(url, logs):
    request = Request(
        url.rstrip("/") + "/api/ingest",
        data=json.dumps({"logs": logs}).encode(),
        headers={
            "Content-Type": "application/json",
            "X-API-Key": os.getenv("LOGSENSE_API_KEY", ""),
        },
    )
    for attempt in range(5):
        try:
            with urlopen(request, timeout=30) as response:
                result = json.load(response)
                print(
                    f"Accepted {result['accepted']}; duplicates {result['duplicates']}",
                    file=sys.stderr,
                )
                return
        except URLError:
            if attempt == 4:
                raise
            time.sleep(2**attempt)


def main():
    from datetime import datetime, timezone

    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("file", nargs="?", default="-")
    parser.add_argument("--source", required=True)
    parser.add_argument("--service", default="unknown")
    parser.add_argument("--dataset", default="")
    parser.add_argument("--url", default="http://127.0.0.1:8010")
    parser.add_argument("--batch-size", type=int, default=100)
    args = parser.parse_args()
    if not 1 <= args.batch_size <= 1000:
        parser.error("batch size must be 1–1000")
    with (
        nullcontext(sys.stdin)
        if args.file == "-"
        else open(args.file, encoding="utf-8-sig") as stream
    ):
        lines = (
            (csv_message(row) for row in csv.DictReader(stream))
            if args.file.endswith(".csv")
            else stream
        )
        batch = []
        for line in lines:
            if not line.strip():
                continue
            # Stable across retries within this collector run, even without source timestamps.
            record = {
                "message": line.strip(),
                "source": args.source,
                "dataset": args.dataset,
                "service": args.service,
            }
            if not has_timestamp(line.strip()):
                record["timestamp"] = datetime.now(timezone.utc).isoformat()
            batch.append(record)
            if len(batch) >= args.batch_size:
                send(args.url, batch)
                batch = []
        if batch:
            send(args.url, batch)


if __name__ == "__main__":
    main()
