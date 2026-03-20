from __future__ import annotations


class AlertDeduplicator:
    def __init__(self) -> None:
        self._seen: set[str] = set()

    def is_new(self, alert_id: str) -> bool:
        return alert_id not in self._seen

    def mark_seen(self, alert_id: str) -> None:
        self._seen.add(alert_id)

    @property
    def seen_ids(self) -> set[str]:
        return self._seen
