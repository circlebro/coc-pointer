"""클랜원 경로.

응답 모양은 api/openapi.yaml 이 정하고, 여기서는 스펙에서 생성한 모델을
그대로 쓴다. 도메인 자료형을 그 모양으로 옮기는 일만 한다.

기본 응답은 우리 DB 한 행만 읽는다. CoC 가 주인인 값(이름·직책·홀·트로피·기부)은
``include=profile`` 로 부를 때만 실린다. 명단만 필요한 요청에 그 비용을 얹지
않으려는 것이며, 앞으로 사본을 걷어내면 그 덩어리가 진짜 CoC 호출이 된다.

고칠 수 있는 값은 사람이 정하는 셋뿐이다(표기·경고 횟수·메모). 이름이나 직책은
CoC 가 주인이라 여기서 받지 않고, 등급은 그달 점수가 정하는 값이라 받지 않는다.
"""

from __future__ import annotations

from datetime import UTC, datetime
from typing import Annotated

from coc_core.member.models import ClanMember
from coc_core.member.service import UNSET, MemberService
from fastapi import APIRouter, Depends, HTTPException, Query, Request

from adapters.member_repository import D1MemberRepository
from schemas import Member as MemberSchema
from schemas import MemberInclude, MemberListResponse, MemberProfile, MemberUpdate

router = APIRouter(prefix="/api/v1", tags=["members"])


def get_member_service(request: Request) -> MemberService:
    """요청마다 조립한다. 스프링 컨테이너가 하던 일을 여기서 직접 한다.

    CoC API 를 부를 일이 없으므로 source 를 넘기지 않는다. 동기화는 cli.py 가
    따로 조립한다.
    """
    env = request.scope["env"]
    return MemberService(repository=D1MemberRepository(env.DB))


MemberSvc = Annotated[MemberService, Depends(get_member_service)]

IncludeQuery = Annotated[
    str | None,
    Query(
        alias="include",
        description="함께 실을 덩어리. 쉼표로 여럿 적는다. 지금은 profile 하나뿐이다",
        examples=["profile"],
    ),
]


def parse_include(raw: str | None) -> set[MemberInclude]:
    """``?include=profile`` 을 갈라 읽는다.

    스펙이 style: form, explode: false 로 적혀 있어 쉼표로 이어 온다. 모르는
    이름은 400 으로 거절한다. 조용히 버리면 부르는 쪽은 덩어리가 빠진 것을
    오타 때문인지 값이 없어서인지 구분할 수 없다.
    """
    if raw is None:
        return set()

    chosen: set[MemberInclude] = set()
    for name in (part.strip() for part in raw.split(",")):
        if not name:
            continue
        try:
            chosen.add(MemberInclude(name))
        except ValueError:
            allowed = ", ".join(sorted(m.value for m in MemberInclude))
            raise HTTPException(
                status_code=400,
                detail=f"모르는 include 값입니다: {name} (쓸 수 있는 값: {allowed})",
            ) from None
    return chosen


def _now() -> str:
    """지금 시각. ISO 8601(UTC)."""
    return datetime.now(UTC).strftime("%Y-%m-%dT%H:%M:%SZ")


def _to_profile(member: ClanMember) -> MemberProfile:
    """CoC 가 주인인 값만 따로 묶는다."""
    return MemberProfile(
        name=member.name,
        role=member.role,
        townhall=member.townhall,
        trophies=member.trophies,
        donations=member.donations,
        donationsReceived=member.donations_received,
        fetchedAt=member.synced_at,
    )


def _to_schema(member: ClanMember, chosen: set[MemberInclude]) -> MemberSchema:
    """도메인 자료형을 스펙이 정한 모양으로.

    고르지 않은 덩어리는 아예 넘기지 않는다. 경로가
    ``response_model_exclude_unset`` 로 응답하므로, 넘기지 않은 필드는 키까지
    사라진다. null 로 채우면 "묻지 않았다"와 "값이 없다"가 같아 보인다.
    """
    fields = {
        "id": member.id,
        "externalId": member.external_id,
        "displayName": member.display_name,
        "status": member.status,
        "warnings": member.warnings,
        "description": member.description,
        "createdAt": member.created_at,
        "updatedAt": member.updated_at,
    }
    if MemberInclude.profile in chosen:
        fields["profile"] = _to_profile(member)
    return MemberSchema(**fields)


@router.get("/members", response_model_exclude_unset=True)
async def list_members(
    service: MemberSvc,
    include: IncludeQuery = None,
    externalId: Annotated[str | None, Query(description="CoC 플레이어 태그로 좁힌다")] = None,
) -> MemberListResponse:
    """클랜원 목록. 나간 사람(INACTIVE)도 포함한다."""
    chosen = parse_include(include)
    if externalId is not None:
        found = await service.find_by_external_id(externalId)
        return MemberListResponse(members=[_to_schema(found, chosen)] if found else [])
    return MemberListResponse(members=[_to_schema(m, chosen) for m in await service.find_all()])


@router.get("/members/{memberId}", response_model_exclude_unset=True)
async def get_member(
    memberId: str, service: MemberSvc, include: IncludeQuery = None
) -> MemberSchema:
    """클랜원 한 명. 우리 식별자로 찾는다."""
    chosen = parse_include(include)
    found = await service.find_by_id(memberId)
    if found is None:
        raise HTTPException(status_code=404, detail="그 클랜원이 없습니다")
    return _to_schema(found, chosen)


@router.patch("/members/{memberId}", response_model_exclude_unset=True)
async def update_member(
    memberId: str,
    body: MemberUpdate,
    service: MemberSvc,
    include: IncludeQuery = None,
) -> MemberSchema:
    """우리가 정하는 값을 고친다.

    보낸 필드만 바꾼다. ``model_fields_set`` 이 요청 본문에 실제로 실려 온 키를
    알려주므로, "안 보냈다"와 "null 을 보냈다"를 가릴 수 있다. 앞은 그대로 두라는
    뜻이고 뒤는 비우라는 뜻이라 서로 다르다.
    """
    chosen = parse_include(include)
    sent = body.model_fields_set
    if not sent:
        raise HTTPException(status_code=400, detail="고칠 값을 하나 이상 보내야 합니다")

    # 스펙에서 경고 횟수는 비울 수 없는 값이다. 다만 생성 모델은 선택 사항인
    # 필드를 모두 ``| None`` 으로 적으므로 null 이 그대로 들어온다. 여기서 막지
    # 않으면 경고 횟수가 없는 클랜원이 만들어진다.
    if "warnings" in sent and body.warnings is None:
        raise HTTPException(status_code=400, detail="warnings 는 비울 수 없습니다")

    updated = await service.update_managed(
        memberId,
        _now(),
        display_name=body.displayName if "displayName" in sent else UNSET,
        warnings=body.warnings if "warnings" in sent else UNSET,
        description=body.description if "description" in sent else UNSET,
    )
    if updated is None:
        raise HTTPException(status_code=404, detail="그 클랜원이 없습니다")
    return _to_schema(updated, chosen)
