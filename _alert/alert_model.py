from __future__ import annotations

from dataclasses import dataclass, field


@dataclass(frozen=True)
class Alert:
    id: str
    cat: str = ""
    title: str = "Alert"
    data: tuple[str, ...] = ()
    desc: str = ""
    zone: str = ""
    original_countdown: int = 0

    @classmethod
    def from_dict(cls, d: dict) -> Alert:
        return cls(
            id=d.get("id", ""),
            cat=d.get("cat", ""),
            title=d.get("title", "Alert"),
            data=tuple(d.get("data", [])),
            desc=d.get("desc", ""),
            zone=d.get("zone", ""),
            original_countdown=d.get("original_countdown", 0),
        )

    def to_dict(self) -> dict:
        return {
            "id": self.id,
            "cat": self.cat,
            "title": self.title,
            "data": list(self.data),
            "desc": self.desc,
            "zone": self.zone,
            "original_countdown": self.original_countdown,
        }
