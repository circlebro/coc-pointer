"""클랜원 자료형.

CoC API 의 표기를 그대로 들이지 않는다. 어댑터가 경계에서 우리 값으로 바꾸고,
모르는 값이 오면 UNKNOWN 으로 둔다. 그래야 CoC 가 새 직책을 만들어도 한 명
때문에 동기화가 통째로 멈추지 않는다.

ClanMember 와 MemberProfile 을 가른다. 앞은 우리가 만들어 낸 값이고 뒤는 CoC 가
주인인 현황이다. 우리는 뒤엣것을 담아 두지 않고 물을 때마다 CoC 에 묻는다.
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
    """클랜원 한 명. 게임 계정 하나를 가리키며 사람이 아니다.

    우리가 만들어 낸 값만 담는다. 이름·직책·홀·트로피는 CoC 가 주인이라 담지
    않고, 필요할 때 external_id 로 CoC 에 묻는다(MemberProfile).

    이름을 담지 않아도 되는 까닭은 과거 기록이 제 이름을 들고 있기 때문이다.
    5월 점수표는 5월의 이름을, 클랜전 기록은 그때의 이름을 들고 있다. 계정이
    사라져도 그 화면들은 읽힌다.

    display_name 은 사람이 정한 표기라 아무도 고치지 않았으면 None 이다.
    동기화는 이것을 채우지 않는다. 채우면 그 값이 사람이 정한 것인지 동기화가
    써 넣은 것인지 구분할 수 없다. 비었을 때 무엇을 보여줄지는 화면이 정한다.

    updated_at 은 이 행이 마지막으로 바뀐 시각이라 메모를 고쳐도 올라가고,
    synced_at 은 CoC 명단에서 마지막으로 본 시각이라 동기화만 올린다.
    """

    id: str
    external_id: str
    display_name: str | None
    status: MemberStatus
    warnings: int
    description: str | None
    created_at: str
    updated_at: str
    synced_at: str | None


@dataclass(frozen=True)
class MemberProfile:
    """CoC 가 주인인 현황. 담아 두지 않고 물을 때마다 받는다.

    external_id 로 어느 클랜원의 것인지 가린다. 우리 식별자를 모르는 층
    (CoC 어댑터)에서도 만들 수 있어야 하기 때문이다.

    fetched_at 이 이 값들의 나이를 말해 준다. 사본이 아니라는 것을 숨기지 않기
    위해 함께 담는다.
    """

    external_id: str
    name: str
    role: ClanRole
    townhall: int | None
    trophies: int | None
    donations: int | None
    donations_received: int | None
    fetched_at: str
