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
uv run pytest packages/core/tests/test_scoring.py -k excel  # run one test
uv run ruff check .              # lint
uv run ruff format .             # format (use --check in CI)
uv add <pkg>                     # add a runtime dependency
uv add --dev <pkg>               # add a dev-only dependency
```

## Layout

The repository holds one deployable app per folder under `apps/`, code shared by two apps
under `packages/`, and shared inputs at the root.

- `apps/web/`: Python app — collects wars and renders the static site.
  - `src/coc_pointer/`: the package (src layout), including `templates/`.
  - `tests/`: pytest suite.
  - `pyproject.toml`: the package's own metadata and dependencies.
- `packages/core/`: Python package `coc_core` — models, config, scoring, rewards, plus
  `testing.py` with the War/WarMember builders both test suites use. Depends on nothing
  in `apps/`; both apps depend on it.
- `apps/api/`: Cloudflare Workers app — stores the CWL bonus draw and admin settings.
  `draw.js` is the whole server; `wrangler.toml` configures it; `deploy.sh` deploys it.
- `config/`, `data/`: shared inputs, not owned by either app.
- Root `pyproject.toml` declares a `uv` workspace, so `uv run`, `uv run pytest` and
  `uv run ruff` all work from the repository root. `uv.lock` lives at the root and is committed.

## Data flow

`coc-pointer collect` (apps/web/src/coc_pointer/collect.py) fetches finished wars from the CoC API through the RoyaleAPI proxy and writes one JSON per war to `data/wars/` plus `data/clan.json`. `coc-pointer build` (apps/web/src/coc_pointer/render.py) reads `data/` and `config/clan.yaml`, scores each month with the pure functions in `coc_core.scoring`, and writes static HTML to `site/` (gitignored). `.github/workflows/collect.yml` runs both every 30 minutes and on manual dispatch, commits new `data/` files, and deploys `site/` to GitHub Pages.

- Scoring rules live only in `packages/core/src/coc_core/scoring.py` (module docstring + `RULES`); templates display `RULES` verbatim. Change rules there and nowhere else.
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

## Releases

Every deploy that is worth naming gets a git tag and a GitHub release, so it is clear which
version put which change in front of the clan.

- Version is `0.MINOR.PATCH` while the project is still taking shape. A new feature bumps
  MINOR; a fix-only deploy bumps PATCH. `1.0.0` waits until the site fully replaces the
  spreadsheet it was built to replace.
- Releasing, in order: bump `version` in `apps/web/pyproject.toml` and `packages/core/pyproject.toml`,
  and `API_VERSION` in `apps/api/wrangler.toml` (all track the tag), commit, then tag the squash commit on
  `main` with `git tag -a v0.6.0 <sha> -m "<한 줄 요약>"`, push tags, and `gh release create`
  with Korean notes listing the PRs it contains.
- The site footer prints the installed `apps/web` version and links to that release, so the
  page itself says which build a viewer is looking at. `GET /api/health` reports the same
  number as the API's `version` — Workers has no startup log, so that endpoint stands in for
  one. The tag, the two `pyproject.toml` versions and `API_VERSION` all carry the same value,
  which is what ties a deployed build back to a point in the repository.
- The Obsidian vault mirrors this: `릴리즈/` holds one note per version and each ticket
  carries a `버전` property, so a ticket shows which release shipped it.

## Git

- Default branch: `main`. Open PRs against it.
- Work happens in git worktrees under `~/orca/workspaces/coc-pointer/`; each worktree is on its own feature branch.
