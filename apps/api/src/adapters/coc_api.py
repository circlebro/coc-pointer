"""CoC 공식 API 어댑터.

RoyaleAPI 프록시를 거친다. 허용 IP 를 프록시가 대신 맞춰 주기 때문이며,
프록시는 User-Agent 없는 요청을 거절한다.

받은 값을 가공하지 않고 그대로 넘긴다. 우리 값으로 바꾸는 일은 도메인 서비스가
한다. 이 층은 "가져오는 일"만 맡는다.
"""

from __future__ import annotations

from typing import Any

import httpx

PROXY_BASE_URL = "https://cocproxy.royaleapi.dev/v1"
USER_AGENT = "coc-pointer (+https://github.com/circlebro/coc-pointer)"


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
    """MemberSource 를 CoC 공식 API 로 구현한다."""

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
