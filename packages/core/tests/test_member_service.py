"""클랜원 서비스.

가짜 대역을 클래스로 만들어 넣는다. 모킹 라이브러리를 쓰지 않는다.
"""

from __future__ import annotations

from coc_core.member.models import ClanMember, ClanRole, MemberStatus
from coc_core.member.service import MemberService

NOW = "2026-09-10T05:30:00Z"


class FakeSource:
    """CoC API 대역. 받아 온 그대로의 값을 흉내낸다."""

    def __init__(self, raw: list[dict]) -> None:
        self.raw = raw

    async def fetch_members(self) -> list[dict]:
        return self.raw


class FakeRepository:
    """저장소 대역. 태그를 열쇠로 담아 둔다."""

    def __init__(self, existing: list[ClanMember] | None = None) -> None:
        self.rows: dict[str, ClanMember] = {m.tag: m for m in (existing or [])}
        self.marked_inactive: list[str] = []

    async def find_all(self) -> list[ClanMember]:
        return list(self.rows.values())

    async def find_by_tag(self, tag: str) -> ClanMember | None:
        return self.rows.get(tag)

    async def upsert_many(self, members: list[ClanMember]) -> int:
        added = 0
        for m in members:
            if m.tag not in self.rows:
                added += 1
            self.rows[m.tag] = m
        return added

    async def mark_inactive(self, tags: list[str], now: str) -> int:
        for tag in tags:
            row = self.rows.get(tag)
            if row is not None:
                self.rows[tag] = ClanMember(**{**row.__dict__, "status": MemberStatus.INACTIVE})
                self.marked_inactive.append(tag)
        return len(tags)


def _raw(tag: str, name: str, role: str = "member") -> dict:
    return {
        "tag": tag,
        "name": name,
        "role": role,
        "townHallLevel": 16,
        "trophies": 4200,
        "donations": 100,
        "donationsReceived": 50,
    }


async def test_처음_동기화하면_모두_새로_들어온다():
    service = MemberService(
        repository=FakeRepository(),
        source=FakeSource([_raw("#A", "도토리"), _raw("#B", "히로")]),
    )

    result = await service.sync(now=NOW)

    assert result.total == 2
    assert result.added == 2
    assert result.left == 0
    assert len(await service.find_all()) == 2


async def test_모르는_직책이_와도_나머지는_저장된다():
    service = MemberService(
        repository=FakeRepository(),
        source=FakeSource([_raw("#A", "도토리", "veteran"), _raw("#B", "히로", "member")]),
    )

    result = await service.sync(now=NOW)

    assert result.total == 2
    assert result.unknown_roles == {"veteran": 1}
    by_tag = {m.tag: m for m in await service.find_all()}
    assert by_tag["#A"].role == ClanRole.UNKNOWN
    assert by_tag["#B"].role == ClanRole.MEMBER


async def test_목록에서_사라지면_INACTIVE_로_내린다():
    repository = FakeRepository()
    service = MemberService(repository=repository, source=FakeSource([_raw("#A", "도토리")]))
    await service.sync(now=NOW)

    service_after = MemberService(repository=repository, source=FakeSource([]))
    result = await service_after.sync(now=NOW)

    assert result.left == 1
    assert repository.rows["#A"].status == MemberStatus.INACTIVE
    assert repository.rows["#A"].tag == "#A"  # 지우지 않는다


async def test_돌아온_사람은_다시_ACTIVE():
    repository = FakeRepository()
    service = MemberService(repository=repository, source=FakeSource([_raw("#A", "도토리")]))
    await service.sync(now=NOW)
    await MemberService(repository=repository, source=FakeSource([])).sync(now=NOW)

    await MemberService(repository=repository, source=FakeSource([_raw("#A", "도토리")])).sync(
        now=NOW
    )

    assert repository.rows["#A"].status == MemberStatus.ACTIVE


async def test_태그로_한_명을_찾는다():
    service = MemberService(
        repository=FakeRepository(),
        source=FakeSource([_raw("#A", "도토리"), _raw("#B", "히로")]),
    )
    await service.sync(now=NOW)

    found = await service.find_by_tag("#B")

    assert found is not None
    assert found.name == "히로"
    assert await service.find_by_tag("#없음") is None
