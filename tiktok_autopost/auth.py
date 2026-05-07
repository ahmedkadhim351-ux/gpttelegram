"""OAuth 2.0 helpers for the TikTok Login Kit.

The flow is the standard "authorization code" flow:

1. Direct the user to :meth:`TikTokAuth.build_auth_url` and have them log in.
2. TikTok redirects the user back to your ``redirect_uri`` with ``?code=...``.
3. Call :meth:`TikTokAuth.exchange_code` with that code to get access and
   refresh tokens.
4. Later, call :meth:`TikTokAuth.refresh` to get a new access token without
   bothering the user again (refresh tokens are valid for ~365 days).

See https://developers.tiktok.com/doc/login-kit-web for the canonical docs.
"""

from __future__ import annotations

import secrets
from typing import Any
from urllib.parse import urlencode

import httpx

DEFAULT_SCOPES: tuple[str, ...] = ("user.info.basic", "video.publish")


class TikTokAuth:
    """Thin wrapper over the TikTok OAuth 2.0 token endpoint."""

    def __init__(
        self,
        client_key: str,
        client_secret: str,
        redirect_uri: str,
        *,
        api_base: str = "https://open.tiktokapis.com",
        auth_base: str = "https://www.tiktok.com",
        timeout: float = 30.0,
    ) -> None:
        self.client_key = client_key
        self.client_secret = client_secret
        self.redirect_uri = redirect_uri
        self.api_base = api_base.rstrip("/")
        self.auth_base = auth_base.rstrip("/")
        self.timeout = timeout

    def build_auth_url(
        self,
        *,
        scopes: tuple[str, ...] | list[str] | None = None,
        state: str | None = None,
    ) -> tuple[str, str]:
        """Return ``(auth_url, state)``.

        The caller should persist ``state`` and verify it matches when the
        redirect comes back, to defend against CSRF.
        """
        scopes = tuple(scopes) if scopes else DEFAULT_SCOPES
        state = state or secrets.token_urlsafe(24)
        params = {
            "client_key": self.client_key,
            "scope": ",".join(scopes),
            "response_type": "code",
            "redirect_uri": self.redirect_uri,
            "state": state,
        }
        return f"{self.auth_base}/v2/auth/authorize/?{urlencode(params)}", state

    async def exchange_code(self, code: str) -> dict[str, Any]:
        """Exchange an authorization code for ``{access_token, refresh_token, ...}``."""
        return await self._token_request(
            {
                "client_key": self.client_key,
                "client_secret": self.client_secret,
                "code": code,
                "grant_type": "authorization_code",
                "redirect_uri": self.redirect_uri,
            }
        )

    async def refresh(self, refresh_token: str) -> dict[str, Any]:
        """Trade a refresh token for a fresh access token."""
        return await self._token_request(
            {
                "client_key": self.client_key,
                "client_secret": self.client_secret,
                "grant_type": "refresh_token",
                "refresh_token": refresh_token,
            }
        )

    async def _token_request(self, data: dict[str, str]) -> dict[str, Any]:
        async with httpx.AsyncClient(timeout=self.timeout) as client:
            response = await client.post(
                f"{self.api_base}/v2/oauth/token/",
                data=data,
                headers={"Cache-Control": "no-cache"},
            )
        response.raise_for_status()
        return response.json()
