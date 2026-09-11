"""apps/api 는 Cloudflare Workers(Pyodide, 파이썬 3.13.2)에 배포된다. 로컬과
CI 는 3.14 로 도므로, 3.14 전용 문법(예: PEP 758 의 `except A, B:`)이 섞여
들어가도 테스트는 조용히 통과하고 `uv run pywrangler deploy` 를 돌릴 때가
되어서야 실패한다. 이 테스트는 3.13 파서로 소스를 다시 파싱해 그 문법을 훨씬
전에, 이 컴퓨터에 3.13 이 설치되어 있지 않아도 잡아낸다.

packages/core/tests/test_py313_syntax.py 에 같은 일을 하는 테스트가 따로 있다.
그쪽은 packages/core 자기 소스만 보고 이쪽은 apps/api 자기 소스만 본다. 한쪽이
다른 쪽을 들여다보면 앱과 공용 코드 사이의 경계가 무너지기 때문에 일부러 두
벌로 둔다.

파일 이름을 굳이 다르게 지은 이유가 있다. tests/ 에 __init__.py 가 없어서
pytest 가 파일 이름을 그대로 모듈 이름으로 삼는데, 두 파일 이름이 같으면
저장소 전체를 한 번에 돌릴 때 "import file mismatch" 로 수집 단계에서 멈춘다.
이름을 통일하고 싶어지더라도 그대로 두는 편이 낫다.
"""

import ast
from pathlib import Path

import pytest

SRC_ROOT = Path(__file__).resolve().parent.parent / "src"


def _source_files() -> list[Path]:
    # src/coc_core 는 deploy.sh 가 만드는 배포용 복사본이라 진짜 소스가 아니다.
    # 원본은 packages/core 쪽 같은 이름의 테스트가 이미 검사한다.
    return sorted(p for p in SRC_ROOT.rglob("*.py") if "coc_core" not in p.parts)


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
