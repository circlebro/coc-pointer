"""Turn stored data into the static site under ``site/``."""

from __future__ import annotations

import shutil
from collections.abc import Iterable
from dataclasses import dataclass
from datetime import UTC, datetime
from importlib import resources
from pathlib import Path

from jinja2 import Environment, PackageLoader, select_autoescape

from coc_pointer.config import ClanConfig
from coc_pointer.models import ClanMember, ClanSnapshot, War
from coc_pointer.scoring import (
    KST,
    RULES,
    MemberMonth,
    RankedMember,
    aggregate_month,
    group_wars_by_month,
    rank_month,
    roster,
    sort_key,
)
from coc_pointer.storage import load_clan_snapshot, load_wars

ROLE_KO = {"leader": "대표", "coLeader": "공동 대표", "admin": "장로", "member": "멤버"}
ROLE_ORDER = {"leader": 0, "coLeader": 1, "admin": 2, "member": 3}


@dataclass(frozen=True)
class MonthView:
    key: str
    label: str
    wars: list[War]
    ranked: list[RankedMember]
    roster: list[RankedMember]
    regular_wars: list[War]
    cwl_wars: list[War]
    regular_grid: list[tuple[RankedMember, list[str]]]  # participants only
    cwl_grid: list[tuple[RankedMember, list[str]]]  # participants only
    cwl_participants: list[MemberMonth]  # actual CWL roster this month, CWL record only
    next_label: str  # month whose CWL roster this month's scores decide


def war_cell(war: War, tag: str) -> str:
    """``"3/2"`` for attacks made, ``x`` for each missed attack, ``""`` if not in the war."""
    for m in war.members:
        if m.tag == tag:
            stars = [str(a.stars) for a in m.attacks]
            stars += ["x"] * (war.attacks_per_member - len(stars))
            return "/".join(stars)
    return ""


def month_label(key: str) -> str:
    year, month = key.split("-")
    return f"{year}년 {int(month)}월"


def next_month_label(key: str) -> str:
    year, month = (int(x) for x in key.split("-"))
    if month == 12:
        year, month = year + 1, 1
    else:
        month += 1
    return f"{year}년 {month}월"


def build_month_view(
    key: str, wars: list[War], config: ClanConfig, clan_members: Iterable[ClanMember] = ()
) -> MonthView:
    ranked = rank_month(aggregate_month(wars, clan_members), config)
    regular_wars = [w for w in wars if w.war_type == "regular"]
    cwl_wars = [w for w in wars if w.war_type == "cwl"]
    return MonthView(
        key=key,
        label=month_label(key),
        wars=wars,
        ranked=ranked,
        roster=roster(ranked),
        regular_wars=regular_wars,
        cwl_wars=cwl_wars,
        regular_grid=_participant_grid(ranked, regular_wars),
        cwl_grid=_participant_grid(ranked, cwl_wars),
        cwl_participants=sorted(
            aggregate_month(cwl_wars, war_types=frozenset({"cwl"})), key=sort_key
        ),
        next_label=next_month_label(key),
    )


def _participant_grid(
    ranked: list[RankedMember], wars: list[War]
) -> list[tuple[RankedMember, list[str]]]:
    """One row per member who was on the roster of at least one of ``wars``."""
    rows = []
    for r in ranked:
        cells = [war_cell(w, r.member.tag) for w in wars]
        if any(cells):
            rows.append((r, cells))
    return rows


def _kst(dt: datetime, fmt: str) -> str:
    return dt.astimezone(KST).strftime(fmt)


def _env() -> Environment:
    env = Environment(
        loader=PackageLoader("coc_pointer", "templates"),
        autoescape=select_autoescape(["html"]),
        trim_blocks=True,
        lstrip_blocks=True,
    )
    env.filters["kst"] = _kst
    env.filters["role_ko"] = lambda role: ROLE_KO.get(role, role)
    return env


def _sorted_members(snapshot: ClanSnapshot | None) -> list[ClanMember]:
    if snapshot is None:
        return []
    return sorted(snapshot.members, key=lambda m: (ROLE_ORDER.get(m.role, 9), -m.trophies, m.name))


def build_site(
    data_dir: Path, config: ClanConfig, out_dir: Path, now: datetime | None = None
) -> list[Path]:
    wars = load_wars(data_dir)
    snapshot = load_clan_snapshot(data_dir)
    clan_members = snapshot.members if snapshot else ()
    months = [
        build_month_view(k, ws, config, clan_members) for k, ws in group_wars_by_month(wars).items()
    ]
    latest = months[-1] if months else None
    generated_at = _kst(now or datetime.now(UTC), "%Y-%m-%d %H:%M")
    clan_name = snapshot.name if snapshot else "클랜"

    env = _env()
    common = {
        "months": months,
        "rules": RULES,
        "generated_at": generated_at,
        "clan_name": clan_name,
    }
    written: list[Path] = []

    def write(rel: str, template: str, **ctx: object) -> None:
        path = out_dir / rel
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(env.get_template(template).render(**common, **ctx), encoding="utf-8")
        written.append(path)

    write("index.html", "index.html", root="", latest=latest)
    for view in months:
        write(f"{view.key}/index.html", "month.html", root="../", view=view)
    write(
        "members/index.html",
        "members.html",
        root="../",
        snapshot=snapshot,
        members=_sorted_members(snapshot),
        config=config,
    )
    css_src = resources.files("coc_pointer").joinpath("templates/style.css")
    css_dst = out_dir / "style.css"
    with resources.as_file(css_src) as src:
        shutil.copyfile(src, css_dst)
    written.append(css_dst)
    return written
