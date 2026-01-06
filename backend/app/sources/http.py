"""Streaming file fetch shared by the scraper-style sources."""
from __future__ import annotations

import os
import re
import time
from pathlib import Path

import requests

from ..config import settings
from .base import DownloadContext, DownloadError

USER_AGENT = (
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/124.0 Safari/537.36"
)

_INVALID = re.compile(r'[<>:"/\\|?*\x00-\x1f]')


def sanitize_filename(name: str, max_length: int = 200) -> str:
    name = _INVALID.sub("", name).strip().strip(".")
    if not name:
        name = "download"
    stem, ext = os.path.splitext(name)
    if len(name) > max_length:
        stem = stem[: max_length - len(ext)]
    return stem + ext


def proxies() -> dict[str, str] | None:
    return {"http": settings.proxy, "https": settings.proxy} if settings.proxy else None


def fetch_page(url: str, timeout: int = 15) -> str:
    headers = {
        "User-Agent": USER_AGENT,
        "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
        "Accept-Language": "en-US,en;q=0.9",
    }
    response = requests.get(url, headers=headers, timeout=timeout, proxies=proxies())
    response.raise_for_status()
    return response.text


def stream_to_file(url: str, destination: Path, ctx: DownloadContext) -> Path:
    """Download `url` to `destination`, reporting progress and honouring cancel."""
    limit = settings.max_filesize_mb * 1024 * 1024
    headers = {"User-Agent": USER_AGENT}
    try:
        response = requests.get(
            url, stream=True, headers=headers, timeout=30, proxies=proxies()
        )
        response.raise_for_status()
    except requests.RequestException as exc:
        raise DownloadError(f"Could not reach the media file: {exc}") from exc

    total = int(response.headers.get("content-length") or 0) or None
    if total and total > limit:
        raise DownloadError(f"That file is larger than the {settings.max_filesize_mb} MB limit.")

    downloaded = 0
    started = time.monotonic()
    destination.parent.mkdir(parents=True, exist_ok=True)
    try:
        with destination.open("wb") as handle:
            for chunk in response.iter_content(64 * 1024):
                ctx.check_cancelled()
                if not chunk:
                    continue
                downloaded += len(chunk)
                if downloaded > limit:
                    raise DownloadError(
                        f"That file is larger than the {settings.max_filesize_mb} MB limit."
                    )
                handle.write(chunk)
                elapsed = max(time.monotonic() - started, 0.001)
                ctx.report(
                    percent=(downloaded / total * 100) if total else 0.0,
                    speed=downloaded / elapsed,
                    downloaded=downloaded,
                    total=total,
                    stage="downloading",
                )
    except Exception:
        destination.unlink(missing_ok=True)
        raise

    ctx.report(percent=100.0, speed=0.0, downloaded=downloaded, total=total, stage="processing")
    return destination
