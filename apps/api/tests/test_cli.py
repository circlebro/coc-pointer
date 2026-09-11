"""동기화 명령.

D1 과 CoC API 를 가짜로 넣어 조립과 보고를 확인한다.
"""

from __future__ import annotations

import httpx

from cli import refresh_members

NOW = "2026-09-10T05:30:00Z"

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
        },
        {
            "tag": "#B",
            "name": "히로",
            "role": "veteran",
            "townHallLevel": 15,
            "trophies": 3800,
            "donations": 80,
            "donationsReceived": 40,
        },
    ],
}


def _transport() -> httpx.MockTransport:
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, json=CLAN_PAYLOAD)

    return httpx.MockTransport(handler)


async def test_동기화_결과를_돌려준다(fake_db):
    result = await refresh_members(
        db=fake_db,
        token="test-token",
        clan_tag="#2C8L822LQ",
        now=NOW,
        transport=_transport(),
    )

    assert result.total == 2
    assert result.added == 2
    assert result.unknown_roles == {"veteran": 1}


async def test_실제로_저장된다(fake_db):
    await refresh_members(
        db=fake_db,
        token="test-token",
        clan_tag="#2C8L822LQ",
        now=NOW,
        transport=_transport(),
    )

    rows = await fake_db.prepare("SELECT tag, name, role FROM clan_members ORDER BY tag").all()

    assert [(r.tag, r.name, r.role) for r in rows.results] == [
        ("#A", "도토리", "ADMIN"),
        ("#B", "히로", "UNKNOWN"),
    ]


async def test_넘긴_시각이_그대로_담긴다(fake_db):
    """now 가 조립을 거쳐 실제로 저장까지 닿는지 본다.

    이것이 없으면 refresh_members 가 now 를 받아 놓고 버린 채 다른 시각을
    써도 앞의 두 테스트는 그대로 통과한다. 처음 본 시각과 갱신 시각은 나중에
    누가 언제 들어왔는지 가리는 근거가 되므로 어긋나면 곤란하다.
    """
    await refresh_members(
        db=fake_db,
        token="test-token",
        clan_tag="#2C8L822LQ",
        now=NOW,
        transport=_transport(),
    )

    rows = await fake_db.prepare(
        "SELECT created_at, updated_at FROM clan_members ORDER BY tag"
    ).all()

    assert [(r.created_at, r.updated_at) for r in rows.results] == [(NOW, NOW), (NOW, NOW)]
