# 이 파일은 contracts/openapi.yaml 에서 생성되었다. 손으로 고치지 마라.

from __future__ import annotations

from enum import StrEnum
from uuid import UUID

from pydantic import AwareDatetime, BaseModel, Field


class ClanRole(StrEnum):
    LEADER = "LEADER"
    COLEADER = "COLEADER"
    ADMIN = "ADMIN"
    MEMBER = "MEMBER"
    UNKNOWN = "UNKNOWN"


class MemberStatus(StrEnum):
    ACTIVE = "ACTIVE"
    INACTIVE = "INACTIVE"


class Member(BaseModel):
    id: UUID = Field(..., description="우리 식별자")
    tag: str = Field(..., description="CoC 플레이어 태그", examples=["#2ABC123"])
    name: str
    role: ClanRole
    status: MemberStatus
    townhall: int | None = None
    trophies: int | None = None
    donations: int | None = None
    donationsReceived: int | None = None
    description: str | None = Field(None, description="관리자 메모. 동기화가 덮어쓰지 않는다")
    createdAt: AwareDatetime
    updatedAt: AwareDatetime


class MemberListResponse(BaseModel):
    members: list[Member]
