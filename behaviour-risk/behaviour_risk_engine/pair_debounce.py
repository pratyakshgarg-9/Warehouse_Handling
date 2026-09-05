"""
Shared "this condition must hold continuously for N seconds before it
counts, and fire only once per continuous occurrence" pattern — used by
several detectors (stepping-on-product, incorrect/unstable stacking,
pallet positioning) that all track a relationship between two tracked
objects over time.
"""

from __future__ import annotations

from datetime import datetime
from typing import Dict, Hashable, Set


class PairDebouncer:
    def __init__(self, min_duration_s: float):
        self._min_duration_s = min_duration_s
        self._since: Dict[Hashable, datetime] = {}
        self._reported: Set[Hashable] = set()

    def observe(self, key: Hashable, timestamp: datetime, active_keys: Set[Hashable]) -> bool:
        """Call once per frame for each currently-active key. Returns True
        the moment this key has been continuously active for
        min_duration_s (fires exactly once per continuous occurrence)."""
        active_keys.add(key)
        start = self._since.setdefault(key, timestamp)
        duration = (timestamp - start).total_seconds()
        if duration >= self._min_duration_s and key not in self._reported:
            self._reported.add(key)
            return True
        return False

    def sweep(self, active_keys: Set[Hashable]) -> None:
        """Call once per frame after all observe() calls, to clear state
        for keys not seen active this frame."""
        for key in list(self._since):
            if key not in active_keys:
                self._since.pop(key, None)
                self._reported.discard(key)
