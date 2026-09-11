"""배포 번들에 실려야 할 꾸러미가 빠지지 않았는지 본다.

apps/api 는 coc_core 를 의존성으로 선언하지 않는다. Cloudflare Workers 에는
그 wasm 휠이 없어 설치가 실패하기 때문이며, 대신 deploy.sh 가 소스를 그대로
복사해 넣는다.

그 대가로 구멍이 하나 생긴다. 번들을 만드는 pywrangler 는 pyproject.toml 의
dependencies 만 읽으므로, 복사해 넣은 coc_core 가 안에서 무엇을 부르는지 알
방법이 없다. 그래서 그 꾸러미가 번들에서 빠지고, 배포는 성공한 것처럼 끝난
뒤 첫 요청에서 ModuleNotFoundError 로 죽는다. 실제로 pyyaml 이 그렇게 빠져
/api/health 가 "No module named 'yaml'" 을 돌려준 적이 있다.

로컬에서는 드러나지 않는다. 워크스페이스의 다른 앱이 coc_core 를 의존성으로
갖고 있어 같은 가상환경에 이미 설치되어 있기 때문이다. 그래서 여기서 본다.
"""

from __future__ import annotations

import ast
import sys
import tomllib
from pathlib import Path

import pytest

HERE = Path(__file__).resolve().parent
API_PYPROJECT = HERE.parent / "pyproject.toml"
CORE_SRC = HERE.parent.parent.parent / "packages" / "core" / "src" / "coc_core"

# 꾸러미 이름과 들여오는 이름이 다른 것들
DISTRIBUTION_NAME = {"yaml": "pyyaml"}

# 표준 라이브러리지만 Workers 에서는 따로 실어야 하는 것들. 모듈 자체는 파이썬에
# 딸려 오는데 자료가 없어서, 보통은 운영체제가 가진 것을 읽는다. Pyodide 에는
# 그것이 없다.
NEEDS_DATA_PACKAGE = {"zoneinfo": "tzdata"}


def _imported_packages() -> set[str]:
    """coc_core 가 부르는 바깥 꾸러미 이름."""
    found: set[str] = set()
    for path in sorted(CORE_SRC.rglob("*.py")):
        tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                found.update(a.name.split(".")[0] for a in node.names)
            elif isinstance(node, ast.ImportFrom) and node.level == 0 and node.module:
                found.add(node.module.split(".")[0])
    return {
        name
        for name in found
        if name != "coc_core"
        and (name not in sys.stdlib_module_names or name in NEEDS_DATA_PACKAGE)
    }


def _declared() -> set[str]:
    """apps/api 가 배포 번들에 넣겠다고 선언한 것."""
    data = tomllib.loads(API_PYPROJECT.read_text(encoding="utf-8"))
    names = set()
    for spec in data["project"]["dependencies"]:
        names.add(spec.split(">")[0].split("<")[0].split("=")[0].split("[")[0].strip().lower())
    return names


@pytest.mark.parametrize("module", sorted(_imported_packages()))
def test_coc_core_가_쓰는_것이_번들에_들어간다(module: str) -> None:
    wanted = NEEDS_DATA_PACKAGE.get(module) or DISTRIBUTION_NAME.get(module, module)
    wanted = wanted.lower()

    assert wanted in _declared(), (
        f"coc_core 가 {module} 을 부르는데 apps/api/pyproject.toml 의 dependencies 에"
        f" {wanted} 가 없습니다. 이대로 배포하면 번들에 실리지 않아 첫 요청에서"
        f" ModuleNotFoundError 로 죽습니다."
    )
