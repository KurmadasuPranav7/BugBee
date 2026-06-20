"""Patch application utilities for BugBee.

The historic ``auto_code_fix.auto_fix`` function performed a line‑level replace
based on a *starting line* and a *search string* for the erroneous line.  The new
implementation adds safety features:

* Creates a timestamped backup before modifying the file.
* Returns the path of the backup for possible rollback.
* Raises ``FileNotFoundError`` if the target does not exist.
"""

from __future__ import annotations

import shutil
import time
from pathlib import Path
from typing import Optional

__all__ = ["apply_patch"]


def _backup_file(original: Path) -> Path:
    """Create a backup ``<original>.bak.<timestamp>`` and return its path."""
    timestamp = time.strftime("%Y%m%d%H%M%S")
    backup_path = original.with_name(f"{original.name}.bak.{timestamp}")
    shutil.copy2(original, backup_path)
    return backup_path


def apply_patch(
    file_path: Path,
    line_number: int,
    error_line: str,
    fixed_line: str,
    *,
    create_backup: bool = True,
) -> bool:
    """Replace *error_line* with *fixed_line* around *line_number* in *file_path*.

    The function reads the file, searches backwards from ``line_number`` for a
    line containing ``error_line`` (mirroring the original behaviour), replaces
    that line, writes the file back, and optionally creates a backup before the
    modification.

    Returns ``True`` if a replacement was made, ``False`` otherwise.
    """
    if not file_path.is_file():
        raise FileNotFoundError(str(file_path))

    if create_backup:
        _backup_file(file_path)

    lines = file_path.read_text(encoding="utf-8").splitlines(keepends=True)
    start_idx = max(0, line_number - 1)  # zero‑based index
    # Search backwards up to 30 lines as in the original script.
    for idx in range(start_idx, max(-1, start_idx - 31), -1):
        if error_line in lines[idx]:
            lines[idx] = fixed_line
            file_path.write_text("".join(lines), encoding="utf-8")
            return True
    return False
