"""coc-pointer 공용 코드.

자료형(models), 설정(config), 점수 계산(scoring), 보상 판정(rewards)이 여기 있다.
정적 페이지를 만드는 apps/web 과 API 서버인 apps/api 가 함께 쓴다.

이 패키지는 apps/api 를 통해 Cloudflare Workers(Pyodide, 파이썬 3.13.2 고정)에서도
돈다 — 3.14 전용 문법(예: 괄호 없는 `except A, B:`)을 쓰면 여기서는 아무 문제 없이
테스트가 통과해도 배포할 때 가서야 실패한다. `requires-python`은 `>=3.13`으로
두고, `tests/test_py313_syntax.py`가 이를 테스트에서 잡는다.
"""
