# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project

coc-pointer: a Clash of Clans (CoC) clan point score tracker. Python 3.14, managed with `uv`. Licensed under MIT.

## Commands

`uv` owns the virtualenv and the Python interpreter (pinned in `.python-version`); never call `pip` or a system `python3` directly.

```bash
uv sync                          # create .venv and install all deps (incl. dev group)
uv run coc-pointer               # run the CLI entry point (src/coc_pointer/__init__.py:main)
uv run pytest                    # run all tests
uv run pytest tests/test_smoke.py::test_package_imports   # run a single test
uv run ruff check .              # lint
uv run ruff format .             # format (use --check in CI)
uv add <pkg>                     # add a runtime dependency
uv add --dev <pkg>               # add a dev-only dependency
```

## Layout

- `src/coc_pointer/`: the package (src layout; installed into `.venv` in editable mode by `uv sync`).
- `tests/`: pytest suite. Test discovery is limited to this directory via `[tool.pytest.ini_options]`.
- `pyproject.toml`: single source of truth for metadata, dependencies, ruff, and pytest config. `uv.lock` is committed.

## Data flow

`coc-pointer collect` (src/coc_pointer/collect.py) fetches finished wars from the CoC API through the RoyaleAPI proxy and writes one JSON per war to `data/wars/` plus `data/clan.json`. `coc-pointer build` (render.py) reads `data/` and `config/clan.yaml`, scores each month with the pure functions in `scoring.py`, and writes static HTML to `site/` (gitignored). `.github/workflows/collect.yml` runs both every 30 minutes and on manual dispatch, commits new `data/` files, and deploys `site/` to GitHub Pages.

- Scoring rules live only in `scoring.py` (module docstring + `RULES`); templates display `RULES` verbatim. Change rules there and nowhere else.
- Members are keyed by player tag, never by name.
- `config/clan.yaml` is the admin surface: tags must be quoted (`#` is a YAML comment).
- The API token comes from `COC_API_TOKEN` (local `.env`, gitignored; Actions secret). The proxy rejects requests without a User-Agent.
- Spec: `docs/superpowers/specs/2026-09-07-coc-pointer-design.md`.

## Current state

Pipeline is implemented end to end. Historical Excel data is not imported; only wars collected by the workflow exist in `data/`.

## Commit convention

Commit subjects use a Conventional Commits type in ASCII, followed by a Korean summary.

| Type | 쓰임 |
|---|---|
| `feat` | 새 기능 |
| `fix` | 버그 수정 |
| `chore` | 설정, 빌드, 잡무 |
| `docs` | 문서 |
| `refactor` | 동작 변경 없는 구조 개선 |
| `test` | 테스트만 추가·수정 |

Example: `feat: 진행 중 클랜전을 실시간으로 반영`

The body explains what changed and why, as Korean bullets, so `git log` alone shows which
feature was built. PRs are squash-merged, so the PR title follows the same format — it
becomes the commit on `main`. Keep the `Co-Authored-By` and `Claude-Session` trailers.

## Git

- Default branch: `main`. Open PRs against it.
- Work happens in git worktrees under `~/orca/workspaces/coc-pointer/`; each worktree is on its own feature branch.
