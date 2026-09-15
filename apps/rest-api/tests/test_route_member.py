"""클랜원 경로."""

from __future__ import annotations

import asyncio

import pytest
from coc_core.member.models import ClanMember, ClanRole, MemberProfile, MemberStatus
from coc_core.member.service import MemberService
from fastapi.testclient import TestClient

from adapters.member_repository import D1MemberRepository
from routes.member import get_member_service
from worker import app

NOW = "2026-09-10T05:30:00Z"
FETCHED = "2026-09-15T08:00:00Z"


def _member(external_id: str, **overrides) -> ClanMember:
    base = {
        "id": f"uuid-{external_id.lstrip('#')}",
        "external_id": external_id,
        "display_name": None,
        "status": MemberStatus.ACTIVE,
        "warnings": 0,
        "description": None,
        "created_at": NOW,
        "updated_at": NOW,
        "synced_at": NOW,
    }
    base.update(overrides)
    return ClanMember(**base)


def _profile(external_id: str, name: str, role: ClanRole = ClanRole.MEMBER) -> MemberProfile:
    return MemberProfile(
        external_id=external_id,
        name=name,
        role=role,
        townhall=16,
        trophies=4200,
        donations=100,
        donations_received=50,
        fetched_at=FETCHED,
    )


class FakeProfiles:
    """CoC 대역.

    ``in_clan`` 은 클랜 응답에 실려 오는 사람들이고, ``elsewhere`` 는 클랜을
    나갔지만 계정이 살아 있는 사람들이다. 둘 다 없으면 계정이 사라진 것이다.
    """

    def __init__(
        self,
        in_clan: dict[str, MemberProfile] | None = None,
        elsewhere: dict[str, MemberProfile] | None = None,
    ) -> None:
        self.in_clan = in_clan or {}
        self.elsewhere = elsewhere or {}
        self.clan_calls = 0
        self.player_calls: list[str] = []

    async def read_clan_profiles(self) -> dict[str, MemberProfile]:
        self.clan_calls += 1
        return dict(self.in_clan)

    async def read_profile(self, external_id: str) -> MemberProfile | None:
        self.player_calls.append(external_id)
        return self.in_clan.get(external_id) or self.elsewhere.get(external_id)


class FakeEnv:
    API_VERSION = "0.7.0"
    COC_API_TOKEN = "test-token"
    CLAN_TAG = "#2C8L822LQ"

    def __init__(self, db) -> None:
        self.DB = db


@pytest.fixture
def profiles() -> FakeProfiles:
    return FakeProfiles()


@pytest.fixture
def client(fake_db, profiles):
    """실제 Workers 처럼 scope 에 env 를 넣어 주는 얇은 래퍼로 앱을 감싼다.

    CoC 는 가짜로 갈아 끼운다. 진짜를 부르면 테스트가 네트워크와 토큰에 기댄다.
    """
    env = FakeEnv(fake_db)

    def fake_service() -> MemberService:
        return MemberService(repository=D1MemberRepository(fake_db), profiles=profiles)

    app.dependency_overrides[get_member_service] = fake_service

    async def with_env(scope, receive, send):
        scope["env"] = env
        await app(scope, receive, send)

    yield TestClient(with_env)
    app.dependency_overrides.clear()


def _seed(fake_db, members):
    asyncio.run(D1MemberRepository(fake_db).register_many(members))


# ---------------------------------------------------------------- 목록


def test_아무도_없으면_빈_목록(client):
    assert client.get("/api/v1/members").json() == {"members": []}


def test_기본_응답은_우리_값만_준다(client, fake_db, profiles):
    """키 자체가 없어야 한다. null 로 채우면 묻지 않은 것과 값이 없는 것이 같아 보인다."""
    _seed(fake_db, [_member("#A")])

    member = client.get("/api/v1/members").json()["members"][0]

    assert set(member) == {
        "id",
        "externalId",
        "displayName",
        "status",
        "warnings",
        "description",
        "createdAt",
        "updatedAt",
    }
    assert profiles.clan_calls == 0  # 청하지 않았으면 CoC 를 부르지 않는다


def test_스펙대로_캐멀케이스로_준다(client, fake_db):
    _seed(fake_db, [_member("#A", display_name="도토리형")])

    member = client.get("/api/v1/members").json()["members"][0]

    assert member["externalId"] == "#A"
    assert member["displayName"] == "도토리형"
    assert member["status"] == "ACTIVE"
    assert member["createdAt"] == NOW
    assert "external_id" not in member


def test_외부_식별자로_좁힌다(client, fake_db):
    _seed(fake_db, [_member("#A"), _member("#B")])

    body = client.get("/api/v1/members", params={"externalId": "#B"}).json()

    assert [m["externalId"] for m in body["members"]] == ["#B"]


def test_없는_식별자면_빈_목록(client, fake_db):
    _seed(fake_db, [_member("#A")])

    body = client.get("/api/v1/members", params={"externalId": "#없음"}).json()

    assert body == {"members": []}


# ---------------------------------------------------------------- 현황


def test_목록에서_현황을_청하면_CoC_를_한_번만_부른다(client, fake_db, profiles):
    """한 명씩 물으면 호출이 사람 수만큼 늘고 Workers 의 하위 요청 한도에 걸린다."""
    _seed(fake_db, [_member("#A"), _member("#B"), _member("#C")])
    profiles.in_clan = {
        "#A": _profile("#A", "도토리"),
        "#B": _profile("#B", "히로"),
        "#C": _profile("#C", "빡곰"),
    }

    body = client.get("/api/v1/members", params={"include": "profile"}).json()

    assert profiles.clan_calls == 1
    assert profiles.player_calls == []
    assert [m["profile"]["name"] for m in body["members"]] == ["도토리", "히로", "빡곰"]


def test_현황은_스펙이_정한_모양으로_온다(client, fake_db, profiles):
    _seed(fake_db, [_member("#A")])
    profiles.in_clan = {"#A": _profile("#A", "도토리", ClanRole.ADMIN)}

    member = client.get("/api/v1/members", params={"include": "profile"}).json()["members"][0]

    assert member["profile"] == {
        "name": "도토리",
        "role": "ADMIN",
        "townhall": 16,
        "trophies": 4200,
        "donations": 100,
        "donationsReceived": 50,
        "fetchedAt": FETCHED,
    }


def test_목록에서_클랜에_없는_사람은_현황이_null(client, fake_db, profiles):
    """클랜 응답에 나간 사람은 실려 오지 않는다. 그 사실을 그대로 내보낸다."""
    _seed(fake_db, [_member("#A"), _member("#B", status=MemberStatus.INACTIVE)])
    profiles.in_clan = {"#A": _profile("#A", "도토리")}
    profiles.elsewhere = {"#B": _profile("#B", "히로")}

    body = client.get("/api/v1/members", params={"include": "profile"}).json()

    by_tag = {m["externalId"]: m for m in body["members"]}
    assert by_tag["#A"]["profile"]["name"] == "도토리"
    assert by_tag["#B"]["profile"] is None
    assert profiles.player_calls == []


def test_한_명은_클랜을_나갔어도_현황이_온다(client, fake_db, profiles):
    """단건은 그 사람만 묻기에 호출이 한 번으로 끝난다."""
    _seed(fake_db, [_member("#B", status=MemberStatus.INACTIVE)])
    profiles.elsewhere = {"#B": _profile("#B", "히로")}

    body = client.get("/api/v1/members/uuid-B", params={"include": "profile"}).json()

    assert body["profile"]["name"] == "히로"
    assert profiles.player_calls == ["#B"]


def test_계정이_사라졌으면_현황이_null(client, fake_db, profiles):
    """우리가 아는 것은 태그뿐이며 없는 이름을 지어내지 않는다."""
    _seed(fake_db, [_member("#B", status=MemberStatus.INACTIVE)])

    body = client.get("/api/v1/members/uuid-B", params={"include": "profile"}).json()

    assert body["externalId"] == "#B"
    assert body["profile"] is None


def test_청하지_않으면_단건도_CoC_를_부르지_않는다(client, fake_db, profiles):
    _seed(fake_db, [_member("#A")])

    body = client.get("/api/v1/members/uuid-A").json()

    assert "profile" not in body
    assert profiles.player_calls == []


def test_모르는_include_는_400(client, fake_db):
    """조용히 버리면 오타인지 값이 없는 것인지 부르는 쪽이 알 수 없다."""
    _seed(fake_db, [_member("#A")])

    response = client.get("/api/v1/members", params={"include": "league"})

    assert response.status_code == 400
    assert "league" in response.json()["detail"]


def test_빈_include_는_기본_응답과_같다(client, fake_db):
    _seed(fake_db, [_member("#A")])

    body = client.get("/api/v1/members", params={"include": ""}).json()

    assert "profile" not in body["members"][0]


# ---------------------------------------------------------------- 단건


def test_우리_식별자로_한_명을_준다(client, fake_db):
    _seed(fake_db, [_member("#A"), _member("#B")])

    response = client.get("/api/v1/members/uuid-B")

    assert response.status_code == 200
    assert response.json()["externalId"] == "#B"


def test_없는_식별자면_404(client, fake_db):
    _seed(fake_db, [_member("#A")])

    response = client.get("/api/v1/members/uuid-없음")

    assert response.status_code == 404
    assert "detail" in response.json()


# ---------------------------------------------------------------- 수정


def test_표기를_고친다(client, fake_db):
    _seed(fake_db, [_member("#A")])

    response = client.patch(
        "/api/v1/members/uuid-A",
        json={"displayName": "도토리형", "description": "부캐 아님"},
    )

    assert response.status_code == 200
    body = response.json()
    assert body["displayName"] == "도토리형"
    assert body["description"] == "부캐 아님"
    assert client.get("/api/v1/members/uuid-A").json()["displayName"] == "도토리형"


def test_보내지_않은_값은_그대로다(client, fake_db):
    _seed(fake_db, [_member("#A", description="부캐 아님")])

    body = client.patch("/api/v1/members/uuid-A", json={"warnings": 2}).json()

    assert body["warnings"] == 2
    assert body["description"] == "부캐 아님"


def test_null_을_보내면_비운다(client, fake_db):
    """표기를 지우면 화면은 CoC 이름으로 돌아간다."""
    _seed(fake_db, [_member("#A", display_name="도토리형")])

    body = client.patch("/api/v1/members/uuid-A", json={"displayName": None}).json()

    assert body["displayName"] is None


def test_고친_뒤_갱신_시각이_올라간다(client, fake_db):
    _seed(fake_db, [_member("#A")])

    body = client.patch("/api/v1/members/uuid-A", json={"warnings": 1}).json()

    assert body["updatedAt"] > NOW
    assert body["createdAt"] == NOW


def test_CoC_가_주인인_값은_고칠_수_없다(client, fake_db, profiles):
    """이름을 보내도 무시한다. 우리 표에 그 열이 아예 없다."""
    _seed(fake_db, [_member("#A")])
    profiles.in_clan = {"#A": _profile("#A", "도토리")}

    body = client.patch(
        "/api/v1/members/uuid-A",
        params={"include": "profile"},
        json={"warnings": 1, "name": "바뀐이름"},
    ).json()

    assert body["warnings"] == 1
    assert body["profile"]["name"] == "도토리"


def test_등급은_고칠_수_없다(client, fake_db):
    """등급은 이번 달 점수가 정하는 값이라 수정 본문에 자리가 없다.

    모르는 키라 조용히 무시되고, 남은 값이 없으므로 400 이 된다.
    """
    _seed(fake_db, [_member("#A")])

    assert client.patch("/api/v1/members/uuid-A", json={"grade": "FIXED"}).status_code == 400


def test_아는_값이_하나도_없으면_400(client, fake_db):
    _seed(fake_db, [_member("#A")])

    assert client.patch("/api/v1/members/uuid-A", json={"name": "바뀐이름"}).status_code == 400


def test_고칠_값을_하나도_안_보내면_400(client, fake_db):
    _seed(fake_db, [_member("#A")])

    assert client.patch("/api/v1/members/uuid-A", json={}).status_code == 400


def test_비울_수_없는_값에_null_을_보내면_400(client, fake_db):
    _seed(fake_db, [_member("#A")])

    assert client.patch("/api/v1/members/uuid-A", json={"warnings": None}).status_code == 400


def test_경고_횟수가_음수면_422(client, fake_db):
    """스펙이 minimum: 0 이라 생성 모델이 먼저 거른다."""
    _seed(fake_db, [_member("#A")])

    assert client.patch("/api/v1/members/uuid-A", json={"warnings": -1}).status_code == 422


def test_없는_사람을_고치면_404(client, fake_db):
    _seed(fake_db, [_member("#A")])

    response = client.patch("/api/v1/members/uuid-없음", json={"warnings": 1})

    assert response.status_code == 404


def test_자격_증명이_없으면_현황_요청은_503(fake_db):
    """500 은 "우리 잘못인데 무엇인지 모른다"는 뜻이라 설정이 빠진 사실을 가린다."""
    env = FakeEnv(fake_db)

    def service_without_coc() -> MemberService:
        return MemberService(repository=D1MemberRepository(fake_db))

    app.dependency_overrides[get_member_service] = service_without_coc

    async def with_env(scope, receive, send):
        scope["env"] = env
        await app(scope, receive, send)

    try:
        client = TestClient(with_env)
        _seed(fake_db, [_member("#A")])

        assert client.get("/api/v1/members").status_code == 200  # 명단은 답한다
        response = client.get("/api/v1/members", params={"include": "profile"})

        assert response.status_code == 503
        assert "자격 증명" in response.json()["detail"]
    finally:
        app.dependency_overrides.clear()
