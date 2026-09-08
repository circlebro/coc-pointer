"""Thin client for the Clash of Clans API via the RoyaleAPI proxy.

The proxy's Cloudflare front rejects requests without a normal User-Agent, so one is
always sent. Tokens are IP-bound; the proxy IP 45.79.218.79 must be allowed on the key.
"""

from __future__ import annotations

from typing import Any
from urllib.parse import quote

import httpx

PROXY_BASE_URL = "https://cocproxy.royaleapi.dev/v1"
USER_AGENT = "coc-pointer/0.1"


class CocApiError(Exception):
    def __init__(self, status: int, path: str, reason: str, message: str) -> None:
        self.status = status
        self.path = path
        self.reason = reason
        self.message = message
        super().__init__(f"HTTP {status} {reason} on {path}: {message}")


def encode_tag(tag: str) -> str:
    return quote(tag, safe="")


class CocApi:
    def __init__(
        self,
        token: str,
        base_url: str = PROXY_BASE_URL,
        transport: httpx.BaseTransport | None = None,
    ) -> None:
        self._client = httpx.Client(
            base_url=base_url,
            headers={
                "Authorization": f"Bearer {token}",
                "User-Agent": USER_AGENT,
                "Accept": "application/json",
            },
            timeout=30.0,
            transport=transport,
        )

    def close(self) -> None:
        self._client.close()

    def __enter__(self) -> CocApi:
        return self

    def __exit__(self, *exc: object) -> None:
        self.close()

    def get(self, path: str) -> dict[str, Any] | None:
        response = self._client.get(path)
        if response.status_code == 404:
            return None
        if response.status_code >= 400:
            try:
                body = response.json()
            except ValueError:
                body = {}
            raise CocApiError(
                status=response.status_code,
                path=path,
                reason=str(body.get("reason", "unknown")),
                message=str(body.get("message", response.text[:200])),
            )
        return response.json()

    def _require(self, path: str) -> dict[str, Any]:
        data = self.get(path)
        if data is None:
            raise CocApiError(404, path, "notFound", "리소스를 찾을 수 없습니다")
        return data

    def clan(self, tag: str) -> dict[str, Any]:
        return self._require(f"/clans/{encode_tag(tag)}")

    def current_war(self, tag: str) -> dict[str, Any]:
        return self._require(f"/clans/{encode_tag(tag)}/currentwar")

    def league_group(self, tag: str) -> dict[str, Any] | None:
        return self.get(f"/clans/{encode_tag(tag)}/currentwar/leaguegroup")

    def cwl_war(self, war_tag: str) -> dict[str, Any]:
        return self._require(f"/clanwarleagues/wars/{encode_tag(war_tag)}")
