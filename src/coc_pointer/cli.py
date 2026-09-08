"""Command line entry point: ``coc-pointer collect`` and ``coc-pointer build``."""

from __future__ import annotations

import argparse
import os
import sys
from pathlib import Path

from coc_pointer.api import CocApi, CocApiError
from coc_pointer.collect import WarLogPrivateError, collect
from coc_pointer.config import ClanConfig, ConfigError, load_clan_tag, load_config
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
    for name, help_ in (
        ("collect", "API에서 끝난 클랜전을 저장"),
        ("build", "점수를 계산해 site/ 생성"),
    ):
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

    if args.command == "collect":
        try:
            clan_tag = load_clan_tag(args.config)
        except (ConfigError, FileNotFoundError) as err:
            return _fail(str(err))
        config = ClanConfig(clan_tag=clan_tag)
        token = os.environ.get(TOKEN_ENV)
        if not token:
            return _fail(
                f"환경 변수 {TOKEN_ENV}이 없습니다. .env 파일이나 GitHub Secrets를 확인하세요."
            )
        try:
            with CocApi(token) as api:
                saved = collect(api, config, args.data_dir)
        except WarLogPrivateError as err:
            return _fail(str(err))
        except CocApiError as err:
            return _fail(f"API 호출 실패: {err}")
        print(f"완료: 새 클랜전 {len(saved)}개")
        return 0

    try:
        config = load_config(args.config)
    except (ConfigError, FileNotFoundError) as err:
        return _fail(str(err))
    written = build_site(args.data_dir, config, args.out)
    print(f"생성: {len(written)}개 파일 → {args.out}")
    return 0
