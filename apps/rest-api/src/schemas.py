# 이 파일은 api/openapi.yaml 에서 생성되었다. 손으로 고치지 마라.

from __future__ import annotations

from enum import StrEnum
from uuid import UUID

from pydantic import AwareDatetime, BaseModel, Field


class ClanStatus(StrEnum):
    ACTIVE = "ACTIVE"
    INACTIVE = "INACTIVE"


class Clan(BaseModel):
    id: str = Field(
        ...,
        description="우리 식별자(UUID 문자열)",
        examples=["3f2a1b4c-5d6e-4f70-8a91-b2c3d4e5f607"],
    )
    externalId: str = Field(
        ...,
        description="CoC 클랜 태그. 이 값으로 CoC API 를 부른다",
        examples=["#2C8L822LQ"],
    )
    displayName: str | None = Field(
        None,
        description="우리가 붙이는 이름. 첫 동기화 때 채운다",
        examples=["미니언즈"],
    )
    status: ClanStatus
    createdAt: str = Field(
        ...,
        description="처음 본 시각. ISO 8601(UTC)",
        examples=["2026-09-11T07:18:57Z"],
    )
    updatedAt: str = Field(
        ...,
        description="마지막으로 갱신한 시각. ISO 8601(UTC)",
        examples=["2026-09-11T07:18:57Z"],
    )


class ClanListResponse(BaseModel):
    clans: list[Clan]


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
