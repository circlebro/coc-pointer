"""클랜 자료형.

CoC 가 주인인 값은 담지 않는다. 마크·레벨·클랜 점수·전적은 물어보면 언제나
지금 값을 주므로, 우리가 사본을 들고 있으면 두 곳에서 관리하게 되고 동기화
사이에 화면이 낡은 값을 보여 준다. 필요하면 external_id 로 CoC 에 물으면 된다.

담는 것은 CoC 가 모르는 값뿐이다. 우리 식별자, 우리가 붙인 이름, 우리 판정.
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum


class ClanStatus(StrEnum):
    """우리가 이 클랜을 다루는가. CoC 는 이것을 모른다.

    MemberStatus 와 값이 같지만 뜻이 다르다. 저쪽은 "클랜에 남아 있는가"이고
    이쪽은 "우리 관심사인가"다. 한쪽만 값이 늘 수 있으므로 따로 둔다.
    """

    ACTIVE = "ACTIVE"  # 지금 다루는 클랜
    INACTIVE = "INACTIVE"  # 더는 다루지 않는다. 지우지 않고 내려 둔다


@dataclass(frozen=True)
class Clan:
    """클랜 하나.

    id 는 우리 식별자이고 external_id 는 CoC 세계의 식별자다. 주소에서 '#' 을
    인코딩하지 않으려고 따로 둔다.

    이름조차 우리가 관리한다. 게임에서 클랜 이름을 바꿀 수 있기 때문이며,
    그때도 우리 표기는 그대로 둘 수 있다. 반면 태그는 클랜을 만들 때 정해지고
    바뀌지 않으므로, 동기화할 때는 그것으로 찾는다.
    """

    id: str
    external_id: str
    display_name: str | None
    status: ClanStatus
    created_at: str
    updated_at: str
