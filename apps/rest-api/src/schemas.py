# 이 파일은 api/openapi.yaml 에서 생성되었다. 손으로 고치지 마라.

from __future__ import annotations

from enum import StrEnum

from pydantic import BaseModel, Field, conint


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


class MemberInclude(StrEnum):
    profile = "profile"


class MemberProfile(BaseModel):
    name: str
    role: ClanRole
    townhall: int | None = None
    trophies: int | None = None
    donations: int | None = None
    donationsReceived: int | None = None
    fetchedAt: str = Field(
        ...,
        description="CoC 가 답한 시각. ISO 8601(UTC)",
        examples=["2026-09-14T09:00:00Z"],
    )


class MemberUpdate(BaseModel):
    displayName: str | None = Field(
        None,
        description="사람이 정한 표기. null 을 보내면 지우고 화면은 CoC 이름으로 돌아간다",
        examples=["히로형"],
    )
    warnings: conint(ge=0) | None = Field(None, description="경고 횟수")
    description: str | None = Field(None, description="관리자 메모")


class Error(BaseModel):
    detail: str = Field(..., examples=["그 클랜원이 없습니다"])


class Member(BaseModel):
    id: str = Field(
        ...,
        description="우리 식별자(UUID 문자열)",
        examples=["3f2a1b4c-5d6e-4f70-8a91-b2c3d4e5f607"],
    )
    externalId: str = Field(
        ...,
        description="CoC 플레이어 태그. 이 값으로 CoC API 를 부른다",
        examples=["#2ABC123"],
    )
    displayName: str | None = Field(
        None,
        description="사람이 정한 표기. 아무도 고치지 않았으면 null 이다",
        examples=["히로형"],
    )
    status: MemberStatus
    warnings: int = Field(..., description="경고 횟수. 표시만 하고 점수에 영향을 주지 않는다")
    description: str | None = Field(None, description="관리자 메모. 동기화가 덮어쓰지 않는다")
    createdAt: str = Field(
        ...,
        description="처음 본 시각. ISO 8601(UTC)",
        examples=["2026-09-11T07:18:57Z"],
    )
    updatedAt: str = Field(
        ...,
        description="마지막으로 바뀐 시각. CoC 에서 받은 시각은 profile.fetchedAt 이다",
        examples=["2026-09-11T07:18:57Z"],
    )
    profile: MemberProfile | None = Field(
        None,
        description="부르지 않으면 키가 없고, 불렀는데 null 이면 CoC 에서 볼 수 없다는 뜻이다",
    )


class MemberListResponse(BaseModel):
    members: list[Member]
