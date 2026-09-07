# coc-pointer 구현 계획

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** CoC 공식 API에서 클랜전·리그전 결과를 자동 수집하고, 엑셀 규칙 그대로 월별 점수와 30인 선발 명단을 계산해 GitHub Pages 정적 페이지로 공개한다.

**Architecture:** 수집기(collect) → `data/` JSON 파일 → 계산기(scoring, 순수 함수) → 렌더러(render, Jinja2) → `site/` 정적 HTML. GitHub Actions가 30분마다와 수동 버튼으로 전체 파이프라인을 실행하고, 새 데이터를 커밋한 뒤 Pages에 배포한다. 저장소가 데이터베이스다.

**Tech Stack:** Python 3.14, uv, httpx(API 호출), PyYAML(설정), Jinja2(템플릿), pytest, ruff, GitHub Actions, GitHub Pages.

**Spec:** `docs/superpowers/specs/2026-09-07-coc-pointer-design.md`

## Global Constraints

- Python `>=3.14`. `uv`만 사용하고 `pip`나 시스템 `python3`를 직접 부르지 않는다. 테스트는 `uv run pytest`, 린트는 `uv run ruff check .`와 `uv run ruff format .`.
- API 기본 주소는 RoyaleAPI 프록시 `https://cocproxy.royaleapi.dev/v1`. 모든 요청에 `User-Agent: coc-pointer/0.1` 헤더를 붙인다 (없으면 403).
- 토큰은 환경 변수 `COC_API_TOKEN`으로만 읽는다. 로컬은 git 제외된 `.env`, Actions는 Secrets.
- 클랜 태그는 `#2C8L822LQ`. 플레이어·클랜 태그는 `^#[0-9A-Z]+$` 형식이며, YAML에서는 반드시 따옴표로 감싼다 (`#`은 YAML 주석 기호).
- 점수 = (5 × 공격 횟수 + 별 총합) ÷ (8 × 공격 기회) × 100. 공격 기회는 일반 클랜전 2회, 리그전 1회. 커트라인은 공격 10회 이상·점수 70점 이상. 선발은 정예 우선, 총 30명.
- 월 귀속은 종료 시각을 `Asia/Seoul`로 바꾼 달.
- 커밋 메시지, PR 제목·본문은 한국어로 쓴다. 코드 식별자·주석·로그는 영어.
- 사용자에게 보이는 문구(HTML, CLI 메시지, 오류 메시지)는 한국어.
- 각 커밋 메시지 끝에 다음 두 줄을 붙인다.
  ```
  Co-Authored-By: Claude Fable 5.1 <noreply@anthropic.com>
  Claude-Session: https://claude.ai/code/session_01SEjU63ioVTGGo4ZeJ2B4wU
  ```

---

## 파일 구조

```
src/coc_pointer/
  __init__.py        # main() → cli.main()
  models.py          # Attack, WarMember, War, ClanMember, ClanSnapshot (+ dict 변환)
  config.py          # ClanConfig, load_config, ConfigError
  scoring.py         # 규칙 문구 RULES, MemberMonth, RankedMember, aggregate/rank/roster
  storage.py         # data/ 읽기·쓰기 (wars/*.json, clan.json)
  api.py             # CocApi (httpx), CocApiError
  collect.py         # API 응답 → War/ClanSnapshot 변환, collect() 오케스트레이션
  render.py          # MonthView 구성, Jinja2로 site/ 생성
  cli.py             # `coc-pointer collect|build`, .env 로딩
  templates/
    base.html, index.html, month.html, members.html, _tables.html, style.css
tests/
  helpers.py         # War/WarMember 생성 도우미
  test_models.py, test_config.py, test_scoring.py, test_storage.py,
  test_api.py, test_collect.py, test_render.py, test_cli.py
config/clan.yaml     # 관리자 설정
data/wars/.gitkeep   # 수집 데이터 폴더
.github/workflows/collect.yml
```

각 모듈의 의존 방향: `cli → collect → api, storage, models` / `cli → render → storage, scoring, config, models` / `scoring → models, config`. `scoring`과 `models`는 외부 호출이 없다.

---

### Task 1: 의존성 추가와 자료형 (models.py)

**Files:**
- Modify: `pyproject.toml`
- Create: `src/coc_pointer/models.py`
- Create: `tests/helpers.py`
- Test: `tests/test_models.py`

**Interfaces:**
- Produces:
  - `Attack(order: int, stars: int)` frozen dataclass
  - `WarMember(tag: str, name: str, townhall: int, attacks: tuple[Attack, ...] = ())`
  - `War(war_type: str, start_time: datetime, end_time: datetime, team_size: int, attacks_per_member: int, opponent_tag: str, opponent_name: str, members: tuple[WarMember, ...])` with `.file_name -> str`, `.to_dict() -> dict`, `War.from_dict(d) -> War`
  - `ClanMember(tag, name, role, townhall, trophies, donations, donations_received)`
  - `ClanSnapshot(fetched_at: datetime, name: str, tag: str, members: tuple[ClanMember, ...])` with `.to_dict()`, `ClanSnapshot.from_dict(d)`
  - 시각은 모두 tz-aware UTC `datetime`. 직렬화 형식은 `2026-09-05T14:30:00Z`.
  - `tests/helpers.py`: `member(tag, name, stars=(), townhall=16) -> WarMember`, `war(members, war_type="regular", end="2026-09-05T14:30:00Z", opponent_tag="#OPP1", opponent_name="상대") -> War`

- [ ] **Step 1: 런타임 의존성 추가**

```bash
uv add httpx pyyaml jinja2
```

Expected: `pyproject.toml`의 `dependencies`에 세 항목이 생기고 `uv.lock`이 갱신된다.

- [ ] **Step 2: 테스트 도우미 작성**

`tests/helpers.py`:

```python
"""Builders for War/WarMember used across tests."""

from datetime import UTC, datetime, timedelta

from coc_pointer.models import Attack, War, WarMember


def member(tag: str, name: str, stars: tuple[int, ...] = (), townhall: int = 16) -> WarMember:
    return WarMember(
        tag=tag,
        name=name,
        townhall=townhall,
        attacks=tuple(Attack(order=i, stars=s) for i, s in enumerate(stars, start=1)),
    )


def war(
    members: list[WarMember] | tuple[WarMember, ...],
    war_type: str = "regular",
    end: str = "2026-09-05T14:30:00Z",
    opponent_tag: str = "#OPP1",
    opponent_name: str = "상대",
) -> War:
    end_dt = datetime.strptime(end, "%Y-%m-%dT%H:%M:%SZ").replace(tzinfo=UTC)
    return War(
        war_type=war_type,
        start_time=end_dt - timedelta(days=1),
        end_time=end_dt,
        team_size=len(members),
        attacks_per_member=2 if war_type == "regular" else 1,
        opponent_tag=opponent_tag,
        opponent_name=opponent_name,
        members=tuple(members),
    )
```

- [ ] **Step 3: 실패하는 테스트 작성**

`tests/test_models.py`:

```python
from datetime import UTC, datetime

from helpers import member, war

from coc_pointer.models import ClanMember, ClanSnapshot, War


def test_war_file_name_uses_utc_end_time_type_and_opponent_tag():
    w = war([member("#P1", "도토리", (3, 2))], end="2026-09-05T14:30:00Z", opponent_tag="#2PP0JJ8L")
    assert w.file_name == "2026-09-05T14-30-00Z_regular_2PP0JJ8L.json"


def test_war_round_trips_through_dict():
    w = war([member("#P1", "도토리", (3, 2), townhall=18), member("#P2", "제니")])
    d = w.to_dict()
    assert d["members"][0]["attacks"] == [{"order": 1, "stars": 3}, {"order": 2, "stars": 2}]
    assert d["members"][1]["attacks"] == []
    assert d["end_time"] == "2026-09-05T14:30:00Z"
    assert War.from_dict(d) == w


def test_clan_snapshot_round_trips_through_dict():
    snap = ClanSnapshot(
        fetched_at=datetime(2026, 9, 7, 9, 0, tzinfo=UTC),
        name="미니언즈",
        tag="#2C8L822LQ",
        members=(ClanMember("#P1", "도토리", "coLeader", 18, 5200, 1200, 900),),
    )
    d = snap.to_dict()
    assert d["fetched_at"] == "2026-09-07T09:00:00Z"
    assert d["members"][0]["role"] == "coLeader"
    assert ClanSnapshot.from_dict(d) == snap
```

- [ ] **Step 4: 테스트 실패 확인**

Run: `uv run pytest tests/test_models.py -v`
Expected: FAIL, `ModuleNotFoundError: No module named 'coc_pointer.models'`

- [ ] **Step 5: models.py 구현**

`src/coc_pointer/models.py`:

```python
"""Immutable data types shared by collector, scorer and renderer.

All datetimes are timezone-aware UTC. Serialized form is ``2026-09-05T14:30:00Z``.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime
from typing import Any

WAR_TYPES = ("regular", "cwl")
_ISO = "%Y-%m-%dT%H:%M:%SZ"


def to_iso(dt: datetime) -> str:
    return dt.astimezone(UTC).strftime(_ISO)


def from_iso(text: str) -> datetime:
    return datetime.strptime(text, _ISO).replace(tzinfo=UTC)


@dataclass(frozen=True)
class Attack:
    order: int
    stars: int


@dataclass(frozen=True)
class WarMember:
    tag: str
    name: str
    townhall: int
    attacks: tuple[Attack, ...] = ()


@dataclass(frozen=True)
class War:
    war_type: str
    start_time: datetime
    end_time: datetime
    team_size: int
    attacks_per_member: int
    opponent_tag: str
    opponent_name: str
    members: tuple[WarMember, ...]

    @property
    def file_name(self) -> str:
        stamp = self.end_time.astimezone(UTC).strftime("%Y-%m-%dT%H-%M-%SZ")
        return f"{stamp}_{self.war_type}_{self.opponent_tag.lstrip('#')}.json"

    def to_dict(self) -> dict[str, Any]:
        return {
            "war_type": self.war_type,
            "start_time": to_iso(self.start_time),
            "end_time": to_iso(self.end_time),
            "team_size": self.team_size,
            "attacks_per_member": self.attacks_per_member,
            "opponent": {"tag": self.opponent_tag, "name": self.opponent_name},
            "members": [
                {
                    "tag": m.tag,
                    "name": m.name,
                    "townhall": m.townhall,
                    "attacks": [{"order": a.order, "stars": a.stars} for a in m.attacks],
                }
                for m in self.members
            ],
        }

    @classmethod
    def from_dict(cls, d: dict[str, Any]) -> War:
        return cls(
            war_type=d["war_type"],
            start_time=from_iso(d["start_time"]),
            end_time=from_iso(d["end_time"]),
            team_size=d["team_size"],
            attacks_per_member=d["attacks_per_member"],
            opponent_tag=d["opponent"]["tag"],
            opponent_name=d["opponent"]["name"],
            members=tuple(
                WarMember(
                    tag=m["tag"],
                    name=m["name"],
                    townhall=m["townhall"],
                    attacks=tuple(Attack(a["order"], a["stars"]) for a in m["attacks"]),
                )
                for m in d["members"]
            ),
        )


@dataclass(frozen=True)
class ClanMember:
    tag: str
    name: str
    role: str
    townhall: int
    trophies: int
    donations: int
    donations_received: int


@dataclass(frozen=True)
class ClanSnapshot:
    fetched_at: datetime
    name: str
    tag: str
    members: tuple[ClanMember, ...]

    def to_dict(self) -> dict[str, Any]:
        return {
            "fetched_at": to_iso(self.fetched_at),
            "name": self.name,
            "tag": self.tag,
            "members": [
                {
                    "tag": m.tag,
                    "name": m.name,
                    "role": m.role,
                    "townhall": m.townhall,
                    "trophies": m.trophies,
                    "donations": m.donations,
                    "donations_received": m.donations_received,
                }
                for m in self.members
            ],
        }

    @classmethod
    def from_dict(cls, d: dict[str, Any]) -> ClanSnapshot:
        return cls(
            fetched_at=from_iso(d["fetched_at"]),
            name=d["name"],
            tag=d["tag"],
            members=tuple(
                ClanMember(
                    tag=m["tag"],
                    name=m["name"],
                    role=m["role"],
                    townhall=m["townhall"],
                    trophies=m["trophies"],
                    donations=m["donations"],
                    donations_received=m["donations_received"],
                )
                for m in d["members"]
            ),
        )
```

- [ ] **Step 6: 테스트 통과 확인**

Run: `uv run pytest tests/test_models.py -v`
Expected: 3 passed

- [ ] **Step 7: 린트와 커밋**

```bash
uv run ruff check . && uv run ruff format .
git add pyproject.toml uv.lock src/coc_pointer/models.py tests/helpers.py tests/test_models.py
git commit -m "자료형 정의와 런타임 의존성 추가

War, WarMember, Attack, ClanSnapshot, ClanMember 불변 자료형과 JSON 변환.
httpx, pyyaml, jinja2 의존성 추가.

Co-Authored-By: Claude Fable 5.1 <noreply@anthropic.com>
Claude-Session: https://claude.ai/code/session_01SEjU63ioVTGGo4ZeJ2B4wU"
```

---

### Task 2: 관리자 설정 (config.py)

**Files:**
- Create: `src/coc_pointer/config.py`
- Test: `tests/test_config.py`

**Interfaces:**
- Produces:
  - `ConfigError(ValueError)`
  - `ClanConfig(clan_tag: str, elite: frozenset[str], alts: frozenset[str], excluded: frozenset[str], warnings: dict[str, int])` with `.is_elite(tag)`, `.is_alt(tag)`, `.is_excluded(tag)`, `.warning_count(tag)`. `is_elite`는 부캐이면 False.
  - `load_config(path: Path) -> ClanConfig`

- [ ] **Step 1: 실패하는 테스트 작성**

`tests/test_config.py`:

```python
from pathlib import Path

import pytest

from coc_pointer.config import ClanConfig, ConfigError, load_config


def write(tmp_path: Path, text: str) -> Path:
    p = tmp_path / "clan.yaml"
    p.write_text(text, encoding="utf-8")
    return p


def test_load_full_config(tmp_path):
    p = write(
        tmp_path,
        """
clan_tag: "#2C8L822LQ"
elite:
  - "#AAA1"
  - "#BBB2"
alts:
  - "#BBB2"
excluded:
  - "#CCC3"
warnings:
  "#DDD4": 2
""",
    )
    cfg = load_config(p)
    assert cfg.clan_tag == "#2C8L822LQ"
    assert cfg.is_elite("#AAA1")
    assert not cfg.is_elite("#BBB2"), "alts can never be elite"
    assert cfg.is_alt("#BBB2")
    assert cfg.is_excluded("#CCC3")
    assert cfg.warning_count("#DDD4") == 2
    assert cfg.warning_count("#AAA1") == 0


def test_missing_lists_default_to_empty(tmp_path):
    cfg = load_config(write(tmp_path, 'clan_tag: "#2C8L822LQ"\n'))
    assert cfg == ClanConfig(clan_tag="#2C8L822LQ")


def test_invalid_tag_reports_location(tmp_path):
    p = write(tmp_path, 'clan_tag: "#2C8L822LQ"\nelite:\n  - "#ok1"\n')
    with pytest.raises(ConfigError, match=r"elite\[0\]"):
        load_config(p)


def test_missing_clan_tag(tmp_path):
    with pytest.raises(ConfigError, match="clan_tag"):
        load_config(write(tmp_path, "elite: []\n"))
```

- [ ] **Step 2: 테스트 실패 확인**

Run: `uv run pytest tests/test_config.py -v`
Expected: FAIL, `ModuleNotFoundError: No module named 'coc_pointer.config'`

- [ ] **Step 3: config.py 구현**

`src/coc_pointer/config.py`:

```python
"""Admin-managed settings loaded from config/clan.yaml.

Tags must be quoted in YAML because ``#`` starts a comment.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from pathlib import Path

import yaml

TAG_RE = re.compile(r"^#[0-9A-Z]+$")


class ConfigError(ValueError):
    """Raised when config/clan.yaml is malformed."""


@dataclass(frozen=True)
class ClanConfig:
    clan_tag: str
    elite: frozenset[str] = frozenset()
    alts: frozenset[str] = frozenset()
    excluded: frozenset[str] = frozenset()
    warnings: dict[str, int] = field(default_factory=dict)

    def is_elite(self, tag: str) -> bool:
        return tag in self.elite and tag not in self.alts

    def is_alt(self, tag: str) -> bool:
        return tag in self.alts

    def is_excluded(self, tag: str) -> bool:
        return tag in self.excluded

    def warning_count(self, tag: str) -> int:
        return self.warnings.get(tag, 0)


def _check_tag(value: object, where: str) -> str:
    if not isinstance(value, str) or not TAG_RE.match(value):
        raise ConfigError(
            f"{where}: 잘못된 태그 형식 {value!r}. "
            "태그는 '#'으로 시작하는 대문자·숫자이며 YAML에서 따옴표로 감싸야 합니다."
        )
    return value


def load_config(path: Path) -> ClanConfig:
    raw = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
    if "clan_tag" not in raw:
        raise ConfigError(f"{path}: clan_tag 항목이 없습니다.")

    def tag_set(key: str) -> frozenset[str]:
        items = raw.get(key) or []
        return frozenset(_check_tag(t, f"{key}[{i}]") for i, t in enumerate(items))

    warnings = {
        _check_tag(t, f"warnings.{t}"): int(n) for t, n in (raw.get("warnings") or {}).items()
    }
    return ClanConfig(
        clan_tag=_check_tag(raw["clan_tag"], "clan_tag"),
        elite=tag_set("elite"),
        alts=tag_set("alts"),
        excluded=tag_set("excluded"),
        warnings=warnings,
    )
```

- [ ] **Step 4: 테스트 통과 확인**

Run: `uv run pytest tests/test_config.py -v`
Expected: 4 passed

- [ ] **Step 5: 린트와 커밋**

```bash
uv run ruff check . && uv run ruff format .
git add src/coc_pointer/config.py tests/test_config.py
git commit -m "관리자 설정 파일 로더 추가

config/clan.yaml에서 정예·부캐·제외·경고를 읽고 태그 형식을 검증한다.

Co-Authored-By: Claude Fable 5.1 <noreply@anthropic.com>
Claude-Session: https://claude.ai/code/session_01SEjU63ioVTGGo4ZeJ2B4wU"
```

---

### Task 3: 점수 공식과 월 귀속 (scoring.py 1부)

**Files:**
- Create: `src/coc_pointer/scoring.py`
- Test: `tests/test_scoring.py`

**Interfaces:**
- Consumes: `War`, `WarMember` (Task 1)
- Produces:
  - 상수 `BASE_POINTS = 5`, `MAX_POINTS_PER_ATTACK = 8`, `MIN_ATTACKS = 10`, `MIN_SCORE = 70.0`, `ROSTER_SIZE = 30`, `KST`
  - `RULES: tuple[str, ...]` 화면에 표시할 규칙 문구
  - `month_key(dt: datetime) -> str` ("2026-09", Asia/Seoul 기준)
  - `MemberMonth(tag, name, townhall, attacks: int, opportunities: int, stars: int)` with properties `.missed`, `.star_avg`, `.score`
  - `passes_cutline(m: MemberMonth) -> bool`

- [ ] **Step 1: 실패하는 테스트 작성**

`tests/test_scoring.py`:

```python
from datetime import UTC, datetime

import pytest

from coc_pointer.scoring import RULES, MemberMonth, month_key, passes_cutline


def mm(attacks: int, opportunities: int, stars: int, tag="#P", name="x") -> MemberMonth:
    return MemberMonth(tag=tag, name=name, townhall=16, attacks=attacks, opportunities=opportunities, stars=stars)


# Rows taken from the clan's real August 2026 sheet; the formula must reproduce them.
@pytest.mark.parametrize(
    ("attacks", "opportunities", "stars", "score"),
    [
        (27, 27, 81, 100.0),  # 도토리
        (27, 27, 80, 99.5),  # Taimanin
        (25, 27, 75, 92.6),  # 정사과
        (23, 27, 62, 81.9),  # 군방
        (70, 72, 170, 90.28),  # 빼빼 (1차 입력표, 소수 둘째 자리)
    ],
)
def test_score_matches_excel(attacks, opportunities, stars, score):
    m = mm(attacks, opportunities, stars)
    assert round(m.score, 2) == pytest.approx(score, abs=0.005) or round(m.score, 1) == score


def test_missed_and_star_avg():
    m = mm(25, 27, 75)
    assert m.missed == 2
    assert round(m.star_avg, 2) == 2.78


def test_zero_opportunities_gives_zero_score():
    m = mm(0, 0, 0)
    assert m.score == 0.0
    assert m.star_avg == 0.0


def test_cutline_requires_ten_attacks_and_seventy_points():
    assert passes_cutline(mm(10, 10, 20))  # (50+20)/80 = 87.5
    assert not passes_cutline(mm(9, 9, 27))  # attacks < 10
    assert not passes_cutline(mm(10, 16, 10))  # (50+10)/128 = 46.9


def test_month_key_uses_korea_time():
    # 2026-08-31 15:30 UTC == 2026-09-01 00:30 KST
    assert month_key(datetime(2026, 8, 31, 15, 30, tzinfo=UTC)) == "2026-09"
    assert month_key(datetime(2026, 8, 31, 14, 30, tzinfo=UTC)) == "2026-08"


def test_rules_text_mentions_formula_and_cutline():
    joined = " ".join(RULES)
    assert "5" in joined and "8" in joined and "10회" in joined and "70점" in joined and "30" in joined
```

- [ ] **Step 2: 테스트 실패 확인**

Run: `uv run pytest tests/test_scoring.py -v`
Expected: FAIL, `ModuleNotFoundError: No module named 'coc_pointer.scoring'`

- [ ] **Step 3: scoring.py 1부 구현**

`src/coc_pointer/scoring.py`:

```python
"""Clan war activity score and CWL roster selection (rules effective 2026-09).

점수 규칙 (엑셀 "클랜 리그전 30인 선발 기준 안내" 그대로):

1. 공격 1회 = 기본 5점 + 그 공격에서 딴 별 수 (최대 8점). 미공격 = 0점.
2. 공격 기회 = 참가한 클랜전마다 일반 클랜전 2회, 리그전 1회. 명단에 없으면 기회 없음.
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

from dataclasses import dataclass
from datetime import datetime
from zoneinfo import ZoneInfo

BASE_POINTS = 5
MAX_POINTS_PER_ATTACK = 8
MIN_ATTACKS = 10
MIN_SCORE = 70.0
ROSTER_SIZE = 30
KST = ZoneInfo("Asia/Seoul")

RULES: tuple[str, ...] = (
    "공격 1회 = 기본 5점 + 획득한 별 수 (최대 8점). 미공격 = 0점.",
    "월 점수 = (5 × 공격 횟수 + 별 총합) ÷ (8 × 공격 기회) × 100. "
    "공격 기회는 일반 클랜전 2회, 리그전 1회.",
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
```

- [ ] **Step 4: 테스트 통과 확인**

Run: `uv run pytest tests/test_scoring.py -v`
Expected: 10 passed (parametrize 5 + 5)

- [ ] **Step 5: 린트와 커밋**

```bash
uv run ruff check . && uv run ruff format .
git add src/coc_pointer/scoring.py tests/test_scoring.py
git commit -m "점수 공식과 월 귀속 규칙 구현

엑셀 8월 표의 실제 숫자 5명분을 정답으로 검증한다. 규칙 문구 RULES를
모듈 docstring과 함께 한 곳에 정의한다.

Co-Authored-By: Claude Fable 5.1 <noreply@anthropic.com>
Claude-Session: https://claude.ai/code/session_01SEjU63ioVTGGo4ZeJ2B4wU"
```

---

### Task 4: 월 집계 (scoring.py 2부)

**Files:**
- Modify: `src/coc_pointer/scoring.py`
- Test: `tests/test_scoring.py` (추가)

**Interfaces:**
- Consumes: `War`, `WarMember`, `month_key`, `MemberMonth`
- Produces:
  - `group_wars_by_month(wars: Iterable[War]) -> dict[str, list[War]]` 월 키 오름차순, 각 목록은 종료 시각 오름차순
  - `aggregate_month(wars: Iterable[War]) -> list[MemberMonth]` 닉네임·홀 레벨은 가장 최근 클랜전 기준. 순서는 태그순(정렬은 Task 5에서).

- [ ] **Step 1: 실패하는 테스트 추가**

`tests/test_scoring.py` 끝에 추가:

```python
from helpers import member, war  # noqa: E402

from coc_pointer.scoring import aggregate_month, group_wars_by_month  # noqa: E402


def by_tag(rows):
    return {r.tag: r for r in rows}


def test_aggregate_counts_opportunities_per_war_type():
    w1 = war([member("#P1", "도토리", (3, 2)), member("#P2", "제니", (1,))], war_type="regular")
    w2 = war([member("#P1", "도토리", (3,))], war_type="cwl", end="2026-09-06T10:00:00Z")
    rows = by_tag(aggregate_month([w1, w2]))
    assert rows["#P1"].attacks == 3 and rows["#P1"].opportunities == 3 and rows["#P1"].stars == 8
    assert rows["#P2"].attacks == 1 and rows["#P2"].opportunities == 2 and rows["#P2"].missed == 1
    assert "#P3" not in rows


def test_aggregate_uses_latest_name_and_townhall():
    old = war([member("#P1", "옛이름", (3, 3), townhall=16)], end="2026-09-01T10:00:00Z")
    new = war([member("#P1", "새이름", (3, 3), townhall=17)], end="2026-09-03T10:00:00Z")
    row = aggregate_month([new, old])[0]
    assert row.name == "새이름" and row.townhall == 17


def test_group_wars_by_month_uses_korea_time_and_sorts():
    aug = war([member("#P1", "a", (3, 3))], end="2026-08-31T14:00:00Z")  # 23:00 KST Aug 31
    sep = war([member("#P1", "a", (3, 3))], end="2026-08-31T15:30:00Z")  # 00:30 KST Sep 1
    later = war([member("#P1", "a", (3, 3))], end="2026-09-05T15:30:00Z")
    grouped = group_wars_by_month([later, sep, aug])
    assert list(grouped) == ["2026-08", "2026-09"]
    assert grouped["2026-09"] == [sep, later]
```

- [ ] **Step 2: 테스트 실패 확인**

Run: `uv run pytest tests/test_scoring.py -v -k "aggregate or group"`
Expected: FAIL, `ImportError: cannot import name 'aggregate_month'`

- [ ] **Step 3: 집계 함수 구현**

`src/coc_pointer/scoring.py` 끝에 추가:

```python
from collections.abc import Iterable  # noqa: E402  (top-of-file imports are above)

from coc_pointer.models import War  # noqa: E402


def group_wars_by_month(wars: Iterable[War]) -> dict[str, list[War]]:
    grouped: dict[str, list[War]] = {}
    for w in sorted(wars, key=lambda w: w.end_time):
        grouped.setdefault(month_key(w.end_time), []).append(w)
    return dict(sorted(grouped.items()))


def aggregate_month(wars: Iterable[War]) -> list[MemberMonth]:
    """Sum attacks/opportunities/stars per member across ``wars`` (assumed same month)."""
    attacks: dict[str, int] = {}
    opportunities: dict[str, int] = {}
    stars: dict[str, int] = {}
    latest: dict[str, tuple[datetime, str, int]] = {}
    for w in wars:
        for m in w.members:
            attacks[m.tag] = attacks.get(m.tag, 0) + len(m.attacks)
            opportunities[m.tag] = opportunities.get(m.tag, 0) + w.attacks_per_member
            stars[m.tag] = stars.get(m.tag, 0) + sum(a.stars for a in m.attacks)
            if m.tag not in latest or w.end_time > latest[m.tag][0]:
                latest[m.tag] = (w.end_time, m.name, m.townhall)
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
```

그 다음 파일 상단 import 블록을 정리한다. `from collections.abc import Iterable`과 `from coc_pointer.models import War`를 상단 import로 옮기고 `# noqa` 주석을 지운다. 최종 상단은 다음과 같다.

```python
from __future__ import annotations

from collections.abc import Iterable
from dataclasses import dataclass
from datetime import datetime
from zoneinfo import ZoneInfo

from coc_pointer.models import War
```

- [ ] **Step 4: 테스트 통과 확인**

Run: `uv run pytest tests/test_scoring.py -v`
Expected: 13 passed

- [ ] **Step 5: 린트와 커밋**

```bash
uv run ruff check . && uv run ruff format .
git add src/coc_pointer/scoring.py tests/test_scoring.py
git commit -m "클랜전 월별 집계 구현

일반 2회·리그전 1회 공격 기회를 합산하고, 닉네임과 홀 레벨은 최근 클랜전
기준으로 잡는다. 월 경계는 한국 시간으로 판단한다.

Co-Authored-By: Claude Fable 5.1 <noreply@anthropic.com>
Claude-Session: https://claude.ai/code/session_01SEjU63ioVTGGo4ZeJ2B4wU"
```

---

### Task 5: 순위와 30인 선발 (scoring.py 3부)

**Files:**
- Modify: `src/coc_pointer/scoring.py`
- Test: `tests/test_scoring.py` (추가)

**Interfaces:**
- Consumes: `MemberMonth`, `passes_cutline`, `ClanConfig` (Task 2)
- Produces:
  - `RankedMember(rank: int, member: MemberMonth, is_elite: bool, is_alt: bool, is_excluded: bool, warnings: int, meets_cutline: bool, selection: str | None)` — `selection`은 `"정예"`, `"선발"`, `None` 중 하나
  - `sort_key(m: MemberMonth) -> tuple` (점수 내림, 별 내림, 공격 내림, 이름 오름)
  - `rank_month(members: Iterable[MemberMonth], config: ClanConfig) -> list[RankedMember]` 월 점수표 순서(점수순, rank 1..N)
  - `roster(ranked: Iterable[RankedMember]) -> list[RankedMember]` 최종 선발 명단: 정예 먼저, 그다음 선발, 각각 점수순, rank를 1..30으로 다시 매김

- [ ] **Step 1: 실패하는 테스트 추가**

`tests/test_scoring.py` 끝에 추가:

```python
from coc_pointer.config import ClanConfig  # noqa: E402
from coc_pointer.scoring import ROSTER_SIZE, rank_month, roster  # noqa: E402


def strong(tag, name="m", score_stars=3):
    # 12 attacks, all made, star avg configurable -> score >= 70
    return mm(12, 12, 12 * score_stars, tag=tag, name=name)


def test_rank_orders_by_score_then_stars_then_attacks_then_name():
    a = mm(10, 10, 20, tag="#A", name="가")  # 87.5
    b = mm(11, 11, 22, tag="#B", name="나")  # 87.5, more stars & attacks
    c = mm(10, 10, 20, tag="#C", name="다")  # 87.5, same as a, later name
    ranked = rank_month([c, a, b], ClanConfig(clan_tag="#X"))
    assert [r.member.tag for r in ranked] == ["#B", "#A", "#C"]
    assert [r.rank for r in ranked] == [1, 2, 3]


def test_selection_elite_first_then_by_score_up_to_roster_size():
    cfg = ClanConfig(clan_tag="#X", elite=frozenset({"#E1", "#E2"}))
    members = [strong(f"#M{i:02d}", name=f"m{i:02d}", score_stars=2) for i in range(35)]
    members += [strong("#E1", "e1", score_stars=1), strong("#E2", "e2", score_stars=1)]
    ranked = rank_month(members, cfg)
    sel = {r.member.tag: r.selection for r in ranked}
    assert sel["#E1"] == "정예" and sel["#E2"] == "정예"
    assert sum(1 for v in sel.values() if v is not None) == ROSTER_SIZE
    assert sum(1 for v in sel.values() if v == "선발") == ROSTER_SIZE - 2
    # the 28 selected regulars are the top-scoring ones; the 7 weakest get None
    unselected = sorted(t for t, v in sel.items() if v is None)
    assert len(unselected) == 7


def test_elite_below_cutline_is_not_selected_as_elite():
    cfg = ClanConfig(clan_tag="#X", elite=frozenset({"#E1"}))
    weak_elite = mm(9, 12, 27, tag="#E1", name="e1")  # 9 attacks < 10
    ranked = rank_month([weak_elite, strong("#M1")], cfg)
    by = {r.member.tag: r for r in ranked}
    assert by["#E1"].is_elite and not by["#E1"].meets_cutline and by["#E1"].selection is None
    assert by["#M1"].selection == "선발"


def test_alt_is_never_elite_but_can_be_selected():
    cfg = ClanConfig(clan_tag="#X", elite=frozenset({"#A1"}), alts=frozenset({"#A1"}))
    ranked = rank_month([strong("#A1")], cfg)
    r = ranked[0]
    assert r.is_alt and not r.is_elite and r.selection == "선발"


def test_excluded_member_is_listed_but_never_selected():
    cfg = ClanConfig(clan_tag="#X", elite=frozenset({"#X1"}), excluded=frozenset({"#X1"}))
    ranked = rank_month([strong("#X1"), strong("#M1")], cfg)
    by = {r.member.tag: r for r in ranked}
    assert by["#X1"].is_excluded and by["#X1"].selection is None
    assert by["#M1"].selection == "선발"


def test_warnings_are_carried_but_do_not_affect_score():
    cfg = ClanConfig(clan_tag="#X", warnings={"#M1": 2})
    r = rank_month([strong("#M1")], cfg)[0]
    assert r.warnings == 2 and r.selection == "선발"


def test_roster_puts_elite_first_and_renumbers():
    cfg = ClanConfig(clan_tag="#X", elite=frozenset({"#E1"}))
    ranked = rank_month([strong("#M1", score_stars=3), strong("#E1", score_stars=1)], cfg)
    final = roster(ranked)
    assert [r.member.tag for r in final] == ["#E1", "#M1"]
    assert [r.rank for r in final] == [1, 2]
    assert [r.selection for r in final] == ["정예", "선발"]
```

- [ ] **Step 2: 테스트 실패 확인**

Run: `uv run pytest tests/test_scoring.py -v -k "rank or selection or elite or alt or excluded or warnings or roster"`
Expected: FAIL, `ImportError: cannot import name 'rank_month'`

- [ ] **Step 3: 순위·선발 구현**

`src/coc_pointer/scoring.py` 끝에 추가 (상단 import에 `from coc_pointer.config import ClanConfig` 추가):

```python
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
```

- [ ] **Step 4: 테스트 통과 확인**

Run: `uv run pytest tests/test_scoring.py -v`
Expected: 20 passed

- [ ] **Step 5: 린트와 커밋**

```bash
uv run ruff check . && uv run ruff format .
git add src/coc_pointer/scoring.py tests/test_scoring.py
git commit -m "월 순위와 30인 선발 규칙 구현

커트라인, 정예 우선, 부캐 정예 불가, 제외, 동점 처리, 최종 명단 재정렬.

Co-Authored-By: Claude Fable 5.1 <noreply@anthropic.com>
Claude-Session: https://claude.ai/code/session_01SEjU63ioVTGGo4ZeJ2B4wU"
```

---

### Task 6: 데이터 저장소 (storage.py)

**Files:**
- Create: `src/coc_pointer/storage.py`
- Test: `tests/test_storage.py`

**Interfaces:**
- Consumes: `War`, `ClanSnapshot` (Task 1)
- Produces:
  - `WARS_DIR = "wars"`, `CLAN_FILE = "clan.json"`
  - `save_war(war: War, data_dir: Path) -> Path | None` 이미 있으면 `None`, 새로 썼으면 경로
  - `load_wars(data_dir: Path) -> list[War]` 종료 시각 오름차순. 폴더가 없으면 빈 목록.
  - `save_clan_snapshot(snapshot: ClanSnapshot, data_dir: Path) -> Path` 항상 덮어씀
  - `load_clan_snapshot(data_dir: Path) -> ClanSnapshot | None`

- [ ] **Step 1: 실패하는 테스트 작성**

`tests/test_storage.py`:

```python
import json
from datetime import UTC, datetime

from helpers import member, war

from coc_pointer.models import ClanMember, ClanSnapshot
from coc_pointer.storage import (
    load_clan_snapshot,
    load_wars,
    save_clan_snapshot,
    save_war,
)


def test_save_war_writes_json_once(tmp_path):
    w = war([member("#P1", "도토리", (3, 2))])
    first = save_war(w, tmp_path)
    assert first == tmp_path / "wars" / w.file_name
    assert json.loads(first.read_text(encoding="utf-8"))["opponent"]["tag"] == "#OPP1"
    assert save_war(w, tmp_path) is None, "existing files are never rewritten"


def test_load_wars_sorted_by_end_time(tmp_path):
    late = war([member("#P1", "a", (3, 3))], end="2026-09-05T10:00:00Z")
    early = war([member("#P1", "a", (3, 3))], end="2026-09-01T10:00:00Z", opponent_tag="#OPP2")
    save_war(late, tmp_path)
    save_war(early, tmp_path)
    assert load_wars(tmp_path) == [early, late]


def test_load_wars_empty_when_missing(tmp_path):
    assert load_wars(tmp_path / "nope") == []


def test_clan_snapshot_round_trip_overwrites(tmp_path):
    snap = ClanSnapshot(
        fetched_at=datetime(2026, 9, 7, tzinfo=UTC),
        name="미니언즈",
        tag="#2C8L822LQ",
        members=(ClanMember("#P1", "도토리", "leader", 18, 5000, 10, 20),),
    )
    assert load_clan_snapshot(tmp_path) is None
    save_clan_snapshot(snap, tmp_path)
    newer = ClanSnapshot(snap.fetched_at, snap.name, snap.tag, ())
    save_clan_snapshot(newer, tmp_path)
    assert load_clan_snapshot(tmp_path) == newer
```

- [ ] **Step 2: 테스트 실패 확인**

Run: `uv run pytest tests/test_storage.py -v`
Expected: FAIL, `ModuleNotFoundError: No module named 'coc_pointer.storage'`

- [ ] **Step 3: storage.py 구현**

`src/coc_pointer/storage.py`:

```python
"""Read and write the ``data/`` directory (the repository is the database)."""

from __future__ import annotations

import json
from pathlib import Path

from coc_pointer.models import ClanSnapshot, War

WARS_DIR = "wars"
CLAN_FILE = "clan.json"


def _dump(path: Path, payload: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def save_war(war: War, data_dir: Path) -> Path | None:
    """Write ``war`` as JSON. Return the path, or ``None`` if it already existed."""
    path = data_dir / WARS_DIR / war.file_name
    if path.exists():
        return None
    _dump(path, war.to_dict())
    return path


def load_wars(data_dir: Path) -> list[War]:
    folder = data_dir / WARS_DIR
    if not folder.is_dir():
        return []
    wars = [War.from_dict(json.loads(p.read_text(encoding="utf-8"))) for p in folder.glob("*.json")]
    return sorted(wars, key=lambda w: w.end_time)


def save_clan_snapshot(snapshot: ClanSnapshot, data_dir: Path) -> Path:
    path = data_dir / CLAN_FILE
    _dump(path, snapshot.to_dict())
    return path


def load_clan_snapshot(data_dir: Path) -> ClanSnapshot | None:
    path = data_dir / CLAN_FILE
    if not path.exists():
        return None
    return ClanSnapshot.from_dict(json.loads(path.read_text(encoding="utf-8")))
```

- [ ] **Step 4: 테스트 통과 확인**

Run: `uv run pytest tests/test_storage.py -v`
Expected: 4 passed

- [ ] **Step 5: 린트와 커밋**

```bash
uv run ruff check . && uv run ruff format .
git add src/coc_pointer/storage.py tests/test_storage.py
git commit -m "data/ 폴더 읽기·쓰기 구현

클랜전은 파일 이름으로 중복을 막고 한 번 쓰면 수정하지 않는다.
클랜원 스냅샷은 매번 덮어쓴다.

Co-Authored-By: Claude Fable 5.1 <noreply@anthropic.com>
Claude-Session: https://claude.ai/code/session_01SEjU63ioVTGGo4ZeJ2B4wU"
```

---

### Task 7: API 클라이언트 (api.py)

**Files:**
- Create: `src/coc_pointer/api.py`
- Test: `tests/test_api.py`

**Interfaces:**
- Produces:
  - `PROXY_BASE_URL = "https://cocproxy.royaleapi.dev/v1"`, `USER_AGENT = "coc-pointer/0.1"`
  - `CocApiError(Exception)` with attributes `status: int`, `path: str`, `reason: str`, `message: str`
  - `CocApi(token: str, base_url: str = PROXY_BASE_URL, transport: httpx.BaseTransport | None = None)`
    - `.get(path: str) -> dict | None` — 404이면 `None`, 4xx/5xx이면 `CocApiError`
    - `.clan(tag) -> dict`, `.current_war(tag) -> dict`, `.league_group(tag) -> dict | None`, `.cwl_war(war_tag) -> dict`
    - `.close()`; 컨텍스트 매니저 지원
  - `encode_tag(tag: str) -> str` (`#` → `%23`)

- [ ] **Step 1: 실패하는 테스트 작성**

`tests/test_api.py`:

```python
import httpx
import pytest

from coc_pointer.api import USER_AGENT, CocApi, CocApiError, encode_tag


def make_api(handler):
    return CocApi(token="tok", transport=httpx.MockTransport(handler))


def test_encode_tag():
    assert encode_tag("#2C8L822LQ") == "%232C8L822LQ"


def test_get_sends_auth_and_user_agent_and_returns_json():
    seen = {}

    def handler(request: httpx.Request) -> httpx.Response:
        seen["url"] = str(request.url)
        seen["auth"] = request.headers["Authorization"]
        seen["ua"] = request.headers["User-Agent"]
        return httpx.Response(200, json={"name": "미니언즈"})

    with make_api(handler) as api:
        assert api.clan("#2C8L822LQ") == {"name": "미니언즈"}
    assert seen["url"] == "https://cocproxy.royaleapi.dev/v1/clans/%232C8L822LQ"
    assert seen["auth"] == "Bearer tok"
    assert seen["ua"] == USER_AGENT


def test_404_returns_none_for_league_group():
    def handler(request):
        return httpx.Response(404, json={"reason": "notFound"})

    with make_api(handler) as api:
        assert api.league_group("#2C8L822LQ") is None


def test_403_raises_with_reason_and_message():
    def handler(request):
        return httpx.Response(403, json={"reason": "accessDenied", "message": "Invalid authorization"})

    with make_api(handler) as api, pytest.raises(CocApiError) as exc:
        api.current_war("#2C8L822LQ")
    err = exc.value
    assert err.status == 403 and err.reason == "accessDenied" and "currentwar" in err.path
    assert "Invalid authorization" in str(err)


def test_cwl_war_path_encodes_tag():
    def handler(request):
        assert request.url.path == "/v1/clanwarleagues/wars/%238GVJQPUUR"
        return httpx.Response(200, json={"state": "warEnded"})

    with make_api(handler) as api:
        assert api.cwl_war("#8GVJQPUUR")["state"] == "warEnded"
```

- [ ] **Step 2: 테스트 실패 확인**

Run: `uv run pytest tests/test_api.py -v`
Expected: FAIL, `ModuleNotFoundError: No module named 'coc_pointer.api'`

- [ ] **Step 3: api.py 구현**

`src/coc_pointer/api.py`:

```python
"""Thin client for the Clash of Clans API via the RoyaleAPI proxy.

The proxy's Cloudflare front rejects requests without a normal User-Agent, so one is
always sent. Tokens are IP-bound; the proxy IP 45.79.218.79 must be allowed on the key.
"""

from __future__ import annotations

from typing import Any
from urllib.parse import quote

import httpx

PROXY_BASE_URL = "https://cocproxy.royaleapi.dev/v1"
USER_AGENT = "coc-pointer/0.1"


class CocApiError(Exception):
    def __init__(self, status: int, path: str, reason: str, message: str) -> None:
        self.status = status
        self.path = path
        self.reason = reason
        self.message = message
        super().__init__(f"HTTP {status} {reason} on {path}: {message}")


def encode_tag(tag: str) -> str:
    return quote(tag, safe="")


class CocApi:
    def __init__(
        self,
        token: str,
        base_url: str = PROXY_BASE_URL,
        transport: httpx.BaseTransport | None = None,
    ) -> None:
        self._client = httpx.Client(
            base_url=base_url,
            headers={
                "Authorization": f"Bearer {token}",
                "User-Agent": USER_AGENT,
                "Accept": "application/json",
            },
            timeout=30.0,
            transport=transport,
        )

    def close(self) -> None:
        self._client.close()

    def __enter__(self) -> CocApi:
        return self

    def __exit__(self, *exc: object) -> None:
        self.close()

    def get(self, path: str) -> dict[str, Any] | None:
        response = self._client.get(path)
        if response.status_code == 404:
            return None
        if response.status_code >= 400:
            try:
                body = response.json()
            except ValueError:
                body = {}
            raise CocApiError(
                status=response.status_code,
                path=path,
                reason=str(body.get("reason", "unknown")),
                message=str(body.get("message", response.text[:200])),
            )
        return response.json()

    def _require(self, path: str) -> dict[str, Any]:
        data = self.get(path)
        if data is None:
            raise CocApiError(404, path, "notFound", "리소스를 찾을 수 없습니다")
        return data

    def clan(self, tag: str) -> dict[str, Any]:
        return self._require(f"/clans/{encode_tag(tag)}")

    def current_war(self, tag: str) -> dict[str, Any]:
        return self._require(f"/clans/{encode_tag(tag)}/currentwar")

    def league_group(self, tag: str) -> dict[str, Any] | None:
        return self.get(f"/clans/{encode_tag(tag)}/currentwar/leaguegroup")

    def cwl_war(self, war_tag: str) -> dict[str, Any]:
        return self._require(f"/clanwarleagues/wars/{encode_tag(war_tag)}")
```

- [ ] **Step 4: 테스트 통과 확인**

Run: `uv run pytest tests/test_api.py -v`
Expected: 5 passed

- [ ] **Step 5: 린트와 커밋**

```bash
uv run ruff check . && uv run ruff format .
git add src/coc_pointer/api.py tests/test_api.py
git commit -m "CoC API 클라이언트 구현

RoyaleAPI 프록시를 기본 주소로 쓰고 User-Agent를 항상 붙인다. 404는 None,
그 외 오류는 CocApiError로 올린다.

Co-Authored-By: Claude Fable 5.1 <noreply@anthropic.com>
Claude-Session: https://claude.ai/code/session_01SEjU63ioVTGGo4ZeJ2B4wU"
```

---

### Task 8: 수집기 (collect.py)

**Files:**
- Create: `src/coc_pointer/collect.py`
- Test: `tests/test_collect.py`

**Interfaces:**
- Consumes: `CocApi`, `CocApiError` (Task 7), `save_war`, `save_clan_snapshot` (Task 6), `War`, `WarMember`, `Attack`, `ClanSnapshot`, `ClanMember` (Task 1), `ClanConfig` (Task 2)
- Produces:
  - `parse_api_time(text: str) -> datetime` (`20260903T093932.000Z` → UTC aware)
  - `war_from_regular(payload: dict) -> War`
  - `war_from_cwl(payload: dict, our_tag: str) -> War | None` (우리 클랜이 없으면 `None`)
  - `clan_snapshot_from_payload(payload: dict, fetched_at: datetime) -> ClanSnapshot`
  - `WarLogPrivateError(Exception)`
  - `collect(api, config: ClanConfig, data_dir: Path, now: datetime | None = None, log: Callable[[str], None] = print) -> list[Path]` 새로 저장한 파일 경로 목록. `api`는 `clan`, `current_war`, `league_group`, `cwl_war` 메서드만 있으면 된다(테스트용 가짜 객체 허용).

- [ ] **Step 1: 실패하는 테스트 작성**

`tests/test_collect.py`:

```python
from datetime import UTC, datetime
from pathlib import Path

import pytest

from coc_pointer.api import CocApiError
from coc_pointer.collect import (
    WarLogPrivateError,
    clan_snapshot_from_payload,
    collect,
    parse_api_time,
    war_from_cwl,
    war_from_regular,
)
from coc_pointer.config import ClanConfig
from coc_pointer.storage import load_clan_snapshot, load_wars

OUR = "#2C8L822LQ"


def side(tag, name, members):
    return {"tag": tag, "name": name, "members": members}


def m(tag, name, th, attacks=None):
    d = {"tag": tag, "name": name, "townhallLevel": th, "mapPosition": 1}
    if attacks is not None:
        d["attacks"] = attacks
    return d


def atk(order, stars):
    return {"attackerTag": "#X", "defenderTag": "#Y", "stars": stars, "destructionPercentage": 50, "order": order, "duration": 100}


REGULAR_ENDED = {
    "state": "warEnded",
    "teamSize": 2,
    "attacksPerMember": 2,
    "preparationStartTime": "20260903T140000.000Z",
    "startTime": "20260904T140000.000Z",
    "endTime": "20260905T140000.000Z",
    "clan": side(OUR, "미니언즈", [m("#P1", "도토리", 18, [atk(2, 3), atk(1, 2)]), m("#P2", "제니", 16)]),
    "opponent": side("#OPP1", "상대클랜", []),
}

CWL_ENDED_WE_ARE_OPPONENT = {
    "state": "warEnded",
    "teamSize": 1,
    "preparationStartTime": "20260902T084403.000Z",
    "startTime": "20260902T084403.000Z",
    "endTime": "20260903T093932.000Z",
    "warStartTime": "20260902T084403.000Z",
    "clan": side("#OTHER", "다른클랜", [m("#Q1", "남", 15, [atk(1, 1)])]),
    "opponent": side(OUR, "미니언즈", [m("#P1", "도토리", 18, [atk(1, 3)])]),
}

CLAN_PAYLOAD = {
    "tag": OUR,
    "name": "미니언즈",
    "memberList": [
        {"tag": "#P1", "name": "도토리", "role": "coLeader", "townHallLevel": 18, "trophies": 5200, "donations": 1200, "donationsReceived": 900},
    ],
}


def test_parse_api_time():
    assert parse_api_time("20260903T093932.000Z") == datetime(2026, 9, 3, 9, 39, 32, tzinfo=UTC)


def test_war_from_regular_sorts_attacks_and_keeps_non_attackers():
    w = war_from_regular(REGULAR_ENDED)
    assert w.war_type == "regular" and w.attacks_per_member == 2 and w.team_size == 2
    assert w.opponent_tag == "#OPP1" and w.opponent_name == "상대클랜"
    assert w.end_time == datetime(2026, 9, 5, 14, 0, tzinfo=UTC)
    p1, p2 = w.members
    assert [a.stars for a in p1.attacks] == [2, 3]
    assert p2.attacks == ()


def test_war_from_cwl_finds_our_side_and_uses_one_attack():
    w = war_from_cwl(CWL_ENDED_WE_ARE_OPPONENT, OUR)
    assert w is not None
    assert w.war_type == "cwl" and w.attacks_per_member == 1
    assert w.opponent_tag == "#OTHER"
    assert w.members[0].tag == "#P1"


def test_war_from_cwl_returns_none_when_not_ours():
    assert war_from_cwl(CWL_ENDED_WE_ARE_OPPONENT, "#NOBODY") is None


def test_clan_snapshot_from_payload_maps_fields():
    snap = clan_snapshot_from_payload(CLAN_PAYLOAD, datetime(2026, 9, 7, tzinfo=UTC))
    assert snap.tag == OUR and snap.name == "미니언즈"
    mem = snap.members[0]
    assert (mem.role, mem.townhall, mem.donations_received) == ("coLeader", 18, 900)


class FakeApi:
    def __init__(self, clan=CLAN_PAYLOAD, current_war=None, league_group=None, cwl_wars=None):
        self._clan = clan
        self._current_war = current_war or {"state": "notInWar"}
        self._league_group = league_group
        self._cwl_wars = cwl_wars or {}
        self.calls: list[str] = []

    def clan(self, tag):
        self.calls.append("clan")
        return self._clan

    def current_war(self, tag):
        self.calls.append("current_war")
        if isinstance(self._current_war, Exception):
            raise self._current_war
        return self._current_war

    def league_group(self, tag):
        self.calls.append("league_group")
        return self._league_group

    def cwl_war(self, war_tag):
        self.calls.append(f"cwl:{war_tag}")
        return self._cwl_wars[war_tag]


CFG = ClanConfig(clan_tag=OUR)


def test_collect_saves_snapshot_and_ended_regular_war(tmp_path: Path):
    api = FakeApi(current_war=REGULAR_ENDED)
    new = collect(api, CFG, tmp_path, now=datetime(2026, 9, 7, tzinfo=UTC), log=lambda s: None)
    assert len(new) == 1 and new[0].name.endswith("_regular_OPP1.json")
    assert load_clan_snapshot(tmp_path).name == "미니언즈"
    assert load_wars(tmp_path)[0].war_type == "regular"
    # second run: nothing new
    assert collect(api, CFG, tmp_path, log=lambda s: None) == []


def test_collect_skips_war_in_progress(tmp_path):
    api = FakeApi(current_war={**REGULAR_ENDED, "state": "inWar"})
    assert collect(api, CFG, tmp_path, log=lambda s: None) == []
    assert load_wars(tmp_path) == []


def test_collect_saves_only_our_ended_cwl_wars(tmp_path):
    group = {"state": "inWar", "season": "2026-09", "rounds": [{"warTags": ["#W1", "#W2"]}, {"warTags": ["#0", "#0"]}]}
    in_progress = {**CWL_ENDED_WE_ARE_OPPONENT, "state": "inWar"}
    api = FakeApi(league_group=group, cwl_wars={"#W1": CWL_ENDED_WE_ARE_OPPONENT, "#W2": in_progress})
    new = collect(api, CFG, tmp_path, log=lambda s: None)
    assert len(new) == 1 and "_cwl_OTHER.json" in new[0].name
    assert "cwl:#0" not in api.calls


def test_collect_raises_clear_error_when_war_log_private(tmp_path):
    api = FakeApi(current_war=CocApiError(403, "/clans/x/currentwar", "accessDenied", "private"))
    with pytest.raises(WarLogPrivateError, match="전적"):
        collect(api, CFG, tmp_path, log=lambda s: None)
```

- [ ] **Step 2: 테스트 실패 확인**

Run: `uv run pytest tests/test_collect.py -v`
Expected: FAIL, `ModuleNotFoundError: No module named 'coc_pointer.collect'`

- [ ] **Step 3: collect.py 구현**

`src/coc_pointer/collect.py`:

```python
"""Fetch finished wars from the API and persist them under ``data/``.

Only ``warEnded`` wars are saved. Regular-war member attacks disappear from the API
as soon as the next war's preparation starts, which is why this runs on a schedule.
"""

from __future__ import annotations

from collections.abc import Callable
from datetime import UTC, datetime
from pathlib import Path
from typing import Any, Protocol

from coc_pointer.api import CocApiError
from coc_pointer.config import ClanConfig
from coc_pointer.models import Attack, ClanMember, ClanSnapshot, War, WarMember
from coc_pointer.storage import save_clan_snapshot, save_war

_API_TIME = "%Y%m%dT%H%M%S.%fZ"
REGULAR_ATTACKS = 2
CWL_ATTACKS = 1
EMPTY_WAR_TAG = "#0"


class WarLogPrivateError(Exception):
    """The clan's war log is private, so the API refuses war details."""


class ApiLike(Protocol):
    def clan(self, tag: str) -> dict[str, Any]: ...
    def current_war(self, tag: str) -> dict[str, Any]: ...
    def league_group(self, tag: str) -> dict[str, Any] | None: ...
    def cwl_war(self, war_tag: str) -> dict[str, Any]: ...


def parse_api_time(text: str) -> datetime:
    return datetime.strptime(text, _API_TIME).replace(tzinfo=UTC)


def _member(raw: dict[str, Any]) -> WarMember:
    attacks = sorted(
        (Attack(order=a["order"], stars=a["stars"]) for a in raw.get("attacks", [])),
        key=lambda a: a.order,
    )
    return WarMember(
        tag=raw["tag"], name=raw["name"], townhall=raw["townhallLevel"], attacks=tuple(attacks)
    )


def _build_war(
    payload: dict[str, Any], war_type: str, ours: dict[str, Any], theirs: dict[str, Any], apm: int
) -> War:
    return War(
        war_type=war_type,
        start_time=parse_api_time(payload["startTime"]),
        end_time=parse_api_time(payload["endTime"]),
        team_size=payload["teamSize"],
        attacks_per_member=apm,
        opponent_tag=theirs["tag"],
        opponent_name=theirs["name"],
        members=tuple(_member(m) for m in ours.get("members", [])),
    )


def war_from_regular(payload: dict[str, Any]) -> War:
    apm = payload.get("attacksPerMember") or REGULAR_ATTACKS
    return _build_war(payload, "regular", payload["clan"], payload["opponent"], apm)


def war_from_cwl(payload: dict[str, Any], our_tag: str) -> War | None:
    clan, opponent = payload["clan"], payload["opponent"]
    if clan["tag"] == our_tag:
        return _build_war(payload, "cwl", clan, opponent, CWL_ATTACKS)
    if opponent["tag"] == our_tag:
        return _build_war(payload, "cwl", opponent, clan, CWL_ATTACKS)
    return None


def clan_snapshot_from_payload(payload: dict[str, Any], fetched_at: datetime) -> ClanSnapshot:
    return ClanSnapshot(
        fetched_at=fetched_at,
        name=payload["name"],
        tag=payload["tag"],
        members=tuple(
            ClanMember(
                tag=m["tag"],
                name=m["name"],
                role=m["role"],
                townhall=m["townHallLevel"],
                trophies=m["trophies"],
                donations=m["donations"],
                donations_received=m["donationsReceived"],
            )
            for m in payload.get("memberList", [])
        ),
    )


def collect(
    api: ApiLike,
    config: ClanConfig,
    data_dir: Path,
    now: datetime | None = None,
    log: Callable[[str], None] = print,
) -> list[Path]:
    """Snapshot the clan, then save every finished war we do not have yet."""
    tag = config.clan_tag
    fetched_at = now or datetime.now(UTC)
    saved: list[Path] = []

    save_clan_snapshot(clan_snapshot_from_payload(api.clan(tag), fetched_at), data_dir)
    log("클랜원 목록 갱신")

    try:
        current = api.current_war(tag)
    except CocApiError as err:
        if err.status == 403:
            raise WarLogPrivateError(
                "클랜전 정보를 조회할 수 없습니다. 클랜 전적을 공개로 설정해 주세요."
            ) from err
        raise
    if current.get("state") == "warEnded":
        war = war_from_regular(current)
        if path := save_war(war, data_dir):
            saved.append(path)
            log(f"일반 클랜전 저장: {path.name}")
    else:
        log(f"일반 클랜전 상태: {current.get('state')} (저장 안 함)")

    group = api.league_group(tag)
    if group:
        for round_ in group.get("rounds", []):
            for war_tag in round_.get("warTags", []):
                if war_tag == EMPTY_WAR_TAG:
                    continue
                payload = api.cwl_war(war_tag)
                if payload.get("state") != "warEnded":
                    continue
                war = war_from_cwl(payload, tag)
                if war is None:
                    continue
                if path := save_war(war, data_dir):
                    saved.append(path)
                    log(f"리그전 저장: {path.name}")
    else:
        log("리그전 진행 중 아님")

    log(f"새로 저장한 클랜전: {len(saved)}개")
    return saved
```

- [ ] **Step 4: 테스트 통과 확인**

Run: `uv run pytest tests/test_collect.py -v`
Expected: 9 passed

- [ ] **Step 5: 린트와 커밋**

```bash
uv run ruff check . && uv run ruff format .
git add src/coc_pointer/collect.py tests/test_collect.py
git commit -m "클랜전 수집기 구현

일반 클랜전과 리그전 응답을 War로 변환하고 끝난 클랜전만 저장한다.
리그전은 우리 클랜이 clan/opponent 어느 쪽이든 태그로 찾는다.

Co-Authored-By: Claude Fable 5.1 <noreply@anthropic.com>
Claude-Session: https://claude.ai/code/session_01SEjU63ioVTGGo4ZeJ2B4wU"
```

---

### Task 9: 렌더러와 템플릿 (render.py, templates/)

**Files:**
- Create: `src/coc_pointer/render.py`
- Create: `src/coc_pointer/templates/base.html`, `_tables.html`, `index.html`, `month.html`, `members.html`, `style.css`
- Test: `tests/test_render.py`

**Interfaces:**
- Consumes: `load_wars`, `load_clan_snapshot` (Task 6), `group_wars_by_month`, `aggregate_month`, `rank_month`, `roster`, `RULES`, `KST`, `RankedMember` (Tasks 3–5), `ClanConfig` (Task 2), `War`, `ClanSnapshot`
- Produces:
  - `MonthView(key: str, label: str, wars: list[War], ranked: list[RankedMember], roster: list[RankedMember], grid: list[tuple[RankedMember, list[str]]])`
  - `build_month_view(key: str, wars: list[War], config: ClanConfig) -> MonthView`
  - `war_cell(war: War, tag: str) -> str` (`"3/2"`, `"3/x"`, `"x/x"`, `""`)
  - `build_site(data_dir: Path, config: ClanConfig, out_dir: Path, now: datetime | None = None) -> list[Path]` 생성한 파일 목록. 출력: `index.html`, `style.css`, `members/index.html`, `{YYYY-MM}/index.html`

- [ ] **Step 1: 실패하는 테스트 작성**

`tests/test_render.py`:

```python
from datetime import UTC, datetime

from helpers import member, war

from coc_pointer.config import ClanConfig
from coc_pointer.models import ClanMember, ClanSnapshot
from coc_pointer.render import build_month_view, build_site, war_cell
from coc_pointer.storage import save_clan_snapshot, save_war

CFG = ClanConfig(clan_tag="#2C8L822LQ", elite=frozenset({"#P1"}), warnings={"#P2": 1})


def test_war_cell_formats():
    w = war([member("#P1", "a", (3, 2)), member("#P2", "b", (1,)), member("#P3", "c")])
    assert war_cell(w, "#P1") == "3/2"
    assert war_cell(w, "#P2") == "1/x"
    assert war_cell(w, "#P3") == "x/x"
    assert war_cell(w, "#NOPE") == ""
    cwl = war([member("#P1", "a", (3,))], war_type="cwl")
    assert war_cell(cwl, "#P1") == "3"


def test_build_month_view_label_and_grid():
    w = war([member("#P1", "도토리", (3, 3)), member("#P2", "제니", (2, 1))])
    view = build_month_view("2026-09", [w], CFG)
    assert view.label == "2026년 9월"
    assert [r.member.name for r in view.ranked] == ["도토리", "제니"]
    assert view.grid[0][1] == ["3/3"]


def seed(tmp_path):
    save_war(war([member("#P1", "도토리", (3, 3), townhall=18), member("#P2", "제니", (2, 1))]), tmp_path)
    save_war(war([member("#P1", "도토리", (3,))], war_type="cwl", end="2026-09-06T10:00:00Z", opponent_tag="#OPP2", opponent_name="리그상대"), tmp_path)
    save_clan_snapshot(
        ClanSnapshot(
            fetched_at=datetime(2026, 9, 7, tzinfo=UTC),
            name="미니언즈",
            tag="#2C8L822LQ",
            members=(
                ClanMember("#P1", "도토리", "coLeader", 18, 5200, 1200, 900),
                ClanMember("#P9", "신입", "member", 12, 1000, 0, 0),
            ),
        ),
        tmp_path,
    )


def test_build_site_writes_pages(tmp_path):
    seed(tmp_path)
    out = tmp_path / "site"
    files = build_site(tmp_path, CFG, out, now=datetime(2026, 9, 7, 3, 0, tzinfo=UTC))
    names = {str(p.relative_to(out)) for p in files}
    assert names == {"index.html", "style.css", "members/index.html", "2026-09/index.html"}

    index = (out / "index.html").read_text(encoding="utf-8")
    assert "미니언즈" in index and "2026년 9월" in index
    assert "기본 5점" in index, "rules text must be shown"
    assert "2026-09-07 12:00" in index, "generated time shown in KST"

    # 3 attacks < MIN_ATTACKS, so nobody is selected; the full score table still lists everyone.
    month = (out / "2026-09" / "index.html").read_text(encoding="utf-8")
    assert "커트라인을 넘은 멤버가 없습니다" in month
    assert "도토리" in month and "제니" in month and "3/3" in month and "리그상대" in month
    assert "●" in month, "elite mark in score table"

    members = (out / "members" / "index.html").read_text(encoding="utf-8")
    assert "#P9" in members and "신입" in members and "공동 대표" in members


def test_build_site_with_no_data(tmp_path):
    out = tmp_path / "site"
    build_site(tmp_path, CFG, out)
    index = (out / "index.html").read_text(encoding="utf-8")
    assert "기록 없음" in index
```

- [ ] **Step 2: 테스트 실패 확인**

Run: `uv run pytest tests/test_render.py -v`
Expected: FAIL, `ModuleNotFoundError: No module named 'coc_pointer.render'`

- [ ] **Step 3: 템플릿 작성**

`src/coc_pointer/templates/base.html`:

```html
<!doctype html>
<html lang="ko">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>{% block title %}{{ clan_name }} 클랜전 점수{% endblock %}</title>
<link rel="stylesheet" href="{{ root }}style.css">
</head>
<body>
<header>
  <h1><a href="{{ root }}">{{ clan_name }} 클랜전 점수</a></h1>
  <nav>
    {% for m in months %}<a href="{{ root }}{{ m.key }}/">{{ m.label }}</a>{% endfor %}
    <a href="{{ root }}members/">클랜원 목록</a>
  </nav>
</header>
<main>
{% block content %}{% endblock %}
</main>
<footer>마지막 갱신: {{ generated_at }} (한국 시간)</footer>
</body>
</html>
```

`src/coc_pointer/templates/_tables.html`:

```html
{# 매크로는 기본적으로 바깥 변수를 못 보므로, 호출하는 템플릿에서 "with context"로 import한다. #}
{% macro rules_box() %}
<section class="rules">
  <h2>선발 규칙</h2>
  <ol>{% for r in rules %}<li>{{ r }}</li>{% endfor %}</ol>
</section>
{% endmacro %}

{% macro roster_table(rows) %}
<div class="scroll"><table>
<thead><tr><th>순위</th><th>닉네임</th><th>홀</th><th>공격</th><th>미공격</th><th>별 평균</th><th>점수</th><th>선발 근거</th></tr></thead>
<tbody>
{% for r in rows %}
<tr class="{{ 'elite' if r.selection == '정예' else '' }}">
  <td>{{ r.rank }}</td><td>{{ r.member.name }}</td><td>{{ r.member.townhall }}</td>
  <td>{{ r.member.attacks }}</td><td>{{ r.member.missed }}</td>
  <td>{{ "%.2f"|format(r.member.star_avg) }}</td><td>{{ "%.1f"|format(r.member.score) }}</td>
  <td>{{ r.selection }} 멤버</td>
</tr>
{% endfor %}
</tbody></table></div>
{% endmacro %}

{% macro score_table(rows) %}
<div class="scroll"><table>
<thead><tr><th>순위</th><th>닉네임</th><th>홀</th><th>공격</th><th>미공격</th><th>별 총합</th><th>별 평균</th><th>점수</th><th>정예</th><th>부캐</th><th>경고</th><th>선발</th></tr></thead>
<tbody>
{% for r in rows %}
<tr class="{{ 'elite' if r.is_elite else '' }} {{ 'below' if not r.meets_cutline else '' }} {{ 'excluded' if r.is_excluded else '' }}">
  <td>{{ r.rank }}</td><td>{{ r.member.name }}</td><td>{{ r.member.townhall }}</td>
  <td>{{ r.member.attacks }}</td><td>{{ r.member.missed }}</td><td>{{ r.member.stars }}</td>
  <td>{{ "%.2f"|format(r.member.star_avg) }}</td><td>{{ "%.1f"|format(r.member.score) }}</td>
  <td>{{ "●" if r.is_elite else "" }}</td><td>{{ "부캐" if r.is_alt else "" }}</td>
  <td>{{ r.warnings if r.warnings else "" }}</td><td>{{ r.selection or ("제외" if r.is_excluded else "미달" if not r.meets_cutline else "") }}</td>
</tr>
{% endfor %}
</tbody></table></div>
{% endmacro %}

{% macro war_grid(view) %}
<div class="scroll"><table class="grid">
<thead><tr><th>닉네임</th>
{% for w in view.wars %}<th><span class="date">{{ w.end_time|kst("%m/%d") }}</span><br><span class="type">{{ "리그" if w.war_type == "cwl" else "일반" }}</span><br><span class="opp">{{ w.opponent_name }}</span></th>{% endfor %}
</tr></thead>
<tbody>
{% for r, cells in view.grid %}
<tr class="{{ 'elite' if r.is_elite else '' }}"><td>{{ r.member.name }}</td>{% for c in cells %}<td class="cell">{{ c }}</td>{% endfor %}</tr>
{% endfor %}
</tbody></table></div>
{% endmacro %}
```

`src/coc_pointer/templates/index.html`:

```html
{% extends "base.html" %}
{% from "_tables.html" import rules_box, roster_table with context %}
{% block content %}
{{ rules_box() }}
{% if latest %}
<section>
  <h2>{{ latest.label }} 최종 선발 명단 ({{ latest.roster|length }}명)</h2>
  {{ roster_table(latest.roster) }}
  <p><a href="{{ latest.key }}/">{{ latest.label }} 전체 점수표 보기 →</a> · 반영된 클랜전 {{ latest.wars|length }}개</p>
</section>
{% else %}
<p class="empty">기록 없음. 아직 저장된 클랜전이 없습니다.</p>
{% endif %}
{% endblock %}
```

`src/coc_pointer/templates/month.html`:

```html
{% extends "base.html" %}
{% from "_tables.html" import rules_box, roster_table, score_table, war_grid with context %}
{% block title %}{{ view.label }} · {{ clan_name }}{% endblock %}
{% block content %}
{{ rules_box() }}
<section>
  <h2>{{ view.label }} 최종 선발 명단 ({{ view.roster|length }}명)</h2>
  {% if view.roster %}{{ roster_table(view.roster) }}{% else %}<p class="empty">커트라인을 넘은 멤버가 없습니다.</p>{% endif %}
</section>
<section>
  <h2>{{ view.label }} 월 점수표 (전원)</h2>
  {{ score_table(view.ranked) }}
</section>
<section>
  <h2>{{ view.label }} 클랜전별 기록 (칸: 공격별 별 수, x = 미공격, 빈칸 = 미참가)</h2>
  {{ war_grid(view) }}
</section>
{% endblock %}
```

`src/coc_pointer/templates/members.html`:

```html
{% extends "base.html" %}
{% block title %}클랜원 목록 · {{ clan_name }}{% endblock %}
{% block content %}
<section>
  <h2>클랜원 목록{% if snapshot %} ({{ snapshot.members|length }}명, {{ snapshot.fetched_at|kst("%Y-%m-%d %H:%M") }} 기준){% endif %}</h2>
  <p>플레이어 태그를 복사해 <code>config/clan.yaml</code>의 정예·부캐·제외 목록에 넣으세요. 태그는 따옴표로 감싸야 합니다.</p>
  {% if snapshot %}
  <div class="scroll"><table>
  <thead><tr><th>닉네임</th><th>플레이어 태그</th><th>역할</th><th>홀</th><th>트로피</th><th>기부</th><th>수령</th><th>설정</th></tr></thead>
  <tbody>
  {% for m in members %}
  <tr><td>{{ m.name }}</td><td><code>{{ m.tag }}</code></td><td>{{ m.role|role_ko }}</td><td>{{ m.townhall }}</td>
      <td>{{ m.trophies }}</td><td>{{ m.donations }}</td><td>{{ m.donations_received }}</td>
      <td>{{ "정예 " if config.is_elite(m.tag) }}{{ "부캐 " if config.is_alt(m.tag) }}{{ "제외 " if config.is_excluded(m.tag) }}{{ "경고%d"|format(config.warning_count(m.tag)) if config.warning_count(m.tag) }}</td></tr>
  {% endfor %}
  </tbody></table></div>
  {% else %}<p class="empty">기록 없음. 아직 클랜원 목록을 가져오지 못했습니다.</p>{% endif %}
</section>
{% endblock %}
```

`src/coc_pointer/templates/style.css`:

```css
:root { --elite: #fff3c4; --muted: #999; --line: #ddd; }
* { box-sizing: border-box; }
body { margin: 0; font-family: -apple-system, "Apple SD Gothic Neo", "Malgun Gothic", sans-serif; font-size: 14px; color: #222; background: #fafafa; }
header { padding: 12px 16px; background: #2b2d42; color: #fff; }
header h1 { margin: 0 0 6px; font-size: 18px; }
header a { color: #fff; text-decoration: none; }
nav a { display: inline-block; margin-right: 12px; opacity: .9; }
main { padding: 12px 16px; max-width: 1200px; margin: 0 auto; }
section { margin-bottom: 28px; }
h2 { font-size: 16px; margin: 0 0 8px; }
.rules { background: #fff; border: 1px solid var(--line); padding: 8px 12px; }
.rules ol { margin: 0; padding-left: 20px; }
.scroll { overflow-x: auto; }
table { border-collapse: collapse; background: #fff; white-space: nowrap; }
th, td { border: 1px solid var(--line); padding: 4px 8px; text-align: center; }
th { background: #f0f0f0; position: sticky; top: 0; }
tr.elite { background: var(--elite); }
tr.below { color: var(--muted); }
tr.excluded td { text-decoration: line-through; }
table.grid th .date { font-weight: bold; }
table.grid th .type, table.grid th .opp { font-weight: normal; font-size: 12px; color: #555; }
.cell { font-variant-numeric: tabular-nums; }
.empty { color: var(--muted); }
footer { padding: 16px; color: var(--muted); font-size: 12px; text-align: center; }
```

- [ ] **Step 4: render.py 구현**

`src/coc_pointer/render.py`:

```python
"""Turn stored data into the static site under ``site/``."""

from __future__ import annotations

import shutil
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
    RankedMember,
    aggregate_month,
    group_wars_by_month,
    rank_month,
    roster,
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
    grid: list[tuple[RankedMember, list[str]]]


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


def build_month_view(key: str, wars: list[War], config: ClanConfig) -> MonthView:
    ranked = rank_month(aggregate_month(wars), config)
    grid = [(r, [war_cell(w, r.member.tag) for w in wars]) for r in ranked]
    return MonthView(
        key=key, label=month_label(key), wars=wars, ranked=ranked, roster=roster(ranked), grid=grid
    )


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
    months = [build_month_view(k, ws, config) for k, ws in group_wars_by_month(wars).items()]
    latest = months[-1] if months else None
    generated_at = _kst(now or datetime.now(UTC), "%Y-%m-%d %H:%M")
    clan_name = snapshot.name if snapshot else "클랜"

    env = _env()
    common = {"months": months, "rules": RULES, "generated_at": generated_at, "clan_name": clan_name}
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
```

- [ ] **Step 5: 테스트 통과 확인**

Run: `uv run pytest tests/test_render.py -v`
Expected: 4 passed. 실패하면 템플릿의 문자열과 테스트 기대 문구(`기본 5점`, `공동 대표`, `기록 없음`, `2026년 9월`)가 일치하는지 먼저 확인한다.

- [ ] **Step 6: 브라우저로 눈으로 확인**

```bash
uv run python -c "
from pathlib import Path
from datetime import UTC, datetime
import sys; sys.path.insert(0, 'tests')
from helpers import member, war
from coc_pointer.config import ClanConfig
from coc_pointer.render import build_site
from coc_pointer.storage import save_war
d = Path('/private/tmp/claude-501/-Users-mzc01-circle-orca-workspaces-coc-pointer-candlefish/2ee8e68b-bd46-4c09-8735-895a934583ea/scratchpad/preview')
save_war(war([member('#P1','도토리',(3,3),18), member('#P2','제니',(2,1))]), d)
build_site(d, ClanConfig(clan_tag='#X', elite=frozenset({'#P1'})), d/'site')
print(d/'site'/'index.html')
"
open /private/tmp/claude-501/-Users-mzc01-circle-orca-workspaces-coc-pointer-candlefish/2ee8e68b-bd46-4c09-8735-895a934583ea/scratchpad/preview/site/index.html
```

Expected: 브라우저에 규칙 상자, 선발 명단 표, 상단 메뉴가 보인다. 표가 화면보다 넓으면 표 안에서만 가로 스크롤된다.

- [ ] **Step 7: 린트와 커밋**

```bash
uv run ruff check . && uv run ruff format .
git add src/coc_pointer/render.py src/coc_pointer/templates tests/test_render.py
git commit -m "정적 페이지 렌더러와 템플릿 추가

첫 페이지, 월별 페이지(선발 명단·월 점수표·클랜전별 기록), 클랜원 목록 페이지.
규칙 문구는 scoring.RULES를 그대로 표시한다.

Co-Authored-By: Claude Fable 5.1 <noreply@anthropic.com>
Claude-Session: https://claude.ai/code/session_01SEjU63ioVTGGo4ZeJ2B4wU"
```

---

### Task 10: 명령줄 진입점 (cli.py)

**Files:**
- Create: `src/coc_pointer/cli.py`
- Modify: `src/coc_pointer/__init__.py`
- Create: `config/clan.yaml`, `data/wars/.gitkeep`
- Modify: `.gitignore` (`site/` 추가)
- Test: `tests/test_cli.py`

**Interfaces:**
- Consumes: `CocApi` (Task 7), `collect`, `WarLogPrivateError` (Task 8), `build_site` (Task 9), `load_config`, `ConfigError` (Task 2)
- Produces:
  - `load_dotenv(path: Path) -> None` `.env`의 `KEY=VALUE` 줄을 환경 변수로 넣되 이미 있는 변수는 덮지 않음
  - `main(argv: list[str] | None = None) -> int` 종료 코드. 명령: `collect [--data-dir data] [--config config/clan.yaml]`, `build [--data-dir data] [--config config/clan.yaml] [--out site]`
  - `coc_pointer.main()`은 `sys.exit(cli.main())`

- [ ] **Step 1: 실패하는 테스트 작성**

`tests/test_cli.py`:

```python
from pathlib import Path

from helpers import member, war

from coc_pointer import cli
from coc_pointer.storage import save_war


def write_config(tmp_path: Path) -> Path:
    p = tmp_path / "clan.yaml"
    p.write_text('clan_tag: "#2C8L822LQ"\nelite:\n  - "#P1"\n', encoding="utf-8")
    return p


def test_build_command_writes_site(tmp_path, capsys):
    save_war(war([member("#P1", "도토리", (3, 3))]), tmp_path / "data")
    code = cli.main(
        ["build", "--data-dir", str(tmp_path / "data"), "--config", str(write_config(tmp_path)), "--out", str(tmp_path / "site")]
    )
    assert code == 0
    assert (tmp_path / "site" / "index.html").exists()
    assert "생성" in capsys.readouterr().out


def test_collect_requires_token(tmp_path, monkeypatch, capsys):
    monkeypatch.delenv("COC_API_TOKEN", raising=False)
    monkeypatch.chdir(tmp_path)  # no .env here
    code = cli.main(["collect", "--data-dir", str(tmp_path / "data"), "--config", str(write_config(tmp_path))])
    assert code == 2
    assert "COC_API_TOKEN" in capsys.readouterr().err


def test_bad_config_reports_and_fails(tmp_path, capsys):
    bad = tmp_path / "clan.yaml"
    bad.write_text('clan_tag: "#2C8L822LQ"\nelite:\n  - "#bad"\n', encoding="utf-8")
    code = cli.main(["build", "--data-dir", str(tmp_path), "--config", str(bad), "--out", str(tmp_path / "site")])
    assert code == 2
    assert "elite[0]" in capsys.readouterr().err


def test_load_dotenv_does_not_override_existing(tmp_path, monkeypatch):
    env = tmp_path / ".env"
    env.write_text("COC_API_TOKEN=from-file\nOTHER=1\n# comment\n", encoding="utf-8")
    monkeypatch.setenv("COC_API_TOKEN", "from-env")
    monkeypatch.delenv("OTHER", raising=False)
    cli.load_dotenv(env)
    import os

    assert os.environ["COC_API_TOKEN"] == "from-env"
    assert os.environ["OTHER"] == "1"
```

- [ ] **Step 2: 테스트 실패 확인**

Run: `uv run pytest tests/test_cli.py -v`
Expected: FAIL, `ImportError: cannot import name 'cli'`

- [ ] **Step 3: cli.py 구현과 진입점 연결**

`src/coc_pointer/cli.py`:

```python
"""Command line entry point: ``coc-pointer collect`` and ``coc-pointer build``."""

from __future__ import annotations

import argparse
import os
import sys
from pathlib import Path

from coc_pointer.api import CocApi, CocApiError
from coc_pointer.collect import WarLogPrivateError, collect
from coc_pointer.config import ConfigError, load_config
from coc_pointer.render import build_site

TOKEN_ENV = "COC_API_TOKEN"


def load_dotenv(path: Path) -> None:
    """Load ``KEY=VALUE`` lines from ``path`` without overriding existing variables."""
    if not path.exists():
        return
    for line in path.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, value = line.split("=", 1)
        os.environ.setdefault(key.strip(), value.strip())


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="coc-pointer", description="클랜전 점수 자동 집계")
    sub = parser.add_subparsers(dest="command", required=True)
    for name, help_ in (("collect", "API에서 끝난 클랜전을 저장"), ("build", "점수를 계산해 site/ 생성")):
        p = sub.add_parser(name, help=help_)
        p.add_argument("--data-dir", default="data", type=Path)
        p.add_argument("--config", default="config/clan.yaml", type=Path)
        if name == "build":
            p.add_argument("--out", default="site", type=Path)
    return parser


def _fail(message: str) -> int:
    print(f"오류: {message}", file=sys.stderr)
    return 2


def main(argv: list[str] | None = None) -> int:
    args = _parser().parse_args(argv)
    load_dotenv(Path(".env"))
    try:
        config = load_config(args.config)
    except (ConfigError, FileNotFoundError) as err:
        return _fail(str(err))

    if args.command == "collect":
        token = os.environ.get(TOKEN_ENV)
        if not token:
            return _fail(f"환경 변수 {TOKEN_ENV}이 없습니다. .env 파일이나 GitHub Secrets를 확인하세요.")
        try:
            with CocApi(token) as api:
                saved = collect(api, config, args.data_dir)
        except WarLogPrivateError as err:
            return _fail(str(err))
        except CocApiError as err:
            return _fail(f"API 호출 실패: {err}")
        print(f"완료: 새 클랜전 {len(saved)}개")
        return 0

    written = build_site(args.data_dir, config, args.out)
    print(f"생성: {len(written)}개 파일 → {args.out}")
    return 0
```

`src/coc_pointer/__init__.py`를 다음으로 교체:

```python
"""coc-pointer: Clash of Clans clan point score tracker."""

import sys


def main() -> None:
    from coc_pointer.cli import main as cli_main

    sys.exit(cli_main())
```

`config/clan.yaml`:

```yaml
# 관리자 설정. 태그는 반드시 따옴표로 감싼다 ('#'은 YAML 주석 기호).
# 플레이어 태그는 웹 페이지의 "클랜원 목록"에서 복사한다.
clan_tag: "#2C8L822LQ"

# 정예 멤버: 커트라인을 넘으면 선발 명단에 먼저 들어간다.
elite: []

# 부캐: 정예가 될 수 없다.
alts: []

# 제외: 표에는 보이지만 선발되지 않는다.
excluded: []

# 경고 횟수: 표시용. 예)  "#ABC123": 1
warnings: {}
```

`.gitignore`에 `site/` 한 줄을 추가하고, `data/wars/.gitkeep` 빈 파일을 만든다.

```bash
echo 'site/' >> .gitignore
mkdir -p data/wars && touch data/wars/.gitkeep
```

`tests/test_smoke.py`는 `main`이 callable인지만 보므로 그대로 둔다.

- [ ] **Step 4: 테스트 통과 확인**

Run: `uv run pytest -v`
Expected: 전체 통과 (Task 1~10 테스트 합계 약 44개)

- [ ] **Step 5: 실제 API로 수집 한 번 실행 (수동 검증)**

```bash
uv run coc-pointer collect
uv run coc-pointer build
ls data/wars | head
open site/index.html
```

Expected: `.env`의 토큰으로 클랜원 목록과 9월 리그전(끝난 라운드) 파일이 `data/wars/`에 생기고, `site/index.html`에 실제 닉네임과 점수가 보인다. 리그전은 멤버당 1회라 대부분 100점 근처로 나오는 것이 정상이다. 두 번째 `collect`는 "새 클랜전 0개"여야 한다.

- [ ] **Step 6: 린트와 커밋**

수집된 `data/` 파일도 함께 커밋한다 (저장소가 데이터베이스다).

```bash
uv run ruff check . && uv run ruff format .
git add src/coc_pointer/cli.py src/coc_pointer/__init__.py tests/test_cli.py config/clan.yaml data .gitignore
git commit -m "명령줄 진입점과 초기 설정 파일 추가

coc-pointer collect / build 명령, .env 로딩, config/clan.yaml 초기값.
첫 수집으로 받은 9월 리그전 데이터를 함께 넣는다.

Co-Authored-By: Claude Fable 5.1 <noreply@anthropic.com>
Claude-Session: https://claude.ai/code/session_01SEjU63ioVTGGo4ZeJ2B4wU"
```

---

### Task 11: GitHub Actions 자동 실행과 Pages 배포

**Files:**
- Create: `.github/workflows/collect.yml`
- Modify: `CLAUDE.md`, `README.md`

**Interfaces:**
- Consumes: `coc-pointer collect`, `coc-pointer build` (Task 10), 저장소 Secret `COC_API_TOKEN`

- [ ] **Step 1: 워크플로 작성**

`.github/workflows/collect.yml`:

```yaml
name: collect

on:
  schedule:
    - cron: "*/30 * * * *"
  workflow_dispatch:

permissions:
  contents: write
  pages: write
  id-token: write

concurrency:
  group: collect
  cancel-in-progress: false

jobs:
  collect-and-deploy:
    runs-on: ubuntu-latest
    environment:
      name: github-pages
      url: ${{ steps.deploy.outputs.page_url }}
    steps:
      - uses: actions/checkout@v4

      - uses: astral-sh/setup-uv@v6
        with:
          enable-cache: true

      - name: Install
        run: uv sync --frozen

      - name: Collect finished wars
        env:
          COC_API_TOKEN: ${{ secrets.COC_API_TOKEN }}
        run: uv run coc-pointer collect

      - name: Build site
        run: uv run coc-pointer build

      - name: Commit new data
        run: |
          git config user.name "github-actions[bot]"
          git config user.email "41898282+github-actions[bot]@users.noreply.github.com"
          git add data
          if git diff --cached --quiet; then
            echo "no new data"
          else
            git commit -m "data: 클랜전 수집 $(date -u +%Y-%m-%dT%H:%MZ)"
            git push
          fi

      - uses: actions/configure-pages@v5
      - uses: actions/upload-pages-artifact@v3
        with:
          path: site
      - id: deploy
        uses: actions/deploy-pages@v4
```

- [ ] **Step 2: 워크플로 문법 검사**

```bash
uv run python -c "import yaml, pathlib; yaml.safe_load(pathlib.Path('.github/workflows/collect.yml').read_text()); print('yaml ok')"
```

Expected: `yaml ok`

- [ ] **Step 3: CLAUDE.md와 README.md 갱신**

`CLAUDE.md`의 `## Layout` 아래에 다음 절을 추가하고, `## Current state` 절을 교체한다.

```markdown
## Data flow

`coc-pointer collect` (src/coc_pointer/collect.py) fetches finished wars from the CoC API through the RoyaleAPI proxy and writes one JSON per war to `data/wars/` plus `data/clan.json`. `coc-pointer build` (render.py) reads `data/` and `config/clan.yaml`, scores each month with the pure functions in `scoring.py`, and writes static HTML to `site/` (gitignored). `.github/workflows/collect.yml` runs both every 30 minutes and on manual dispatch, commits new `data/` files, and deploys `site/` to GitHub Pages.

- Scoring rules live only in `scoring.py` (module docstring + `RULES`); templates display `RULES` verbatim. Change rules there and nowhere else.
- Members are keyed by player tag, never by name.
- `config/clan.yaml` is the admin surface: tags must be quoted (`#` is a YAML comment).
- The API token comes from `COC_API_TOKEN` (local `.env`, gitignored; Actions secret). The proxy rejects requests without a User-Agent.
- Spec: `docs/superpowers/specs/2026-09-07-coc-pointer-design.md`.

## Current state

Pipeline is implemented end to end. Historical Excel data is not imported; only wars collected by the workflow exist in `data/`.
```

`README.md`를 다음으로 교체:

```markdown
# coc-pointer

클래시 오브 클랜 클랜 "미니언즈"의 클랜전 활동 점수와 리그전 30인 선발 명단을 자동으로 집계합니다.

- 결과 페이지: https://circlebro.github.io/coc-pointer/
- 관리자 설정: `config/clan.yaml` (정예·부캐·제외·경고). GitHub 웹에서 고치면 다음 실행에 반영됩니다.
- 즉시 갱신: 저장소 Actions 탭 → `collect` → Run workflow

개발 명령은 `CLAUDE.md`를 참고하세요.
```

- [ ] **Step 4: 커밋과 푸시, PR 생성**

```bash
uv run ruff check . && uv run pytest -q
git add .github/workflows/collect.yml CLAUDE.md README.md
git commit -m "GitHub Actions 수집·배포 워크플로 추가

30분마다와 수동 실행으로 collect → build → data 커밋 → Pages 배포.
CLAUDE.md에 데이터 흐름을, README에 페이지 주소와 관리 방법을 적는다.

Co-Authored-By: Claude Fable 5.1 <noreply@anthropic.com>
Claude-Session: https://claude.ai/code/session_01SEjU63ioVTGGo4ZeJ2B4wU"
git push -u origin design-spec
gh auth switch --user circlebro
gh pr create --base main --head design-spec --title "클랜전 점수 자동 집계 파이프라인 구현" --body "$(cat <<'EOF'
## 요약

- CoC API(RoyaleAPI 프록시)에서 끝난 일반 클랜전·리그전을 수집해 `data/wars/`에 저장
- 엑셀 규칙 그대로 월별 점수·커트라인·30인 선발 명단 계산 (`scoring.py`, 실제 8월 표로 검산)
- 첫 페이지, 월별 페이지, 클랜원 목록 페이지를 정적 HTML로 생성
- GitHub Actions가 30분마다와 수동으로 수집·빌드·커밋·Pages 배포

설계: `docs/superpowers/specs/2026-09-07-coc-pointer-design.md`

## 테스트 계획

- [x] `uv run pytest` 전체 통과
- [x] `uv run ruff check .` 통과
- [x] 로컬에서 실제 API로 `collect` → `build` 실행, 9월 리그전 데이터 확인
- [ ] 머지 후 Actions 수동 실행 성공, Pages 주소에서 페이지 확인

🤖 Generated with [Claude Code](https://claude.com/claude-code)

https://claude.ai/code/session_01SEjU63ioVTGGo4ZeJ2B4wU
EOF
)"
```

- [ ] **Step 5: 머지 후 Pages 켜기와 첫 실행**

PR을 스쿼시 머지한 다음 (사용자 선호: `gh pr merge --squash`):

```bash
gh api -X POST repos/circlebro/coc-pointer/pages -f build_type=workflow 2>/dev/null || echo "already enabled"
gh workflow run collect --repo circlebro/coc-pointer
sleep 90
gh run list --repo circlebro/coc-pointer --workflow collect --limit 1
```

Expected: 실행이 `completed success`. 그 뒤 https://circlebro.github.io/coc-pointer/ 에서 페이지가 보인다. 실패하면 `gh run view --log-failed`로 원인을 본다. 흔한 원인: Pages가 아직 "GitHub Actions" 소스로 설정되지 않음(저장소 Settings → Pages에서 확인), Secret 이름 오타.

---

## 자체 점검 결과

**Spec 커버리지:**
- 2.1 수집기 → Task 7, 8. User-Agent, 끝난 클랜전만, clan/opponent 판별, 중복 방지, `#0` 건너뛰기 포함.
- 2.2 계산기 → Task 3, 4, 5. RULES 한 곳 정의.
- 2.3 렌더러 → Task 9.
- 3.1~3.4 데이터 형식 → Task 1 (모델), Task 6 (저장), Task 2 (설정), 태그 기준 식별은 Task 4.
- 4.x 점수 규칙 → Task 3 (공식·월 귀속·커트라인), Task 5 (선발·부캐·제외·경고·동점), 표시 형식은 Task 9 템플릿의 `%.1f`/`%.2f`.
- 5.1~5.3 페이지 → Task 9. 첫 페이지 규칙·명단·링크·갱신 시각, 월별 3표, 클랜원 목록(태그·역할·설정 열).
- 6 Actions → Task 11.
- 7 오류 처리 → Task 7 (CocApiError), Task 8 (WarLogPrivateError, 진행 중 건너뜀, leaguegroup 404), Task 10 (설정 오류·토큰 없음 메시지), Task 9 (기록 없음).
- 9 테스트 → 각 Task의 Step 1.
- 10 준비 목록 → Task 11 Step 5 (Pages), 플레이어 태그는 운영 중 `config/clan.yaml`로.

**타입 일관성:** `RankedMember.selection`은 `"정예"|"선발"|None`으로 Task 5, 9 템플릿에서 동일. `War.attacks_per_member`는 Task 1 정의, Task 4 집계, Task 8 변환(regular 2, cwl 1), Task 9 `war_cell`에서 같은 이름. `load_wars`/`save_war` 시그니처는 Task 6 정의와 Task 8, 9, 10 사용이 일치.
