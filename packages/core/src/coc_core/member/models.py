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


class MemberGrade(StrEnum):
    """리그전 선발에서의 자리.

    시트는 넷으로 적는다(확정 ● · 경쟁 △ · 예비 ◎ · 제외 ✕). 여기 담는 것은
    셋뿐이다.

    - 사람이 매기는 것: FIXED, EXCLUDED
    - 계산되는 것: 경쟁과 예비는 그 달 점수 순위가 가른다. 30위 안이면 경쟁,
      밖이면 예비다. 매달 바뀌는 값이라 담지 않는다

    담아 두면 점수가 바뀔 때마다 맞춰 줘야 하고, 그러다 어긋난다.
    """

    FIXED = "FIXED"  # 확정 ●. 길드장·부길드장·명예
    COMPETING = "COMPETING"  # 경쟁 △. 아무것도 매기지 않으면 이것이다
    EXCLUDED = "EXCLUDED"  # 제외 ✕. 부캐, 쉬는 계정


class MemberStatus(StrEnum):
    """클랜 소속 여부. CoC API 가 주지 않고 우리가 판정한다."""

    ACTIVE = "ACTIVE"  # 지금 클랜 목록에 있다
    INACTIVE = "INACTIVE"  # 목록에서 사라졌다. 지우지 않고 내려 둔다


@dataclass(frozen=True)
class ClanMember:
    """클랜원 한 명.

    id 는 우리 식별자이고 external_id 는 CoC 세계의 식별자다. 주소에서 '#' 을
    인코딩하지 않으려고 id 를 따로 둔다. Clan 과 같은 규칙이다.

    grade·grade_reason·warnings 는 우리가 정하는 값이라 동기화가 덮어쓰지 않는다.
    CoC 는 이런 것을 모른다.

    display_name 과 name 도 다르다. 앞은 사람이 정한 표기라 아무도 고치지 않았으면
    None 이고, 뒤는 CoC 가 지금 들고 있는 이름이라 동기화가 늘 덮는다. 동기화는
    display_name 을 채우지 않는다. 채우면 그 값이 사람이 정한 것인지 동기화가 써
    넣은 것인지 구분할 수 없다. 비었을 때 무엇을 보여줄지는 화면이 정한다.

    updated_at 과 synced_at 은 다르다. 앞은 이 행이 마지막으로 바뀐 시각이라
    메모를 고쳐도 올라가고, 뒤는 CoC 가 준 값을 받아 적은 시각이라 동기화만
    올린다. 둘을 하나로 두면 메모만 고친 뒤에도 "방금 받은 값"처럼 보인다.
    """

    id: str
    external_id: str
    display_name: str | None
    name: str
    role: ClanRole
    status: MemberStatus
    grade: MemberGrade
    grade_reason: str | None
    warnings: int
    townhall: int | None
    trophies: int | None
    donations: int | None
    donations_received: int | None
    description: str | None
    created_at: str
    updated_at: str
    synced_at: str | None
