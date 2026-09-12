"""
Analysis results cache for JMeter test results.

Caches analyze_file results keyed by file identity (path, mtime, size)
so repeated tool calls don't re-parse unchanged files.
"""

import os
from collections import OrderedDict
from pathlib import Path
from typing import Dict, Optional, Tuple


class AnalysisCache:
    """LRU cache for analysis results."""

    def __init__(self, max_entries: int = 8) -> None:
        self.max_entries = max(0, int(max_entries))
        self._store: "OrderedDict[Tuple[str, int, int], Dict]" = OrderedDict()
        self.hits = 0
        self.misses = 0

    @staticmethod
    def key_for(path: Path) -> Tuple[str, int, int]:
        """Cache key: resolved path + modification time + size."""
        resolved = Path(path).resolve()
        st = resolved.stat()
        return (str(resolved), st.st_mtime_ns, st.st_size)

    def get(self, path: Path) -> Optional[Dict]:
        key = self.key_for(path)
        if key in self._store:
            self._store.move_to_end(key)
            self.hits += 1
            return self._store[key]
        self.misses += 1
        return None

    def put(self, path: Path, value: Dict) -> None:
        if self.max_entries <= 0:
            return
        key = self.key_for(path)
        self._store[key] = value
        self._store.move_to_end(key)
        while len(self._store) > self.max_entries:
            self._store.popitem(last=False)

    def clear(self) -> None:
        self._store.clear()

    def __len__(self) -> int:
        return len(self._store)


_default_cache: Optional[AnalysisCache] = None


def _cache_size_from_env() -> int:
    raw = os.getenv('JMETER_ANALYSIS_CACHE_SIZE')
    if raw is None:
        return 8
    try:
        size = int(raw)
    except ValueError:
        return 8
    if size < 0:
        return 8
    return size  # 0 disables the cache


def default_cache() -> AnalysisCache:
    """Module-level shared cache; size from JMETER_ANALYSIS_CACHE_SIZE."""
    global _default_cache
    if _default_cache is None:
        _default_cache = AnalysisCache(max_entries=_cache_size_from_env())
    return _default_cache
