"""Immutable data types shared by collector, scorer and renderer.

All datetimes are timezone-aware UTC. Serialized form is ``2026-09-05T14:30:00Z``.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime
from typing import Any

WAR_TYPES = ("regular", "cwl")
_ISO = "%Y-%m-%dT%H:%M:%SZ"


def to_iso(dt: datetime) -> str:
    return dt.astimezone(UTC).strftime(_ISO)


def from_iso(text: str) -> datetime:
    return datetime.strptime(text, _ISO).replace(tzinfo=UTC)


@dataclass(frozen=True)
class Attack:
    order: int
    stars: int


@dataclass(frozen=True)
class WarMember:
    tag: str
    name: str
    townhall: int
    attacks: tuple[Attack, ...] = ()


@dataclass(frozen=True)
class War:
    war_type: str
    start_time: datetime
    end_time: datetime
    team_size: int
    attacks_per_member: int
    opponent_tag: str
    opponent_name: str
    members: tuple[WarMember, ...]

    @property
    def file_name(self) -> str:
        stamp = self.end_time.astimezone(UTC).strftime("%Y-%m-%dT%H-%M-%SZ")
        return f"{stamp}_{self.war_type}_{self.opponent_tag.lstrip('#')}.json"

    def to_dict(self) -> dict[str, Any]:
        return {
            "war_type": self.war_type,
            "start_time": to_iso(self.start_time),
            "end_time": to_iso(self.end_time),
            "team_size": self.team_size,
            "attacks_per_member": self.attacks_per_member,
            "opponent": {"tag": self.opponent_tag, "name": self.opponent_name},
            "members": [
                {
                    "tag": m.tag,
                    "name": m.name,
                    "townhall": m.townhall,
                    "attacks": [{"order": a.order, "stars": a.stars} for a in m.attacks],
                }
                for m in self.members
            ],
        }

    @classmethod
    def from_dict(cls, d: dict[str, Any]) -> War:
        return cls(
            war_type=d["war_type"],
            start_time=from_iso(d["start_time"]),
            end_time=from_iso(d["end_time"]),
            team_size=d["team_size"],
            attacks_per_member=d["attacks_per_member"],
            opponent_tag=d["opponent"]["tag"],
            opponent_name=d["opponent"]["name"],
            members=tuple(
                WarMember(
                    tag=m["tag"],
                    name=m["name"],
                    townhall=m["townhall"],
                    attacks=tuple(Attack(a["order"], a["stars"]) for a in m["attacks"]),
                )
                for m in d["members"]
            ),
        )


@dataclass(frozen=True)
class ClanMember:
    tag: str
    name: str
    role: str
    townhall: int
    trophies: int
    donations: int
    donations_received: int


@dataclass(frozen=True)
class ClanSnapshot:
    fetched_at: datetime
    name: str
    tag: str
    members: tuple[ClanMember, ...]

    def to_dict(self) -> dict[str, Any]:
        return {
            "fetched_at": to_iso(self.fetched_at),
            "name": self.name,
            "tag": self.tag,
            "members": [
                {
                    "tag": m.tag,
                    "name": m.name,
                    "role": m.role,
                    "townhall": m.townhall,
                    "trophies": m.trophies,
                    "donations": m.donations,
                    "donations_received": m.donations_received,
                }
                for m in self.members
            ],
        }

    @classmethod
    def from_dict(cls, d: dict[str, Any]) -> ClanSnapshot:
        return cls(
            fetched_at=from_iso(d["fetched_at"]),
            name=d["name"],
            tag=d["tag"],
            members=tuple(
                ClanMember(
                    tag=m["tag"],
                    name=m["name"],
                    role=m["role"],
                    townhall=m["townhall"],
                    trophies=m["trophies"],
                    donations=m["donations"],
                    donations_received=m["donations_received"],
                )
                for m in d["members"]
            ),
        )
