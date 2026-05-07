from __future__ import annotations

from urllib.parse import parse_qs, urlparse

import httpx
import pytest

from tiktok_autopost.auth import TikTokAuth


@pytest.fixture
def auth() -> TikTokAuth:
    return TikTokAuth(
        client_key="ck_test",
        client_secret="cs_test",
        redirect_uri="https://example.com/cb",
    )


def test_build_auth_url_includes_required_params(auth: TikTokAuth) -> None:
    url, state = auth.build_auth_url(state="fixed-state")

    parsed = urlparse(url)
    assert parsed.scheme == "https"
    assert parsed.netloc == "www.tiktok.com"
    assert parsed.path == "/v2/auth/authorize/"

    q = parse_qs(parsed.query)
    assert q["client_key"] == ["ck_test"]
    assert q["redirect_uri"] == ["https://example.com/cb"]
    assert q["response_type"] == ["code"]
    assert q["state"] == ["fixed-state"]
    assert q["scope"] == ["user.info.basic,video.publish"]
    assert state == "fixed-state"


def test_build_auth_url_generates_state_when_omitted(auth: TikTokAuth) -> None:
    url1, s1 = auth.build_auth_url()
    url2, s2 = auth.build_auth_url()
    assert s1 != s2
    assert s1 in url1
    assert s2 in url2


def test_build_auth_url_respects_custom_scopes(auth: TikTokAuth) -> None:
    url, _ = auth.build_auth_url(scopes=["video.upload", "user.info.basic"])
    q = parse_qs(urlparse(url).query)
    assert q["scope"] == ["video.upload,user.info.basic"]


async def test_exchange_code_posts_form_payload(monkeypatch: pytest.MonkeyPatch) -> None:
    captured: dict[str, object] = {}

    def handler(request: httpx.Request) -> httpx.Response:
        captured["url"] = str(request.url)
        captured["method"] = request.method
        captured["headers"] = dict(request.headers)
        captured["body"] = request.content.decode()
        return httpx.Response(
            200,
            json={
                "access_token": "at",
                "refresh_token": "rt",
                "expires_in": 86400,
                "open_id": "open-id",
                "scope": "user.info.basic,video.publish",
                "token_type": "Bearer",
            },
        )

    transport = httpx.MockTransport(handler)
    real_async_client = httpx.AsyncClient

    def patched(*args: object, **kwargs: object) -> httpx.AsyncClient:
        return real_async_client(*args, transport=transport, **kwargs)  # type: ignore[arg-type]

    monkeypatch.setattr("tiktok_autopost.auth.httpx.AsyncClient", patched)

    auth = TikTokAuth("ck", "cs", "https://example.com/cb")
    tokens = await auth.exchange_code("the-code")

    assert tokens["access_token"] == "at"
    assert tokens["refresh_token"] == "rt"
    assert captured["method"] == "POST"
    assert captured["url"] == "https://open.tiktokapis.com/v2/oauth/token/"
    body = dict(pair.split("=", 1) for pair in str(captured["body"]).split("&"))
    assert body["client_key"] == "ck"
    assert body["client_secret"] == "cs"
    assert body["code"] == "the-code"
    assert body["grant_type"] == "authorization_code"
    assert body["redirect_uri"] == "https%3A%2F%2Fexample.com%2Fcb"


async def test_refresh_uses_refresh_token_grant(monkeypatch: pytest.MonkeyPatch) -> None:
    captured_body: dict[str, str] = {}

    def handler(request: httpx.Request) -> httpx.Response:
        for pair in request.content.decode().split("&"):
            k, v = pair.split("=", 1)
            captured_body[k] = v
        return httpx.Response(200, json={"access_token": "new-at"})

    transport = httpx.MockTransport(handler)
    real_async_client = httpx.AsyncClient

    def patched(*args: object, **kwargs: object) -> httpx.AsyncClient:
        return real_async_client(*args, transport=transport, **kwargs)  # type: ignore[arg-type]

    monkeypatch.setattr("tiktok_autopost.auth.httpx.AsyncClient", patched)

    auth = TikTokAuth("ck", "cs", "https://example.com/cb")
    tokens = await auth.refresh("the-refresh-token")

    assert tokens == {"access_token": "new-at"}
    assert captured_body["grant_type"] == "refresh_token"
    assert captured_body["refresh_token"] == "the-refresh-token"
    assert captured_body["client_key"] == "ck"
    assert captured_body["client_secret"] == "cs"
