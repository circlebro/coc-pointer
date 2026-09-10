"""packages/core 는 GitHub Actions/로컬(파이썬 3.14)뿐 아니라 Cloudflare
Workers(Pyodide, 파이썬 3.13.2)에서도 돈다. 배포는 `uv run pywrangler
sync`/`deploy` 단계에서만 3.13을 확인하므로, 3.14 전용 문법(예: PEP 758의
`except A, B:`)이 섞여 들어가도 로컬 테스트·CI는 조용히 통과하고 배포할 때가
되어서야 실패한다. 이 테스트는 3.13 파서로 소스를 다시 파싱해 그 문법을 훨씬
전에, 이 컴퓨터에 3.13이 설치되어 있지 않아도 잡아낸다.
"""

import ast
from pathlib import Path

import pytest

SRC_ROOT = Path(__file__).resolve().parent.parent / "src" / "coc_core"


def _source_files() -> list[Path]:
    return sorted(SRC_ROOT.rglob("*.py"))


@pytest.mark.parametrize("path", _source_files(), ids=lambda p: str(p.relative_to(SRC_ROOT)))
def test_parses_under_python_3_13(path: Path) -> None:
    source = path.read_text(encoding="utf-8")
    try:
        ast.parse(source, filename=str(path), feature_version=(3, 13))
    except SyntaxError as exc:
        pytest.fail(
            f"{path.relative_to(SRC_ROOT)} uses syntax that Python 3.13 (Cloudflare "
            f"Workers) can't parse: {exc}"
        )
