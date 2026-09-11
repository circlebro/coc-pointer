"""CoC API 어댑터.

httpx 의 MockTransport 로 응답을 흉내낸다. 실제 API 를 부르지 않는다.
"""

from __future__ import annotations

import httpx
import pytest

from adapters.coc_api import USER_AGENT, CocApi, CocApiError, encode_tag

CLAN_PAYLOAD = {
    "tag": "#2C8L822LQ",
    "name": "미니언즈",
    "memberList": [
        {
            "tag": "#A",
            "name": "도토리",
            "role": "admin",
            "townHallLevel": 16,
            "trophies": 4200,
            "donations": 100,
            "donationsReceived": 50,
        }
    ],
}


def _api(handler) -> CocApi:
    return CocApi(
        token="test-token",
        clan_tag="#2C8L822LQ",
        transport=httpx.MockTransport(handler),
    )


async def test_클랜원_목록을_그대로_돌려준다():
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, json=CLAN_PAYLOAD)

    api = _api(handler)
    members = await api.fetch_members()
    await api.aclose()

    assert len(members) == 1
    assert members[0]["role"] == "admin"  # 가공하지 않는다


async def test_태그를_인코딩해_부른다():
    seen: list[str] = []

    def handler(request: httpx.Request) -> httpx.Response:
        # raw_path 를 본다. url.path 는 httpx 가 디코딩한 값이라
        # %23 이 # 로 되돌아와 인코딩 여부를 그대로 확인할 수 없다
        seen.append(request.url.raw_path.decode())
        return httpx.Response(200, json=CLAN_PAYLOAD)

    api = _api(handler)
    await api.fetch_members()
    await api.aclose()

    assert seen == ["/v1/clans/%232C8L822LQ"]


async def test_프록시가_요구하는_헤더를_붙인다():
    seen: dict[str, str] = {}

    def handler(request: httpx.Request) -> httpx.Response:
        seen.update(request.headers)
        return httpx.Response(200, json=CLAN_PAYLOAD)

    api = _api(handler)
    await api.fetch_members()
    await api.aclose()

    assert seen["authorization"] == "Bearer test-token"
    assert seen["user-agent"] == USER_AGENT


async def test_실패하면_이유를_담아_올린다():
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(403, json={"reason": "accessDenied", "message": "잘못된 토큰"})

    api = _api(handler)
    with pytest.raises(CocApiError) as caught:
        await api.fetch_members()
    await api.aclose()

    assert caught.value.status == 403
    assert "accessDenied" in str(caught.value)


def test_태그_인코딩():
    assert encode_tag("#2ABC123") == "%232ABC123"
    assert encode_tag("2ABC123") == "%232ABC123"
