"""동기화 명령.

D1 과 CoC API 를 가짜로 넣어 조립과 보고를 확인한다.
"""

from __future__ import annotations

import httpx

from cli import refresh_clan, refresh_members

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

    rows = await fake_db.prepare(
        "SELECT external_id, name, role FROM clan_members ORDER BY external_id"
    ).all()

    assert [(r.external_id, r.name, r.role) for r in rows.results] == [
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
        "SELECT created_at, updated_at FROM clan_members ORDER BY external_id"
    ).all()

    assert [(r.created_at, r.updated_at) for r in rows.results] == [(NOW, NOW), (NOW, NOW)]


async def test_클랜도_동기화한다(fake_db):
    clan = await refresh_clan(
        db=fake_db,
        token="test-token",
        clan_tag="#2C8L822LQ",
        now=NOW,
        transport=_transport(),
    )

    assert clan.external_id == "#2C8L822LQ"
    assert clan.display_name == "미니언즈"  # 첫 동기화 때 CoC 이름으로 채운다
    assert clan.created_at == NOW


async def test_클랜이_실제로_저장된다(fake_db):
    await refresh_clan(
        db=fake_db,
        token="test-token",
        clan_tag="#2C8L822LQ",
        now=NOW,
        transport=_transport(),
    )

    rows = await fake_db.prepare("SELECT external_id, display_name, status FROM clans").all()

    assert [(r.external_id, r.display_name, r.status) for r in rows.results] == [
        ("#2C8L822LQ", "미니언즈", "ACTIVE")
    ]


async def test_클랜과_클랜원을_따로_부를_수_있다(fake_db):
    """한 번의 CoC 요청에서 둘 다 나오지만 부르는 자리는 갈라 둔다.

    클랜만 갱신하고 싶을 때 클랜원까지 건드리지 않는다.
    """
    await refresh_clan(
        db=fake_db, token="t", clan_tag="#2C8L822LQ", now=NOW, transport=_transport()
    )

    members = await fake_db.prepare("SELECT COUNT(*) AS n FROM clan_members").first()

    assert members.n == 0  # 클랜만 넣었으니 클랜원은 비어 있다
