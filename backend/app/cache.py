"""A small TTL cache for lookup results, keyed by (lookup, window, args).

The data only changes when the source is reloaded, so ten minutes is about sparing the
database, not about freshness.
"""

import threading
import time
from collections.abc import Callable, Hashable
from typing import Any

TEN_MINUTES = 600.0
MAX_ENTRIES = 512


class TTLCache:
    def __init__(
        self, ttl_seconds: float = TEN_MINUTES, clock: Callable[[], float] = time.monotonic
    ) -> None:
        self._ttl = ttl_seconds
        self._clock = clock
        self._entries: dict[Hashable, tuple[float, Any]] = {}
        self._lock = threading.Lock()

    def get_or_compute[T](self, key: Hashable, compute: Callable[[], T]) -> T:
        # Held while computing, so two requests for the same cold key run one query.
        # Lookups take milliseconds on this data; a per-key lock is not worth its weight.
        with self._lock:
            entry = self._entries.get(key)
            if entry is not None and self._clock() < entry[0]:
                cached: T = entry[1]
                return cached
            value = compute()
            self._make_room()
            self._entries[key] = (self._clock() + self._ttl, value)
            return value

    def _make_room(self) -> None:
        # Part of a key (a person's id) can come from a question, so the key space is
        # not bounded by the data. Expired entries go first; then, if full, everything.
        now = self._clock()
        self._entries = {k: v for k, v in self._entries.items() if now < v[0]}
        if len(self._entries) >= MAX_ENTRIES:
            self._entries.clear()

    def __len__(self) -> int:
        return len(self._entries)
