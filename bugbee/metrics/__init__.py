"""Metrics collection for BugBee.

The original script accumulated a dictionary ``metrics_obj`` and appended JSON
lines to ``metrics.jsonl``.  ``MetricsCollector`` provides a thin wrapper around
that behaviour, exposing methods to update sections and write a record.  All
timestamps are ISO‑8601 strings.
"""

from __future__ import annotations

import json
import time
from datetime import datetime
from pathlib import Path
from typing import Any, Dict

from bugbee.config.settings import settings

__all__ = ["MetricsCollector"]


class MetricsCollector:
    """Collect and persist metrics for a single run.

    Usage example::

        collector = MetricsCollector()
        collector.update("command", "python myscript.py")
        collector.update("retrieval", {"top_score": 0.9})
        collector.write()
    """

    def __init__(self, file_path: Path | None = None) -> None:
        self.file_path = file_path or Path.cwd() / "metrics.jsonl"
        self.metrics: Dict[str, Any] = {
            "timestamp": datetime.utcnow().isoformat(),
            "command": "",
            "exceptionType": "NA",
            "retrieval": {"top_score": 0.0, "avg_score": 0.0, "latency_ms": 0.0},
            "llm": {"input_tokens": 0, "output_tokens": 0, "latency_ms": 0.0},
            "diagnosis": {"error_line_found": False, "fix_generated": False},
            "autofix": {"patch_applied": False, "files_modified": 0},
            "validation": {"passed": False},
        }

    def update(self, key: str, value: Any) -> None:
        """Set *key* to *value* – creates nested dicts as needed."""
        parts = key.split(".")
        target = self.metrics
        for part in parts[:-1]:
            target = target.setdefault(part, {})
        target[parts[-1]] = value

    def write(self) -> None:
        """Append the current metrics as a JSON line to ``metrics.jsonl``."""
        self.file_path.parent.mkdir(parents=True, exist_ok=True)
        with self.file_path.open("a", encoding="utf-8") as f:
            f.write(json.dumps(self.metrics) + "\n")
