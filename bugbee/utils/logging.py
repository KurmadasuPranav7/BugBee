"""Logging utilities for BugBee.

The module configures a root logger the first time it is imported. By
**default BugBee writes structured logs to a file only** — the terminal is
owned entirely by ``bugbee.ui``, which renders a polished, human-readable
line for the same events via ``rich``. Previously this handler wrote to
``sys.stdout``, which meant every event printed *twice*: once as a plain
``HH:MM:SS | INFO | ... | message`` line from this module, and once as the
styled line from ``bugbee.ui``. Routing this logger to disk instead removes
that duplication while keeping the full diagnostic trail available for bug
reports.

Verbosity (the file log level) is controlled via the global
``bugbee.config.settings.Settings.log_level`` value. If you want the raw,
timestamped log lines on the console too — e.g. while debugging a flaky LLM
call — pass ``--verbose`` on the CLI, which calls
:func:`enable_console_logging`.
"""

from __future__ import annotations

import logging
from pathlib import Path

from bugbee.config.settings import settings

_LOG_FORMAT = "%(asctime)s | %(levelname)-8s | %(name)s | %(message)s"
_DATE_FORMAT = "%H:%M:%S"

_DEFAULT_LOG_DIR = Path.home() / ".bugbee" / "logs"
_DEFAULT_LOG_FILE = _DEFAULT_LOG_DIR / "bugbee.log"


def _log_file_path() -> Path:
    """Resolve the log file location, honouring ``settings.log_file`` if set."""
    configured = getattr(settings, "log_file", None)
    path = Path(configured) if configured else _DEFAULT_LOG_FILE
    path.parent.mkdir(parents=True, exist_ok=True)
    return path


def _configure_logging() -> None:
    """Attach a file handler to the root logger according to current settings.

    Deliberately does **not** attach a console handler by default: BugBee's
    terminal output is owned by ``bugbee.ui`` so users see one clean, styled
    line per event instead of a duplicate plain-text log line underneath it.
    """
    root = logging.getLogger()
    if any(isinstance(h, logging.FileHandler) for h in root.handlers):
        return  # already configured

    level = getattr(logging, settings.log_level.upper(), logging.INFO)

    handler = logging.FileHandler(_log_file_path(), encoding="utf-8")
    handler.setFormatter(logging.Formatter(_LOG_FORMAT, datefmt=_DATE_FORMAT))
    handler.setLevel(level)

    root.setLevel(level)
    root.addHandler(handler)


def enable_console_logging(level: int = logging.DEBUG) -> None:
    """Additionally stream raw log lines to the console (``--verbose`` mode).

    Uses ``rich.logging.RichHandler`` instead of a plain ``StreamHandler`` so
    the extra output stays visually consistent with the rest of the BugBee
    UI instead of looking like a different, bolted-on tool.
    """
    from rich.logging import RichHandler

    root = logging.getLogger()
    if any(isinstance(h, RichHandler) for h in root.handlers):
        return  # already enabled

    handler = RichHandler(level=level, show_time=True, show_path=False, markup=True)
    root.addHandler(handler)
    if root.level > level:
        root.setLevel(level)


# Configure file logging on import – mirrors the behaviour of many libraries,
# but writes to disk instead of the terminal so it never collides with the
# rich-powered UI in ``bugbee.ui``.
_configure_logging()


def get_logger(name: str) -> logging.Logger:
    """Return a logger scoped to *name* (typically ``__name__``)."""
    return logging.getLogger(name)