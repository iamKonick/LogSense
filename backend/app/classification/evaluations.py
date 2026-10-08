"""Read evaluation artifacts independently of the currently deployed model."""

import json
from pathlib import Path


def list_evaluations(directory):
    root = Path(directory)
    runs = []
    if not root.is_dir():
        return runs
    for path in root.glob("*/report.json"):
        # Refuse symlinks outside the configured report directory.
        if not path.resolve().is_relative_to(root.resolve()):
            continue
        try:
            report = json.loads(path.read_text())
            if not isinstance(report, dict) or not isinstance(report.get("test_metrics"), dict):
                continue
            runs.append({"run_id": path.parent.name, **report})
        except (OSError, ValueError):
            continue
    return sorted(runs, key=lambda r: r.get("version", ""), reverse=True)
