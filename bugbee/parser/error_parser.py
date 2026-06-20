"""Error‑parsing utilities for BugBee.

The original script performed a handful of regex‑based operations to:

1. Extract the file and line number from a stack‑trace.
2. Sanitize an error string for stable hashing.
3. Compute a SHA‑256 hash of the sanitized error.

These helpers are now grouped in a dedicated module so they can be reused by the
CLI and any future programmatic API.
"""

from __future__ import annotations

import hashlib
import os
import re
from pathlib import Path
from typing import Optional, Tuple

__all__ = [
    "extract_location",
    "sanitize_error",
    "error_hash",
]


def extract_location(stderr: str, command: list[str]) -> Tuple[Optional[Path], Optional[int]]:
    """Return the source file path and line number for the *first* stack entry.

    The function mirrors the logic that existed in ``main.py`` for the supported
    languages (Python, C, C++, Go, JavaScript, generic build tools).  It returns
    ``(None, None)`` when no location can be determined.
    """
    file_under_execution = command[-1] if command else ""
    line_number: Optional[int] = None
    path: Optional[Path] = None

    # Python stack trace
    if file_under_execution.endswith(".py"):
        match = re.search(r'File "([^\"]+)", line (\d+)', stderr)
        if match:
            path = Path(match.group(1))
            line_number = int(match.group(2))

    # C source (main.c)
    elif file_under_execution.endswith(".c"):
        match = re.search(r"main\.c:(\d+):\d+:", stderr)
        if match:
            path = Path(os.getcwd()) / file_under_execution
            line_number = int(match.group(1))

    # C++ source (main.cpp)
    elif file_under_execution.endswith(".cpp"):
        match = re.search(r"main\.cpp:(\d+):\d+:", stderr)
        if match:
            path = Path(os.getcwd()) / file_under_execution
            line_number = int(match.group(1))

    # Go source (main.go)
    elif file_under_execution.endswith(".go"):
        match = re.search(r"main\.go:(\d+):\d+:", stderr)
        if match:
            path = Path(os.getcwd()) / file_under_execution
            line_number = int(match.group(1))

    # JavaScript (Node) – try to pull the line from a V8 stack frame.
    elif file_under_execution.endswith(".js"):
        cwd = os.getcwd()
        escaped = re.escape(cwd)
        match = re.search(rf"at\s+.*?\({escaped}[\\/](.+?):(\d+):\d+\)", stderr)
        if match:
            path = Path(os.getcwd()) / file_under_execution
            line_number = int(match.group(2))

    # Generic build tool – attempts to find a "file:line" pattern.
    elif file_under_execution.endswith("build"):
        cwd = os.getcwd()
        escaped = re.escape(cwd)
        match = re.search(rf"(?:\()?({escaped}[\\/](.+?))[^\s]*?(\d+):\d+", stderr)
        if match:
            path = Path(match.group(1))
            line_number = int(match.group(3))

    return path, line_number


def sanitize_error(stderr: str) -> str:
    """Remove environment‑specific noise from *stderr*.

    The transformations aim to produce a stable string that can be used for
    hashing and cache lookup:

    * Replace absolute paths with ``<PATH>``.
    * Replace timestamps (HH:MM:SS) with ``<TIME>``.
    * Replace numeric line identifiers with ``<NUM>``.
    """
    cleaned = re.sub(r"(/[\w\.-]+)+", "<PATH>", stderr)
    cleaned = re.sub(r"\d{2}:\d{2}:\d{2}", "<TIME>", cleaned)
    cleaned = re.sub(r"line \d+", "line <NUM>", cleaned)
    return cleaned.strip()


def error_hash(sanitized_error: str) -> str:
    """Return the SHA‑256 hash of *sanitized_error* as a hex string."""
    return hashlib.sha256(sanitized_error.encode("utf-8")).hexdigest()
