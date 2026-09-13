"""클랜 조회 경로."""

from __future__ import annotations

import asyncio

import pytest
from coc_core.clan.models import Clan, ClanStatus
from fastapi.testclient import TestClient

from adapters.clan_repository import D1ClanRepository
from schemas import Clan as ClanSchema
from schemas import ClanListResponse
from worker import app

NOW = "2026-09-11T07:18:57Z"


class FakeEnv:
    API_VERSION = "0.6.0"
    COC_API_TOKEN = "test-token"
    CLAN_TAG = "#2C8L822LQ"

    def __init__(self, db) -> None:
        self.DB = db


def _clan(external_id: str = "#2C8L822LQ", **overrides) -> Clan:
    base = {
        "id": f"uuid-{external_id.lstrip('#')}",
        "external_id": external_id,
        "display_name": "미니언즈",
        "status": ClanStatus.ACTIVE,
        "created_at": NOW,
        "updated_at": NOW,
    }
    base.update(overrides)
    return Clan(**base)


@pytest.fixture
def client(fake_db):
    env = FakeEnv(fake_db)

    async def with_env(scope, receive, send):
        scope["env"] = env
        await app(scope, receive, send)

    return TestClient(with_env)


def _seed(fake_db, clans):
    async def go():
        repository = D1ClanRepository(fake_db)
        for c in clans:
            await repository.upsert(c)

    asyncio.run(go())


def test_아무것도_없으면_빈_목록(client):
    body = client.get("/api/v1/clans").json()

    assert body == {"clans": []}


def test_스펙대로_캐멀케이스로_준다(client, fake_db):
    _seed(fake_db, [_clan()])

    clan = client.get("/api/v1/clans").json()["clans"][0]

    assert clan["externalId"] == "#2C8L822LQ"
    assert clan["displayName"] == "미니언즈"
    assert clan["status"] == "ACTIVE"
    assert clan["createdAt"] == NOW
    assert "external_id" not in clan


def test_응답이_스펙_모델을_그대로_통과한다(client, fake_db):
    """생성 모델로 검증한다.

    클랜원 경로는 이렇게 하지 못한다. 스펙이 id 를 format: uuid 로, 시각을
    format: date-time 으로 선언해 생성 모델이 UUID·AwareDatetime 이 되는데
    도메인은 둘 다 문자열로 다루기 때문이다. 클랜 스펙은 그 format 을 두지
    않아 전부 str 로 생성되고, 그래서 여기서는 모델을 실제로 쓸 수 있다.
    """
    _seed(fake_db, [_clan()])

    body = client.get("/api/v1/clans").json()

    parsed = ClanListResponse.model_validate(body)  # 어긋나면 여기서 터진다
    assert parsed.clans[0].externalId == "#2C8L822LQ"


def test_이름이_없어도_준다(client, fake_db):
    _seed(fake_db, [_clan(display_name=None)])

    clan = client.get("/api/v1/clans").json()["clans"][0]

    assert clan["displayName"] is None
    ClanSchema.model_validate(clan)  # 스펙이 nullable 로 허용한다


def test_CoC_가_주는_값은_응답에도_없다(client, fake_db):
    """마크·레벨·점수가 새어 나가지 않는지 본다.

    사실 이 경로는 구조적으로 새어 나올 수 없다. 스펙에서 생성한 모델을 쓰므로
    거기 없는 필드를 넘겨도 Pydantic 이 걸러낸다(직접 clanLevel 을 넘겨 확인했다).
    응답 키를 model_fields 와 견주는 것도 의미가 없다. 응답이 그 모델에서
    나오므로 언제나 같기 때문이다.

    그래도 남겨 두는 까닭은 의도를 적어 두기 위해서다. 나중에 누가 사전을
    손수 만드는 방식으로 되돌리면 그때는 이 테스트가 실제로 잡는다.
    """
    _seed(fake_db, [_clan()])

    clan = client.get("/api/v1/clans").json()["clans"][0]

    for leaked in ("badgeUrls", "clanLevel", "clanPoints", "warWins", "memberList"):
        assert leaked not in clan, f"{leaked} 가 응답에 새어 나왔습니다"
