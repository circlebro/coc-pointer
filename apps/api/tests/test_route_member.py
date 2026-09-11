"""클랜원 조회 경로."""

from __future__ import annotations

import asyncio

import pytest
from coc_core.member.models import ClanMember, ClanRole, MemberStatus
from fastapi.testclient import TestClient

from adapters.member_repository import D1MemberRepository
from schemas import Member, MemberListResponse
from worker import app

NOW = "2026-09-10T05:30:00Z"


class FakeEnv:
    API_VERSION = "0.5.0"
    COC_API_TOKEN = "test-token"
    CLAN_TAG = "#2C8L822LQ"

    def __init__(self, db) -> None:
        self.DB = db


def _member(tag: str, name: str, **overrides) -> ClanMember:
    base = {
        "id": f"uuid-{tag.lstrip('#')}",
        "tag": tag,
        "name": name,
        "role": ClanRole.MEMBER,
        "status": MemberStatus.ACTIVE,
        "townhall": 16,
        "trophies": 4200,
        "donations": 100,
        "donations_received": 50,
        "description": None,
        "created_at": NOW,
        "updated_at": NOW,
    }
    base.update(overrides)
    return ClanMember(**base)


@pytest.fixture
def client(fake_db):
    """실제 Workers 처럼 scope 에 env 를 넣어 주는 얇은 래퍼로 앱을 감싼다."""
    env = FakeEnv(fake_db)

    async def with_env(scope, receive, send):
        scope["env"] = env
        await app(scope, receive, send)

    return TestClient(with_env)


def _seed(fake_db, members):
    asyncio.run(D1MemberRepository(fake_db).upsert_many(members))


def test_아무도_없으면_빈_목록(client):
    body = client.get("/api/v1/members").json()

    assert body == {"members": []}


def test_이름_순으로_돌려준다(client, fake_db):
    _seed(fake_db, [_member("#B", "히로"), _member("#A", "도토리")])

    body = client.get("/api/v1/members").json()

    assert [m["name"] for m in body["members"]] == ["도토리", "히로"]


def test_계약대로_캐멀케이스로_준다(client, fake_db):
    _seed(fake_db, [_member("#A", "도토리", role=ClanRole.ADMIN)])

    member = client.get("/api/v1/members").json()["members"][0]

    assert member["tag"] == "#A"
    assert member["role"] == "ADMIN"
    assert member["status"] == "ACTIVE"
    assert member["donationsReceived"] == 50
    assert member["createdAt"] == NOW
    assert "donations_received" not in member


def test_태그로_좁힌다(client, fake_db):
    _seed(fake_db, [_member("#A", "도토리"), _member("#B", "히로")])

    body = client.get("/api/v1/members", params={"tag": "#B"}).json()

    assert [m["name"] for m in body["members"]] == ["히로"]


def test_없는_태그면_빈_목록(client, fake_db):
    _seed(fake_db, [_member("#A", "도토리")])

    body = client.get("/api/v1/members", params={"tag": "#없음"}).json()

    assert body == {"members": []}


def test_응답_키가_계약과_정확히_같다(client, fake_db):
    """계약에서 생성한 모델과 실제 응답의 키가 어긋나지 않는지 본다.

    이 경로는 생성 모델을 쓰지 않고 _to_response 로 사전을 손수 만든다.
    생성 모델이 id 를 UUID, createdAt 을 AwareDatetime 으로 선언하는데 우리
    도메인은 둘 다 문자열로 다루기 때문이다. 그래서 계약을 고치고 모델을 다시
    생성해도 _to_response 는 저절로 따라가지 않는다. 이 테스트가 그 둘을 잇는
    유일한 자리라, 키가 하나라도 어긋나면 여기서 걸린다.
    """
    _seed(fake_db, [_member("#A", "도토리")])

    member = client.get("/api/v1/members").json()["members"][0]

    assert set(member) == set(Member.model_fields)


def test_응답_봉투가_계약과_같다(client):
    """목록을 감싸는 바깥 모양도 계약이 정한 그대로여야 한다."""
    body = client.get("/api/v1/members").json()

    assert set(body) == set(MemberListResponse.model_fields)
