"""Auto-posting helper for TikTok's Content Posting API.

This package wraps the official TikTok Content Posting API
(https://developers.tiktok.com/doc/content-posting-api-get-started)
so you can publish promotional videos for your Telegram bot from Python.

It does **not** scrape TikTok or post comments under other people's videos —
that would violate TikTok's Terms of Service. The supported flows are:

* OAuth 2.0 user authorization (login + token refresh).
* ``init -> upload -> status`` direct post (publish a video on the authorized
  account immediately).
* ``init -> upload -> status`` inbox upload (drop a draft into the user's
  TikTok inbox so they can finish posting in the app).
"""

from .auth import TikTokAuth
from .client import PrivacyLevel, TikTokAPIError, TikTokClient
from .config import TikTokSettings

__all__ = [
    "PrivacyLevel",
    "TikTokAPIError",
    "TikTokAuth",
    "TikTokClient",
    "TikTokSettings",
]
