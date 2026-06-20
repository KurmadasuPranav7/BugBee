"""Legacy shim for backward compatibility.

The original project exposed a ``main`` function in ``cli-wrapper/src/cli_wrapper/main.py``.
We import that function and expose it here so existing ``import bugbee.legacy``
or ``python -m bugbee.legacy`` continues to work.
"""

import sys
from pathlib import Path

# Ensure the original source directory is on ``sys.path``.
_PROJECT_ROOT = Path(__file__).resolve().parents[2]  # points to repository root
_SRC_DIR = _PROJECT_ROOT / "cli-wrapper" / "src" / "cli_wrapper"
if str(_SRC_DIR) not in sys.path:
    sys.path.insert(0, str(_SRC_DIR))

# Import the historic ``main`` function.
try:
    from main import main as _original_main  # type: ignore
except Exception as exc:  # pragma: no cover – during early development the module may not be importable yet
    raise ImportError("Unable to import legacy main function") from exc


def main() -> None:
    """Entry point that forwards to the original implementation.

    This wrapper exists so that external scripts that called the old ``main``
    continue to operate.  All behaviour (including interactive prompts) is
    unchanged.
    """
    _original_main()
