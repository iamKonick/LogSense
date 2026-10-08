"""Reproducible one-command Loghub preparation and 80/20 evaluation."""

import argparse
import sys
from datetime import datetime, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "experiments"))
from loghub import prepare
from train import train

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--data", default="data/loghub")
    parser.add_argument(
        "--output",
        default="experiments/runs/loghub-" + datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ"),
    )
    parser.add_argument("--seed", type=int, default=42)
    args = parser.parse_args()
    manifest = prepare(args.data)
    train(Path(args.data) / "labeled.csv", args.output, manifest["label_provenance"], args.seed)
