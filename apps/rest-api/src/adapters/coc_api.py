"""CoC 공식 API 어댑터.

RoyaleAPI 프록시를 거친다. 허용 IP 를 프록시가 대신 맞춰 주기 때문이며,
프록시는 User-Agent 없는 요청을 거절한다.

받은 값을 가공하지 않고 그대로 넘긴다. 우리 값으로 바꾸는 일은 도메인 서비스가
한다. 이 층은 "가져오는 일"만 맡는다.
"""

from __future__ import annotations

from datetime import UTC, datetime
from typing import Any

import httpx
from coc_core.member.models import ClanRole, MemberProfile

PROXY_BASE_URL = "https://cocproxy.royaleapi.dev/v1"
USER_AGENT = "coc-pointer (+https://github.com/circlebro/coc-pointer)"


def _now() -> str:
    """받은 시각. ISO 8601(UTC). 현황의 나이를 밝히는 데 쓴다."""
    return datetime.now(UTC).strftime("%Y-%m-%dT%H:%M:%SZ")


def _to_profile(raw: dict[str, Any], fetched_at: str) -> MemberProfile:
    """CoC 가 준 항목을 우리 자료형으로. 경계에서 한 번만 바꾼다.

    클랜 응답의 항목과 /players 응답은 열쇠 이름이 같아 한 함수로 다룬다.
    다만 /players 는 무소속이면 role 이 없고, 그때는 UNKNOWN 이 된다.
    """
    return MemberProfile(
        external_id=raw["tag"],
        name=raw["name"],
        role=ClanRole.from_coc(raw.get("role", "")),
        townhall=raw.get("townHallLevel"),
        trophies=raw.get("trophies"),
        donations=raw.get("donations"),
        donations_received=raw.get("donationsReceived"),
        fetched_at=fetched_at,
    )


class CocApiError(RuntimeError):
    """CoC API 가 200 이 아닌 답을 준 경우."""

    def __init__(self, status: int, path: str, reason: str, message: str) -> None:
        super().__init__(f"{status} {path}: {reason} {message}".strip())
        self.status = status
        self.path = path
        self.reason = reason


def encode_tag(tag: str) -> str:
    """플레이어·클랜 태그를 주소에 넣을 수 있게 바꾼다.

    '#' 은 주소에서 조각 구분자라 그대로 쓸 수 없다. 앞에 '#' 이 없으면 붙인다.
    """
    return "%23" + tag.lstrip("#")


class CocApi:
    """MemberSource·ClanSource·MemberProfileReader 를 CoC 공식 API 로 구현한다.

    명단과 클랜 정보는 같은 요청(GET /clans/{tag})에서 나온다. CoC 가 둘을 한
    번에 주기 때문이다. 다만 부르는 쪽이 무엇을 받는지 분명하도록 메서드는
    갈라 둔다.

    한 사람만 필요할 때는 GET /players/{tag} 를 쓴다. 클랜을 나간 사람은 클랜
    응답에 없지만 이쪽으로는 나온다. 계정 자체가 사라졌으면 404 다.
    """

    def __init__(
        self,
        token: str,
        clan_tag: str,
        base_url: str = PROXY_BASE_URL,
        transport: httpx.AsyncBaseTransport | None = None,
    ) -> None:
        self._clan_tag = clan_tag
        self._client = httpx.AsyncClient(
            base_url=base_url,
            headers={
                "Authorization": f"Bearer {token}",
                "User-Agent": USER_AGENT,
                "Accept": "application/json",
            },
            timeout=30.0,
            transport=transport,
        )

    async def aclose(self) -> None:
        await self._client.aclose()

    async def fetch_members(self) -> list[dict[str, Any]]:
        """클랜원 목록. CoC 가 준 항목을 그대로 돌려준다."""
        clan = await self._get(f"/clans/{encode_tag(self._clan_tag)}")
        return list(clan.get("memberList", []))

    async def fetch_player(self, external_id: str) -> dict[str, Any] | None:
        """한 사람. 계정이 사라졌으면 None.

        404 만 None 으로 바꾼다. 그 밖의 실패는 그대로 올린다. 서버가 잠깐
        아픈 것과 계정이 없는 것은 다른 일이고, 전자를 조용히 삼키면 "이 사람
        계정이 사라졌다"는 잘못된 결론이 화면까지 간다.
        """
        try:
            return await self._get(f"/players/{encode_tag(external_id)}")
        except CocApiError as exc:
            if exc.status == 404:
                return None
            raise

    async def read_clan_profiles(self) -> dict[str, MemberProfile]:
        """클랜에 있는 사람 전부의 현황. 태그를 열쇠로 한 사전. 호출은 한 번이다."""
        now = _now()
        return {raw["tag"]: _to_profile(raw, now) for raw in await self.fetch_members()}

    async def read_profile(self, external_id: str) -> MemberProfile | None:
        """한 사람의 현황. 계정이 사라졌으면 None.

        /players 응답은 클랜 응답과 직책 자리가 다르다. 클랜에 속해 있으면
        clan.role 이 아니라 최상위 role 에 담겨 오고, 무소속이면 아예 없다.
        무소속은 우리가 아는 직책이 없다는 뜻이라 UNKNOWN 으로 둔다.
        """
        raw = await self.fetch_player(external_id)
        return None if raw is None else _to_profile(raw, _now())

    async def fetch_clan(self) -> dict[str, Any]:
        """클랜 정보. 클랜원 목록은 빼고 돌려준다.

        뺄 때 원본을 고치지 않고 사본을 만든다. 부르는 쪽이 받은 것을 그대로
        믿을 수 있어야 하고, 같은 응답을 두 메서드가 나눠 쓰기 때문이다.
        """
        clan = await self._get(f"/clans/{encode_tag(self._clan_tag)}")
        return {k: v for k, v in clan.items() if k != "memberList"}

    async def _get(self, path: str) -> dict[str, Any]:
        response = await self._client.get(path)
        if response.status_code != 200:
            body: dict[str, Any] = {}
            try:
                body = response.json()
            except ValueError:
                pass
            raise CocApiError(
                status=response.status_code,
                path=path,
                reason=str(body.get("reason", "")),
                message=str(body.get("message", "")),
            )
        return response.json()
