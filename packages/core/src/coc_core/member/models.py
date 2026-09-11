"""클랜원 자료형.

CoC API 의 표기를 그대로 들이지 않는다. 어댑터가 경계에서 우리 값으로 바꾸고,
모르는 값이 오면 UNKNOWN 으로 둔다. 그래야 CoC 가 새 직책을 만들어도 한 명
때문에 동기화가 통째로 멈추지 않는다.
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum


class ClanRole(StrEnum):
    """게임 안 직책.

    이름을 CoC API 표기의 대문자와 맞춘다. 그래서 변환이 한 줄로 끝난다.
    """

    LEADER = "LEADER"
    COLEADER = "COLEADER"  # 언더스코어를 넣지 않는다. API 의 coLeader 와 맞추기 위해서다
    ADMIN = "ADMIN"  # 게임 화면에서는 "장로(Elder)". API 가 admin 으로 준다
    MEMBER = "MEMBER"
    UNKNOWN = "UNKNOWN"

    @classmethod
    def from_coc(cls, raw: str) -> ClanRole:
        """CoC API 표기를 우리 값으로. 모르는 값이면 UNKNOWN."""
        try:
            return cls(raw.upper())
        except ValueError:
            return cls.UNKNOWN


class MemberStatus(StrEnum):
    """클랜 소속 여부. CoC API 가 주지 않고 우리가 판정한다."""

    ACTIVE = "ACTIVE"  # 지금 클랜 목록에 있다
    INACTIVE = "INACTIVE"  # 목록에서 사라졌다. 지우지 않고 내려 둔다


@dataclass(frozen=True)
class ClanMember:
    """클랜원 한 명.

    id 는 우리 식별자이고 tag 는 CoC 세계의 식별자다. 주소에서 '#' 을 인코딩하지
    않으려고 id 를 따로 둔다.
    """

    id: str
    tag: str
    name: str
    role: ClanRole
    status: MemberStatus
    townhall: int | None
    trophies: int | None
    donations: int | None
    donations_received: int | None
    description: str | None
    created_at: str
    updated_at: str
