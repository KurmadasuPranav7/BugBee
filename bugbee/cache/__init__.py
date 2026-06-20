"""Cache handling for BugBee.

Provides a thin wrapper around a JSON file (default ``bugbee.json``) used to
store LLM responses keyed by a deterministic error hash.  The API mirrors the
original script's ``check_cache`` and ``save_to_cache`` functions.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Dict, Optional

from bugbee.config.settings import settings

__all__ = ["Cache", "cache"]


class Cache:
    """Simple JSON‑file cache.

    The cache file is created on first use and persisted between runs.  Loading
    and writing are performed lazily to avoid disk I/O during CLI start‑up.
    """

    def __init__(self, path: Optional[Path] = None) -> None:
        self.path = path or settings.cache_file
        self._data: Dict[str, Any] = {}
        self._loaded = False

    def _load(self) -> None:
        if self._loaded:
            return
        if self.path.is_file():
            try:
                self._data = json.load(self.path.open())
            except json.JSONDecodeError:
                self._data = {}
        else:
            self._data = {}
        self._loaded = True

    def _save(self) -> None:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self.path.write_text(json.dumps(self._data, indent=2))

    def get(self, key: str) -> Optional[Any]:
        self._load()
        return self._data.get(key)

    def set(self, key: str, value: Any) -> None:
        self._load()
        self._data[key] = value
        self._save()

    def clear(self) -> None:
        self._data.clear()
        self._loaded = True
        if self.path.is_file():
            self.path.unlink()

# Export a lazy accessor for the cache. The cache object is instantiated
# only when first needed, avoiding file I/O during CLI start‑up.

def get_cache() -> Cache:
    """Return a shared ``Cache`` instance, creating it on first call.

    This mirrors the previous ``cache`` singleton but defers the actual object
    construction (and the associated disk read) until the cache is accessed.
    """
    global _cache_instance
    try:
        return _cache_instance
    except NameError:
        _cache_instance = Cache()
        return _cache_instance
