"""Clan war activity score and CWL roster selection (rules effective 2026-09).

점수 규칙 (엑셀 "클랜 리그전 30인 선발 기준 안내" 그대로):

1. 공격 1회 = 기본 5점 + 그 공격에서 딴 별 수 (최대 8점). 미공격 = 0점.
2. 점수에는 일반 클랜전만 반영한다. 공격 기회 = 참가한 일반 클랜전마다 2회. 명단에 없으면
   기회 없음. 리그전(CWL)은 수집하고 기록표에 보여 주되 점수·선발에는 포함하지 않는다.
3. 월 점수 = (5 × 공격 횟수 + 별 총합) ÷ (8 × 공격 기회) × 100.
   별 평균 = 별 총합 ÷ 공격 기회.
4. 월 귀속 = 클랜전 종료 시각을 한국 시간(Asia/Seoul)으로 바꾼 달.
5. 커트라인 = 해당 월 공격 10회 이상 그리고 점수 70점 이상. 정예에게도 동일 적용.
6. 선발 = 커트라인을 넘은 정예 멤버(점수순) 먼저, 남은 자리를 커트라인을 넘은
   일반 멤버 점수순으로 채워 총 30명. 동점은 별 총합 → 공격 횟수 → 닉네임 순.
7. 부캐(alts)는 정예가 될 수 없다. 제외(excluded) 멤버는 표시되지만 선발되지 않는다.
   경고(warnings)는 표시만 하고 점수에 영향이 없다.

이 모듈은 외부 호출이 없는 순수 계산이다. ``RULES``가 화면에 표시되는 유일한 규칙 문구다.
"""

from __future__ import annotations

from collections.abc import Iterable
from dataclasses import dataclass
from datetime import UTC, datetime
from zoneinfo import ZoneInfo

from coc_pointer.config import ClanConfig
from coc_pointer.models import ClanMember, War

BASE_POINTS = 5
MAX_POINTS_PER_ATTACK = 8
MIN_ATTACKS = 10
MIN_SCORE = 70.0
ROSTER_SIZE = 30
SCORED_WAR_TYPES = frozenset({"regular"})  # CWL is recorded but never scored
KST = ZoneInfo("Asia/Seoul")

RULES: tuple[str, ...] = (
    "공격 1회 = 기본 5점 + 획득한 별 수 (최대 8점). 미공격 = 0점.",
    "월 점수 = (5 × 공격 횟수 + 별 총합) ÷ (8 × 공격 기회) × 100. "
    "일반 클랜전만 반영하며 공격 기회는 클랜전당 2회. "
    "리그전은 기록표에만 표시하고 점수에 넣지 않음.",
    "커트라인: 해당 월 공격 10회 이상, 점수 70점 이상. 정예 멤버에게도 동일하게 적용.",
    "선발 순서: 커트라인을 넘은 정예 멤버를 먼저 넣고, 남은 자리를 점수 높은 순으로 채워 총 30명.",
    "부캐는 정예 멤버가 될 수 없음. 제외 멤버는 표에 보이지만 선발되지 않음. "
    "경고 횟수는 표시만 하고 점수에 영향 없음.",
    "클랜전의 월 귀속은 종료 시각(한국 시간) 기준.",
)


def month_key(dt: datetime) -> str:
    """Return ``YYYY-MM`` of ``dt`` in Korea time."""
    return dt.astimezone(KST).strftime("%Y-%m")


@dataclass(frozen=True)
class MemberMonth:
    """One member's aggregated war activity for one month."""

    tag: str
    name: str
    townhall: int
    attacks: int
    opportunities: int
    stars: int

    @property
    def missed(self) -> int:
        return self.opportunities - self.attacks

    @property
    def star_avg(self) -> float:
        return self.stars / self.opportunities if self.opportunities else 0.0

    @property
    def score(self) -> float:
        if not self.opportunities:
            return 0.0
        earned = BASE_POINTS * self.attacks + self.stars
        return earned / (MAX_POINTS_PER_ATTACK * self.opportunities) * 100


def passes_cutline(m: MemberMonth) -> bool:
    return m.attacks >= MIN_ATTACKS and m.score >= MIN_SCORE


def group_wars_by_month(wars: Iterable[War]) -> dict[str, list[War]]:
    grouped: dict[str, list[War]] = {}
    for w in sorted(wars, key=lambda w: w.end_time):
        grouped.setdefault(month_key(w.end_time), []).append(w)
    return dict(sorted(grouped.items()))


def aggregate_month(
    wars: Iterable[War], clan_members: Iterable[ClanMember] = ()
) -> list[MemberMonth]:
    """Sum attacks/opportunities/stars per member across ``wars`` (assumed same month).

    Only wars whose type is in ``SCORED_WAR_TYPES`` count; CWL wars are ignored here.

    ``clan_members`` (usually the current clan snapshot) adds a zero row for every clan member
    who took part in none of the wars, so the monthly table lists the whole clan.
    Names and townhalls seen in a war take precedence over the snapshot's.
    """
    attacks: dict[str, int] = {}
    opportunities: dict[str, int] = {}
    stars: dict[str, int] = {}
    latest: dict[str, tuple[datetime, str, int]] = {}
    for w in wars:
        if w.war_type not in SCORED_WAR_TYPES:
            continue
        for m in w.members:
            attacks[m.tag] = attacks.get(m.tag, 0) + len(m.attacks)
            opportunities[m.tag] = opportunities.get(m.tag, 0) + w.attacks_per_member
            stars[m.tag] = stars.get(m.tag, 0) + sum(a.stars for a in m.attacks)
            if m.tag not in latest or w.end_time > latest[m.tag][0]:
                latest[m.tag] = (w.end_time, m.name, m.townhall)
    for cm in clan_members:
        if cm.tag not in attacks:
            attacks[cm.tag] = opportunities[cm.tag] = stars[cm.tag] = 0
            latest[cm.tag] = (datetime.min.replace(tzinfo=UTC), cm.name, cm.townhall)
    return [
        MemberMonth(
            tag=tag,
            name=latest[tag][1],
            townhall=latest[tag][2],
            attacks=attacks[tag],
            opportunities=opportunities[tag],
            stars=stars[tag],
        )
        for tag in sorted(attacks)
    ]


@dataclass(frozen=True)
class RankedMember:
    rank: int
    member: MemberMonth
    is_elite: bool
    is_alt: bool
    is_excluded: bool
    warnings: int
    meets_cutline: bool
    selection: str | None  # "정예" | "선발" | None


def sort_key(m: MemberMonth) -> tuple[float, int, int, str]:
    return (-m.score, -m.stars, -m.attacks, m.name)


def rank_month(members: Iterable[MemberMonth], config: ClanConfig) -> list[RankedMember]:
    """Order members by score and mark who is selected for the CWL roster."""
    ordered = sorted(members, key=sort_key)

    def eligible(m: MemberMonth) -> bool:
        return passes_cutline(m) and not config.is_excluded(m.tag)

    selection: dict[str, str] = {}
    for m in ordered:
        if config.is_elite(m.tag) and eligible(m) and len(selection) < ROSTER_SIZE:
            selection[m.tag] = "정예"
    for m in ordered:
        if len(selection) >= ROSTER_SIZE:
            break
        if m.tag not in selection and eligible(m):
            selection[m.tag] = "선발"

    return [
        RankedMember(
            rank=i,
            member=m,
            is_elite=config.is_elite(m.tag),
            is_alt=config.is_alt(m.tag),
            is_excluded=config.is_excluded(m.tag),
            warnings=config.warning_count(m.tag),
            meets_cutline=passes_cutline(m),
            selection=selection.get(m.tag),
        )
        for i, m in enumerate(ordered, start=1)
    ]


def roster(ranked: Iterable[RankedMember]) -> list[RankedMember]:
    """Final roster: elite first, then selected, each in score order, ranks renumbered."""
    rows = list(ranked)
    chosen = [r for r in rows if r.selection == "정예"] + [r for r in rows if r.selection == "선발"]
    return [
        RankedMember(
            rank=i,
            member=r.member,
            is_elite=r.is_elite,
            is_alt=r.is_alt,
            is_excluded=r.is_excluded,
            warnings=r.warnings,
            meets_cutline=r.meets_cutline,
            selection=r.selection,
        )
        for i, r in enumerate(chosen, start=1)
    ]
