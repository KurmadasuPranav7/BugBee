"""Utility helpers for lazy importing heavy dependencies.

This module provides a simple ``lazy_import`` function that defers the actual
``import`` until the first attribute access.  It is used throughout the codebase
to keep the CLI start‑up path lightweight.
"""

from __future__ import annotations

import importlib
import sys
import types
from typing import Any


def lazy_import(module_name: str) -> types.ModuleType:
    """Return a proxy module that imports ``module_name`` on first attribute use.

    The returned object behaves like the real module but delays the import until
    an attribute or ``__getattr__`` is accessed.  Subsequent accesses reuse the
    already-loaded module.
    """

    class _LazyModule(types.ModuleType):
        __dict__: dict[str, Any]
        _module: types.ModuleType | None = None

        def _load(self) -> types.ModuleType:
            if self._module is None:
                self._module = importlib.import_module(module_name)
                # Insert the loaded module into ``sys.modules`` so other imports
                # resolve to the same object.
                sys.modules[module_name] = self._module
            return self._module

        def __getattr__(self, name: str) -> Any:  # pragma: no cover – exercised at runtime
            return getattr(self._load(), name)

        def __dir__(self) -> list[str]:  # pragma: no cover
            return dir(self._load())

    return _LazyModule(module_name)
