"""Thin async wrapper around ``yt-dlp``."""

from __future__ import annotations

import asyncio
import logging
import shutil
import tempfile
from dataclasses import dataclass
from enum import Enum
from pathlib import Path
from typing import Any

import yt_dlp
import yt_dlp.utils

logger = logging.getLogger(__name__)


class MediaKind(str, Enum):
    VIDEO = "video"
    AUDIO = "audio"


@dataclass(frozen=True)
class MediaInfo:
    title: str
    uploader: str | None
    duration: int | None
    webpage_url: str
    thumbnail: str | None
    extractor: str
    is_live: bool


@dataclass
class DownloadResult:
    path: Path
    workdir: Path
    kind: MediaKind
    title: str
    duration: int | None
    info: MediaInfo

    def cleanup(self) -> None:
        try:
            shutil.rmtree(self.workdir, ignore_errors=True)
        except OSError:
            logger.warning("failed to clean workdir %s", self.workdir, exc_info=True)


class DownloadError(Exception):
    """Generic download failure."""


class UnsupportedURLError(DownloadError):
    """URL is not supported by yt-dlp."""


class LiveStreamError(DownloadError):
    """Cannot download a live stream."""


class FileTooLargeError(DownloadError):
    def __init__(self, size_bytes: int, limit_bytes: int) -> None:
        self.size_bytes = size_bytes
        self.limit_bytes = limit_bytes
        super().__init__(
            f"File is {size_bytes / 1024 / 1024:.1f} MiB which exceeds the "
            f"{limit_bytes / 1024 / 1024:.1f} MiB limit"
        )

    @property
    def size_mb(self) -> float:
        return self.size_bytes / 1024 / 1024

    @property
    def limit_mb(self) -> float:
        return self.limit_bytes / 1024 / 1024


def _video_format(max_height: int) -> str:
    return (
        f"bestvideo[height<={max_height}][ext=mp4]+bestaudio[ext=m4a]/"
        f"best[height<={max_height}][ext=mp4]/"
        f"best[height<={max_height}]/best"
    )


def build_ydl_options(
    *,
    output_template: str,
    kind: MediaKind,
    max_height: int = 720,
    max_filesize_bytes: int | None = None,
    cookiefile: str | None = None,
) -> dict[str, Any]:
    """Build the ``yt-dlp`` options dict for a download.

    Kept pure so it can be unit-tested without actually invoking yt-dlp.
    """

    opts: dict[str, Any] = {
        "outtmpl": output_template,
        "noplaylist": True,
        "quiet": True,
        "no_warnings": True,
        "restrictfilenames": True,
        "logtostderr": False,
        "retries": 3,
        "fragment_retries": 3,
        "concurrent_fragment_downloads": 4,
        "logger": _SilentLogger(),
    }
    if cookiefile:
        opts["cookiefile"] = cookiefile
    if max_filesize_bytes is not None and max_filesize_bytes > 0:
        opts["max_filesize"] = max_filesize_bytes

    if kind is MediaKind.VIDEO:
        opts["format"] = _video_format(max_height)
        opts["merge_output_format"] = "mp4"
        opts["postprocessors"] = [
            {
                "key": "FFmpegVideoRemuxer",
                "preferedformat": "mp4",
            }
        ]
    elif kind is MediaKind.AUDIO:
        opts["format"] = "bestaudio/best"
        opts["postprocessors"] = [
            {
                "key": "FFmpegExtractAudio",
                "preferredcodec": "mp3",
                "preferredquality": "192",
            }
        ]
    else:
        raise ValueError(f"Unknown MediaKind: {kind!r}")
    return opts


class _SilentLogger:
    def debug(self, msg: str) -> None:
        pass

    def info(self, msg: str) -> None:
        pass

    def warning(self, msg: str) -> None:
        logger.debug("yt-dlp warning: %s", msg)

    def error(self, msg: str) -> None:
        logger.debug("yt-dlp error: %s", msg)


def _normalize_info(payload: dict[str, Any] | None, fallback_url: str) -> dict[str, Any]:
    if payload is None:
        raise UnsupportedURLError("yt-dlp returned no metadata")
    if payload.get("_type") == "playlist":
        entries = [e for e in (payload.get("entries") or []) if e]
        if not entries:
            raise UnsupportedURLError("Playlist is empty")
        payload = entries[0]
    payload.setdefault("webpage_url", fallback_url)
    return payload


def _to_media_info(payload: dict[str, Any]) -> MediaInfo:
    return MediaInfo(
        title=str(payload.get("title") or "Untitled"),
        uploader=payload.get("uploader") or payload.get("channel"),
        duration=int(payload["duration"]) if payload.get("duration") else None,
        webpage_url=str(payload.get("webpage_url") or ""),
        thumbnail=payload.get("thumbnail"),
        extractor=str(payload.get("extractor_key") or payload.get("extractor") or "unknown"),
        is_live=bool(payload.get("is_live")),
    )


def _classify_download_error(err: Exception) -> DownloadError:
    msg = str(err)
    lowered = msg.lower()
    if "unsupported url" in lowered or "no video formats found" in lowered:
        return UnsupportedURLError(msg)
    if "is live" in lowered or "live event" in lowered:
        return LiveStreamError(msg)
    return DownloadError(msg)


def _fetch_info_sync(url: str) -> MediaInfo:
    opts = {
        "quiet": True,
        "no_warnings": True,
        "noplaylist": True,
        "skip_download": True,
        "logger": _SilentLogger(),
    }
    try:
        with yt_dlp.YoutubeDL(opts) as ydl:
            payload = ydl.extract_info(url, download=False)
    except yt_dlp.utils.UnsupportedError as e:
        raise UnsupportedURLError(str(e)) from e
    except yt_dlp.utils.DownloadError as e:
        raise _classify_download_error(e) from e
    payload = _normalize_info(payload, url)
    return _to_media_info(payload)


async def fetch_info(url: str) -> MediaInfo:
    """Fetch metadata for *url* without downloading the media."""

    return await asyncio.to_thread(_fetch_info_sync, url)


def _resolve_output_path(payload: dict[str, Any], workdir: Path) -> Path:
    requested = payload.get("requested_downloads") or []
    for entry in requested:
        candidate = entry.get("filepath") or entry.get("_filename")
        if candidate:
            path = Path(candidate)
            if path.exists():
                return path
    candidate = payload.get("filepath") or payload.get("_filename")
    if candidate:
        path = Path(candidate)
        if path.exists():
            return path
    files = sorted(
        (p for p in workdir.iterdir() if p.is_file()),
        key=lambda p: p.stat().st_mtime,
        reverse=True,
    )
    if files:
        return files[0]
    raise DownloadError("yt-dlp finished but produced no output file")


def _download_sync(
    *,
    url: str,
    kind: MediaKind,
    max_filesize_bytes: int,
    max_height: int,
    cookiefile: str | None,
) -> DownloadResult:
    info = _fetch_info_sync(url)
    if info.is_live:
        raise LiveStreamError("Live streams are not supported")

    workdir = Path(tempfile.mkdtemp(prefix="ytbot-"))
    output_template = str(workdir / "%(id)s.%(ext)s")
    opts = build_ydl_options(
        output_template=output_template,
        kind=kind,
        max_height=max_height,
        max_filesize_bytes=max_filesize_bytes,
        cookiefile=cookiefile,
    )
    try:
        with yt_dlp.YoutubeDL(opts) as ydl:
            payload = ydl.extract_info(url, download=True)
    except yt_dlp.utils.DownloadError as e:
        shutil.rmtree(workdir, ignore_errors=True)
        raise _classify_download_error(e) from e
    except Exception:
        shutil.rmtree(workdir, ignore_errors=True)
        raise

    payload = _normalize_info(payload, url)
    try:
        path = _resolve_output_path(payload, workdir)
    except DownloadError:
        shutil.rmtree(workdir, ignore_errors=True)
        raise

    size = path.stat().st_size
    if size > max_filesize_bytes:
        shutil.rmtree(workdir, ignore_errors=True)
        raise FileTooLargeError(size, max_filesize_bytes)

    return DownloadResult(
        path=path,
        workdir=workdir,
        kind=kind,
        title=info.title,
        duration=info.duration,
        info=info,
    )


async def download(
    url: str,
    *,
    kind: MediaKind,
    max_filesize_bytes: int,
    max_height: int = 720,
    cookiefile: str | None = None,
) -> DownloadResult:
    """Download *url* as either a video or an audio file."""

    return await asyncio.to_thread(
        _download_sync,
        url=url,
        kind=kind,
        max_filesize_bytes=max_filesize_bytes,
        max_height=max_height,
        cookiefile=cookiefile,
    )


def format_duration(seconds: int | None) -> str:
    """Render *seconds* as a human-readable duration."""

    if seconds is None or seconds < 0:
        return "—"
    seconds = int(seconds)
    hours, rem = divmod(seconds, 3600)
    minutes, secs = divmod(rem, 60)
    if hours:
        return f"{hours}:{minutes:02d}:{secs:02d}"
    return f"{minutes}:{secs:02d}"


__all__ = [
    "DownloadError",
    "DownloadResult",
    "FileTooLargeError",
    "LiveStreamError",
    "MediaInfo",
    "MediaKind",
    "UnsupportedURLError",
    "build_ydl_options",
    "download",
    "fetch_info",
    "format_duration",
]
