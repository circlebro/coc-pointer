import httpx
import pytest

from coc_pointer.api import USER_AGENT, CocApi, CocApiError, encode_tag


def make_api(handler):
    return CocApi(token="tok", transport=httpx.MockTransport(handler))


def test_encode_tag():
    assert encode_tag("#2C8L822LQ") == "%232C8L822LQ"


def test_get_sends_auth_and_user_agent_and_returns_json():
    seen = {}

    def handler(request: httpx.Request) -> httpx.Response:
        seen["url"] = str(request.url)
        seen["auth"] = request.headers["Authorization"]
        seen["ua"] = request.headers["User-Agent"]
        return httpx.Response(200, json={"name": "미니언즈"})

    with make_api(handler) as api:
        assert api.clan("#2C8L822LQ") == {"name": "미니언즈"}
    assert seen["url"] == "https://cocproxy.royaleapi.dev/v1/clans/%232C8L822LQ"
    assert seen["auth"] == "Bearer tok"
    assert seen["ua"] == USER_AGENT


def test_404_returns_none_for_league_group():
    def handler(request):
        return httpx.Response(404, json={"reason": "notFound"})

    with make_api(handler) as api:
        assert api.league_group("#2C8L822LQ") is None


def test_403_raises_with_reason_and_message():
    def handler(request):
        return httpx.Response(
            403,
            json={
                "reason": "accessDenied",
                "message": "Invalid authorization",
            },
        )

    with make_api(handler) as api, pytest.raises(CocApiError) as exc:
        api.current_war("#2C8L822LQ")
    err = exc.value
    assert err.status == 403 and err.reason == "accessDenied" and "currentwar" in err.path
    assert "Invalid authorization" in str(err)


def test_cwl_war_path_encodes_tag():
    def handler(request):
        # httpx normalizes .path to decoded form, so check raw_path for encoding
        raw = (
            request.url.raw_path.decode("utf-8")
            if isinstance(request.url.raw_path, bytes)
            else request.url.raw_path
        )
        assert raw == "/v1/clanwarleagues/wars/%238GVJQPUUR"
        return httpx.Response(200, json={"state": "warEnded"})

    with make_api(handler) as api:
        assert api.cwl_war("#8GVJQPUUR")["state"] == "warEnded"
