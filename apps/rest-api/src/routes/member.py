"""클랜원 경로.

응답 모양은 api/openapi.yaml 이 정하고, 여기서는 스펙에서 생성한 모델을
그대로 쓴다. 도메인 자료형을 그 모양으로 옮기는 일만 한다.

고칠 수 있는 값은 우리가 정하는 넷뿐이다(등급·등급 사유·경고 횟수·메모).
이름이나 직책은 CoC 가 주인이라 여기서 받지 않는다.
"""

from __future__ import annotations

from datetime import UTC, datetime
from typing import Annotated

from coc_core.member.models import ClanMember
from coc_core.member.service import UNSET, MemberService
from fastapi import APIRouter, Depends, HTTPException, Query, Request

from adapters.member_repository import D1MemberRepository
from schemas import Member as MemberSchema
from schemas import MemberListResponse, MemberUpdate

router = APIRouter(prefix="/api/v1", tags=["members"])


def get_member_service(request: Request) -> MemberService:
    """요청마다 조립한다. 스프링 컨테이너가 하던 일을 여기서 직접 한다.

    CoC API 를 부를 일이 없으므로 source 를 넘기지 않는다. 동기화는 cli.py 가
    따로 조립한다.
    """
    env = request.scope["env"]
    return MemberService(repository=D1MemberRepository(env.DB))


MemberSvc = Annotated[MemberService, Depends(get_member_service)]


def _now() -> str:
    """지금 시각. ISO 8601(UTC)."""
    return datetime.now(UTC).strftime("%Y-%m-%dT%H:%M:%SZ")


def _to_schema(member: ClanMember) -> MemberSchema:
    """도메인 자료형을 스펙이 정한 모양으로."""
    return MemberSchema(
        id=member.id,
        externalId=member.external_id,
        name=member.name,
        role=member.role,
        status=member.status,
        grade=member.grade,
        gradeReason=member.grade_reason,
        warnings=member.warnings,
        townhall=member.townhall,
        trophies=member.trophies,
        donations=member.donations,
        donationsReceived=member.donations_received,
        description=member.description,
        createdAt=member.created_at,
        updatedAt=member.updated_at,
    )


@router.get("/members")
async def list_members(
    service: MemberSvc,
    externalId: Annotated[str | None, Query(description="CoC 플레이어 태그로 좁힌다")] = None,
) -> MemberListResponse:
    """클랜원 목록. 나간 사람(INACTIVE)도 포함한다."""
    if externalId is not None:
        found = await service.find_by_external_id(externalId)
        return MemberListResponse(members=[_to_schema(found)] if found else [])
    return MemberListResponse(members=[_to_schema(m) for m in await service.find_all()])


@router.get("/members/{memberId}")
async def get_member(memberId: str, service: MemberSvc) -> MemberSchema:
    """클랜원 한 명. 우리 식별자로 찾는다."""
    found = await service.find_by_id(memberId)
    if found is None:
        raise HTTPException(status_code=404, detail="그 클랜원이 없습니다")
    return _to_schema(found)


@router.patch("/members/{memberId}")
async def update_member(memberId: str, body: MemberUpdate, service: MemberSvc) -> MemberSchema:
    """우리가 정하는 값을 고친다.

    보낸 필드만 바꾼다. ``model_fields_set`` 이 요청 본문에 실제로 실려 온 키를
    알려주므로, "안 보냈다"와 "null 을 보냈다"를 가릴 수 있다. 앞은 그대로 두라는
    뜻이고 뒤는 비우라는 뜻이라 서로 다르다.
    """
    sent = body.model_fields_set
    if not sent:
        raise HTTPException(status_code=400, detail="고칠 값을 하나 이상 보내야 합니다")

    # 스펙에서 등급과 경고 횟수는 비울 수 없는 값이다. 다만 생성 모델은 선택
    # 사항인 필드를 모두 ``| None`` 으로 적으므로 null 이 그대로 들어온다.
    # 여기서 막지 않으면 등급이 없는 클랜원이 만들어진다.
    for field_name in ("grade", "warnings"):
        if field_name in sent and getattr(body, field_name) is None:
            raise HTTPException(status_code=400, detail=f"{field_name} 은 비울 수 없습니다")

    updated = await service.update_managed(
        memberId,
        _now(),
        grade=body.grade if "grade" in sent else UNSET,
        grade_reason=body.gradeReason if "gradeReason" in sent else UNSET,
        warnings=body.warnings if "warnings" in sent else UNSET,
        description=body.description if "description" in sent else UNSET,
    )
    if updated is None:
        raise HTTPException(status_code=404, detail="그 클랜원이 없습니다")
    return _to_schema(updated)
