"""Stateful alert deduplication logic."""
from __future__ import annotations


class AlertDeduplicator:
    """Tracks seen alert IDs to suppress duplicates."""

    def __init__(self) -> None:
        self._seen: set[str] = set()

    def is_new(self, alert_id: str) -> bool:
        """Return True if *alert_id* has not been seen before."""
        return alert_id not in self._seen

    def mark_seen(self, alert_id: str) -> None:
        """Record *alert_id* as seen."""
        self._seen.add(alert_id)

    @property
    def seen_ids(self) -> set[str]:
        """Return the set of all seen alert IDs."""
        return self._seen
