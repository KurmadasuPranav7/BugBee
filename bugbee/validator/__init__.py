"""Validation utilities for BugBee.

After applying an automatic patch the original tool re‑ran the failing command to
ensure the issue is resolved.  ``run_validation`` mirrors that behaviour: it
executes the supplied command and returns ``True`` when the exit code is ``0``.
"""

from __future__ import annotations

import subprocess
from pathlib import Path
from typing import List

__all__ = ["run_validation"]


def run_validation(command: List[str], cwd: Path | None = None) -> bool:
    """Execute *command* and return ``True`` if it finishes with exit code ``0``.

    ``cwd`` defaults to the current working directory.  Standard output and
    error streams are captured but not displayed; callers can log them if they
    wish.
    """
    result = subprocess.run(
        command,
        cwd=cwd,
        capture_output=True,
        text=True,
    )
    return result.returncode == 0
