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

## Current state

Only the scaffold exists: `main()` prints a placeholder and there is one smoke test. No CoC API client, scoring logic, or storage yet. When those are added, extend this file with how clan/player data is fetched, scored, and stored, and where the CoC API token is expected to come from.

## Git

- Default branch: `main`. Open PRs against it.
- Work happens in git worktrees under `~/orca/workspaces/coc-pointer/`; each worktree is on its own feature branch.
