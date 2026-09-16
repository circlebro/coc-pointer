"""운영 표면을 지키는 검사.

**임시 조치다.** 제대로 된 로그인은 TASK-23(사용자 관리)이 맡는다. 그때까지
운영 표면을 열어 둘 수 없어 비밀번호 하나로 막아 둔다.

지금 방식이 약한 곳은 셋이다.

- **한 벌을 모두가 나눠 쓴다.** 누가 무엇을 했는지 알 수 없다
- **새어 나가도 알 수 없다.** 만료도 회수도 없다
- **머무름이 없다.** 요청마다 다시 보내야 하므로 화면이 그것을 들고 있어야 한다

그래도 아무나 부르는 것보다는 낫고, 로그인이 생기면 이 파일만 갈아 끼우면 된다.
검사를 거는 자리가 worker.py 한 줄이기 때문이다.

**비밀번호는 ASCII 여야 한다.** HTTP 헤더가 ASCII 만 담기 때문이다. 한글로 정하면
브라우저가 요청을 보내지도 못하고, 서버가 거부하는 것이 아니라 아예 나가지 않아
쓰는 사람은 무엇이 잘못됐는지 알 길이 없다.
"""

from __future__ import annotations

import hmac
from typing import Any

from fastapi import HTTPException, Request

HEADER = "X-Admin-Password"


def require_admin(request: Request) -> None:
    """운영 표면을 부를 자격이 있는지 본다.

    비밀값이 설정되어 있지 않으면 **모두 막는다.** 열어 두는 쪽으로 기울면,
    설정을 빠뜨린 배포가 조용히 운영 표면을 공개해 버린다. 막아 두면 곧바로
    드러난다.
    """
    env: Any = request.scope["env"]
    expected = getattr(env, "ADMIN_PASSWORD", None)
    if not expected:
        raise HTTPException(
            status_code=503,
            detail="운영 비밀번호가 설정되지 않아 이 요청을 받을 수 없습니다",
        )

    given = request.headers.get(HEADER, "")
    # 한 글자씩 견주면 걸린 시간으로 앞자리를 알아낼 수 있다. 길이가 달라도
    # 같은 시간이 걸리게 견준다.
    if not hmac.compare_digest(given, str(expected)):
        raise HTTPException(status_code=401, detail="비밀번호가 맞지 않습니다")
