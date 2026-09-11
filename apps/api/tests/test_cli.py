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
