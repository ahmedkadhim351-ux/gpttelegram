"""Command-line interface for ``tiktok_autopost``.

Run ``python -m tiktok_autopost --help`` to see the available commands.

Typical usage::

    # 1. Print the URL the creator must open in a browser to authorize the app.
    python -m tiktok_autopost auth-url

    # 2. After being redirected to your ``TIKTOK_REDIRECT_URI`` with ?code=...,
    #    exchange that code for an access + refresh token pair.
    python -m tiktok_autopost exchange-code <CODE>

    # 3. Refresh later when the access token expires.
    python -m tiktok_autopost refresh --refresh-token <RT>

    # 4. Publish a video.
    python -m tiktok_autopost post path/to/video.mp4 \\
        --title "Tip: this Telegram bot answers any question" \\
        --privacy SELF_ONLY
"""

from __future__ import annotations

import argparse
import asyncio
import json
import sys
from pathlib import Path

from .auth import TikTokAuth
from .client import TikTokClient
from .config import TikTokSettings


def _load_settings() -> TikTokSettings:
    try:
        return TikTokSettings()  # type: ignore[call-arg]
    except Exception as exc:  # noqa: BLE001 - surface configuration errors verbatim
        print(f"Failed to load TikTok settings (check your .env): {exc}", file=sys.stderr)
        sys.exit(2)


def _build_auth(settings: TikTokSettings) -> TikTokAuth:
    return TikTokAuth(
        client_key=settings.client_key,
        client_secret=settings.client_secret,
        redirect_uri=settings.redirect_uri,
        api_base=settings.api_base,
        auth_base=settings.auth_base,
    )


async def cmd_auth_url(args: argparse.Namespace) -> int:
    auth = _build_auth(_load_settings())
    url, state = auth.build_auth_url(scopes=args.scopes.split(","))
    print(url)
    print(f"# state={state}", file=sys.stderr)
    return 0


async def cmd_exchange_code(args: argparse.Namespace) -> int:
    auth = _build_auth(_load_settings())
    tokens = await auth.exchange_code(args.code)
    print(json.dumps(tokens, indent=2, ensure_ascii=False))
    return 0


async def cmd_refresh(args: argparse.Namespace) -> int:
    settings = _load_settings()
    refresh_token = args.refresh_token or settings.refresh_token
    if not refresh_token:
        print(
            "Provide --refresh-token or set TIKTOK_REFRESH_TOKEN in the environment.",
            file=sys.stderr,
        )
        return 2
    auth = _build_auth(settings)
    tokens = await auth.refresh(refresh_token)
    print(json.dumps(tokens, indent=2, ensure_ascii=False))
    return 0


async def cmd_post(args: argparse.Namespace) -> int:
    settings = _load_settings()
    access_token = args.access_token or settings.access_token
    if not access_token:
        print(
            "Provide --access-token or set TIKTOK_ACCESS_TOKEN in the environment.",
            file=sys.stderr,
        )
        return 2
    video_path = Path(args.video)
    if not video_path.is_file():  # noqa: ASYNC240 - local stat is non-blocking enough
        print(f"Video file not found: {video_path}", file=sys.stderr)
        return 2

    async with TikTokClient(access_token=access_token, api_base=settings.api_base) as client:
        result = await client.post_video(
            video_path,
            title=args.title,
            privacy_level=args.privacy,
            wait=not args.no_wait,
        )
    print(json.dumps(result, indent=2, ensure_ascii=False))
    return 0


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="tiktok-autopost", description=__doc__)
    sub = parser.add_subparsers(dest="cmd", required=True)

    p_url = sub.add_parser("auth-url", help="Print OAuth authorization URL")
    p_url.add_argument(
        "--scopes",
        default="user.info.basic,video.publish",
        help="Comma-separated OAuth scopes (default: user.info.basic,video.publish)",
    )
    p_url.set_defaults(func=cmd_auth_url)

    p_exch = sub.add_parser("exchange-code", help="Exchange authorization code for tokens")
    p_exch.add_argument("code", help="The ?code=... value from the OAuth redirect")
    p_exch.set_defaults(func=cmd_exchange_code)

    p_ref = sub.add_parser("refresh", help="Refresh an access token")
    p_ref.add_argument("--refresh-token", help="Refresh token (defaults to TIKTOK_REFRESH_TOKEN)")
    p_ref.set_defaults(func=cmd_refresh)

    p_post = sub.add_parser("post", help="Upload and publish a video")
    p_post.add_argument("video", help="Path to the .mp4 file to upload")
    p_post.add_argument("--title", required=True, help="Caption / video title")
    p_post.add_argument(
        "--privacy",
        default="SELF_ONLY",
        choices=[
            "PUBLIC_TO_EVERYONE",
            "MUTUAL_FOLLOW_FRIENDS",
            "FOLLOWER_OF_CREATOR",
            "SELF_ONLY",
        ],
        help="Privacy level (default: SELF_ONLY — safest while you test the flow)",
    )
    p_post.add_argument(
        "--access-token",
        help="Access token (defaults to TIKTOK_ACCESS_TOKEN env var)",
    )
    p_post.add_argument(
        "--no-wait",
        action="store_true",
        help="Return immediately after the upload finishes; don't poll status.",
    )
    p_post.set_defaults(func=cmd_post)

    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    return asyncio.run(args.func(args))


if __name__ == "__main__":
    sys.exit(main())
