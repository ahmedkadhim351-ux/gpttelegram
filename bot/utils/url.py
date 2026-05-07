"""URL extraction helpers."""

from __future__ import annotations

import re
from urllib.parse import urlparse

_URL_RE = re.compile(r"https?://[^\s<>]+", re.IGNORECASE)
_TRAILING_PUNCT = ").,!?;:\"'"


def extract_first_url(text: str | None) -> str | None:
    """Return the first http(s) URL in *text*, or None."""

    if not text:
        return None
    match = _URL_RE.search(text)
    if not match:
        return None
    url = match.group(0)
    while url and url[-1] in _TRAILING_PUNCT:
        url = url[:-1]
    if not _is_http_url(url):
        return None
    return url


def _is_http_url(url: str) -> bool:
    try:
        parsed = urlparse(url)
    except ValueError:
        return False
    return parsed.scheme in {"http", "https"} and bool(parsed.netloc)
