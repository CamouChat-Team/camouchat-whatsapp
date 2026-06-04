from dataclasses import dataclass
from typing import Any


@dataclass
class ActivityEventModel:
    """Normalized real-time activity / presence event from WA-JS."""

    event_name: str | None
    timestamp: int | None
    contact_id: str | None
    is_online: bool | None
    state: str | None
    short_name: str | None
    is_group: bool | None
    is_user: bool | None
    is_contact: bool | None
    participants: list[dict[str, Any]] | None
    raw: dict[str, Any] | None

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "ActivityEventModel":
        event_name = data.get("eventName") or data.get("event_name") or data.get("kind")
        timestamp = data.get("timestamp") or data.get("t")
        contact_id = data.get("id") or data.get("contact_id") or data.get("chat_id")
        is_online = data.get("online")
        if is_online is None:
            is_online = data.get("isOnline")

        participants = data.get("participants")
        if not isinstance(participants, list):
            participants = None

        raw = data.get("raw")
        if not isinstance(raw, dict):
            raw = data

        return cls(
            event_name=event_name,
            timestamp=timestamp,
            contact_id=contact_id,
            is_online=is_online,
            state=data.get("state"),
            short_name=data.get("shortName") or data.get("short_name"),
            is_group=data.get("isGroup"),
            is_user=data.get("isUser"),
            is_contact=data.get("isContact"),
            participants=participants,
            raw=raw,
        )

    def to_dict(self, include_none: bool = False) -> dict[str, Any]:
        raw = {
            "event_name": self.event_name,
            "timestamp": self.timestamp,
            "contact_id": self.contact_id,
            "is_online": self.is_online,
            "state": self.state,
            "short_name": self.short_name,
            "is_group": self.is_group,
            "is_user": self.is_user,
            "is_contact": self.is_contact,
            "participants": self.participants,
            "raw": self.raw,
        }
        if include_none:
            return raw
        return {key: value for key, value in raw.items() if value is not None}

    def __str__(self) -> str:
        if self.event_name == "conn.online":
            return f"ActivityEventModel(conn.online online={self.is_online})"

        return (
            "ActivityEventModel("
            f"event='{self.event_name}', "
            f"contact='{self.contact_id}', "
            f"state='{self.state}', "
            f"online={self.is_online}"
            ")"
        )