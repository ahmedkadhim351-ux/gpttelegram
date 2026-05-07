# tiktok_autopost

Async Python helper for the **official** [TikTok Content Posting
API](https://developers.tiktok.com/doc/content-posting-api-get-started).

Use this to publish promo videos for your Telegram bot from your own
TikTok creator account. The package wraps three things:

* OAuth 2.0 login (authorization code flow + token refresh).
* `init -> upload -> status` "direct post" (publish immediately).
* `init -> upload -> status` "inbox upload" (save as draft, finish
  in the TikTok app).

> **Not** included: posting comments under other people's videos,
> follow/unfollow loops, or any unofficial scraping. That violates
> TikTok's Terms of Service and will get the account banned.

---

## 1. Register a TikTok app

1. Go to <https://developers.tiktok.com> and sign in with your TikTok
   account.
2. **Manage apps** → **Connect an app**. Fill out the basic info.
3. Open the app and add the **Login Kit** product. Add your redirect
   URI (e.g. `https://example.com/oauth/tiktok/callback`). For local
   testing you can use `http://localhost:8080/callback`.
4. Add the **Content Posting API** product. Request the
   `video.publish` scope (direct post) and/or `video.upload` scope
   (inbox upload). For brand-new apps TikTok approves the
   "Sandbox" mode automatically — that is enough to post on the
   handful of accounts you add as **test users**.
5. Once you graduate the app to production, your sandbox limits go
   away and you can post on any account that authorizes your app.
6. Copy the **Client Key** and **Client Secret** into your `.env`:

   ```dotenv
   TIKTOK_CLIENT_KEY=...
   TIKTOK_CLIENT_SECRET=...
   TIKTOK_REDIRECT_URI=https://example.com/oauth/tiktok/callback
   ```

## 2. Authorize once

The first time, you authorize your TikTok account so the API can
post on its behalf:

```bash
# Step A — generate the URL the creator should open in a browser.
python -m tiktok_autopost auth-url
# https://www.tiktok.com/v2/auth/authorize/?client_key=...&scope=user.info.basic,video.publish&...
# # state=k4hG... (printed to stderr — keep it for CSRF check)
```

Open that URL, log in with the TikTok account that should publish
videos, click **Allow**. TikTok will redirect to your
`TIKTOK_REDIRECT_URI` with `?code=<CODE>&state=<STATE>` in the
query string. Check that the `state` matches.

```bash
# Step B — exchange the code for tokens.
python -m tiktok_autopost exchange-code <CODE>
# {
#   "access_token": "act.example...",
#   "refresh_token": "rt.example...",
#   "expires_in": 86400,
#   "open_id": "...",
#   "scope": "user.info.basic,video.publish",
#   "token_type": "Bearer"
# }
```

Save both tokens into `.env`:

```dotenv
TIKTOK_ACCESS_TOKEN=act.example...
TIKTOK_REFRESH_TOKEN=rt.example...
```

When the access token expires (usually 24h):

```bash
python -m tiktok_autopost refresh
```

## 3. Post a video

```bash
python -m tiktok_autopost post path/to/video.mp4 \
  --title "GPT-4o в Telegram, бот в шапке профиля → @your_bot" \
  --privacy SELF_ONLY
```

While you are testing, leave `--privacy SELF_ONLY` so the video
only appears for your account. Once you're happy, switch to
`PUBLIC_TO_EVERYONE`.

The CLI will:

1. Call the **init** endpoint and receive a `publish_id` and an
   `upload_url`.
2. `PUT` the video bytes to `upload_url` (single chunk for files
   <= 64 MiB, otherwise chunked).
3. Poll the **status** endpoint until the publish completes (or
   fails).

Use `--no-wait` if you want to fire-and-forget; the status check
can be done later with `fetch_status(publish_id)` from Python.

## 4. Library usage

```python
import asyncio
from pathlib import Path

from tiktok_autopost import TikTokClient


async def main() -> None:
    async with TikTokClient(access_token="act.example...") as client:
        # See available privacy options for this account.
        creator = await client.query_creator_info()
        print(creator["privacy_level_options"])

        result = await client.post_video(
            Path("video.mp4"),
            title="GPT-4o в Telegram → @your_bot",
            privacy_level="PUBLIC_TO_EVERYONE",
        )
        print(result)


asyncio.run(main())
```

## File-format limits (from TikTok docs)

| Limit             | Value                                |
|-------------------|--------------------------------------|
| Container         | `.mp4`, `.mov`, `.webm`              |
| Codec             | H.264 / H.265                        |
| Resolution        | up to 4096 × 2160                    |
| Length            | up to 10 minutes                     |
| File size         | up to 4 GB                           |
| Aspect ratio      | any (vertical 9:16 recommended)      |
| Single-chunk size | <= 64 MiB                            |
| Chunk range       | 5 MiB – 64 MiB (multi-chunk)         |

## Rate limits & approval

* **Sandbox apps** can post on up to 4 test accounts only. The same
  rate limits as production apply (≈ 6 posts / minute / token).
* **Production apps** require an audit by TikTok — the form is in
  the developer console next to each product.
* Wait at least a few seconds between posts; rapid-fire publishing
  is the fastest way to get the access token revoked.

## What this package will *not* do

* Post comments under other users' videos.
* Like / follow / DM other accounts.
* Scrape video URLs, captions, or analytics outside of the official
  API.

If you need any of that, the answer is **no** — those actions
violate TikTok's [Community Guidelines](https://www.tiktok.com/community-guidelines)
and [Terms of Service](https://www.tiktok.com/legal/terms-of-service)
and the platform's anti-abuse systems will detect and ban the
account.
