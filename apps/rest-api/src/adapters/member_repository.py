"""클랜원 저장소를 D1 으로 구현한다.

클랜원 질의는 이 파일에만 둔다. 도메인은 SQL 을 모르고, 저장소를 갈아 끼우면
여기만 바뀐다.

D1 은 SQLite 라서 표준 SQL 이 그대로 돈다. 다만 부르는 모양이 다르다.

    await db.prepare(SQL).bind(값).all()     # 여러 행. 결과는 .results
    await db.prepare(SQL).bind(값).first()   # 한 행. 없으면 None
    await db.prepare(SQL).bind(값).run()     # 쓰기
"""

from __future__ import annotations

from typing import Any

from coc_core.member.models import ClanMember, ClanRole, MemberGrade, MemberStatus

_COLUMNS = (
    "id, tag, name, role, townhall, trophies, donations, donations_received, "
    "status, grade, grade_reason, warnings, created_at, updated_at, description"
)

_FIND_ALL = f"SELECT {_COLUMNS} FROM clan_members ORDER BY name"

_FIND_BY_TAG = f"SELECT {_COLUMNS} FROM clan_members WHERE tag = ?"

_COUNT_BY_TAG = "SELECT COUNT(*) AS n FROM clan_members WHERE tag = ?"

# description·created_at·grade·grade_reason·warnings 는 갱신하지 않는다.
# 우리가 정하는 값이라 동기화가 덮으면 안 된다. 처음 본 시각도 한 번만 정해진다.
# 등급을 바꾸는 일은 update_grade 가 따로 맡는다.
_UPSERT = """
INSERT INTO clan_members (
  id, tag, name, role, townhall, trophies, donations, donations_received,
  status, grade, grade_reason, warnings, created_at, updated_at, description
)
VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
ON CONFLICT(tag) DO UPDATE SET
  name               = excluded.name,
  role               = excluded.role,
  townhall           = excluded.townhall,
  trophies           = excluded.trophies,
  donations          = excluded.donations,
  donations_received = excluded.donations_received,
  status             = excluded.status,
  updated_at         = excluded.updated_at
"""

_MARK_INACTIVE = "UPDATE clan_members SET status = 'INACTIVE', updated_at = ? WHERE tag = ?"


def _to_member(row: Any) -> ClanMember:
    return ClanMember(
        id=row.id,
        tag=row.tag,
        name=row.name,
        role=ClanRole(row.role),
        status=MemberStatus(row.status),
        grade=MemberGrade(row.grade),
        grade_reason=row.grade_reason,
        warnings=row.warnings,
        townhall=row.townhall,
        trophies=row.trophies,
        donations=row.donations,
        donations_received=row.donations_received,
        description=row.description,
        created_at=row.created_at,
        updated_at=row.updated_at,
    )


class D1MemberRepository:
    """MemberRepository 를 D1 으로 구현한다."""

    def __init__(self, db: Any) -> None:
        self._db = db

    async def find_all(self) -> list[ClanMember]:
        result = await self._db.prepare(_FIND_ALL).all()
        return [_to_member(row) for row in result.results]

    async def find_by_tag(self, tag: str) -> ClanMember | None:
        row = await self._db.prepare(_FIND_BY_TAG).bind(tag).first()
        return _to_member(row) if row is not None else None

    async def upsert_many(self, members: list[ClanMember]) -> int:
        added = 0
        for m in members:
            existing = await self._db.prepare(_COUNT_BY_TAG).bind(m.tag).first()
            if existing is None or existing.n == 0:
                added += 1
            await (
                self._db.prepare(_UPSERT)
                .bind(
                    m.id,
                    m.tag,
                    m.name,
                    str(m.role),
                    m.townhall,
                    m.trophies,
                    m.donations,
                    m.donations_received,
                    str(m.status),
                    str(m.grade),
                    m.grade_reason,
                    m.warnings,
                    m.created_at,
                    m.updated_at,
                    m.description,
                )
                .run()
            )
        return added

    async def mark_inactive(self, tags: list[str], now: str) -> int:
        for tag in tags:
            await self._db.prepare(_MARK_INACTIVE).bind(now, tag).run()
        return len(tags)
