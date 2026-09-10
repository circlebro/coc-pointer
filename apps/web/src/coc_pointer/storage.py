"""Read and write the ``data/`` directory (the repository is the database)."""

from __future__ import annotations

import json
from pathlib import Path

from coc_core.models import ClanSnapshot, War

WARS_DIR = "wars"
IN_PROGRESS_DIR = "in-progress"
CLAN_FILE = "clan.json"


def _dump(path: Path, payload: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def save_war(war: War, data_dir: Path) -> Path | None:
    """Write ``war`` as JSON and return its path, or ``None`` if nothing was written.

    A finished war lands in ``wars/`` and is never rewritten, so the record is immutable
    and git keeps one commit per war. An unfinished war lands in ``in-progress/`` instead
    and is refreshed on every run; that directory is git-ignored because its contents
    change constantly and are re-fetched from the API anyway. When the war finishes, the
    final record is written to ``wars/`` and the in-progress copy is removed.
    """
    if war.in_progress:
        path = data_dir / IN_PROGRESS_DIR / war.file_name
        _dump(path, war.to_dict())
        return path

    path = data_dir / WARS_DIR / war.file_name
    if path.exists():
        return None
    _dump(path, war.to_dict())
    (data_dir / IN_PROGRESS_DIR / war.file_name).unlink(missing_ok=True)
    return path


def _read_wars(folder: Path) -> list[War]:
    if not folder.is_dir():
        return []
    return [War.from_dict(json.loads(p.read_text(encoding="utf-8"))) for p in folder.glob("*.json")]


def load_wars(data_dir: Path) -> list[War]:
    """Finished wars plus any unfinished ones we do not already have a final record for."""
    wars = _read_wars(data_dir / WARS_DIR)
    finished = {w.file_name for w in wars}
    wars += [w for w in _read_wars(data_dir / IN_PROGRESS_DIR) if w.file_name not in finished]
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
