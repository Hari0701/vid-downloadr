"""Pinterest pins. Images come from Open Graph tags; video pins fall back to yt-dlp."""
from __future__ import annotations

import json
import re
from pathlib import Path

from bs4 import BeautifulSoup

from ..schemas import DownloadOptions, MediaInfo
from .base import DownloadContext, DownloadError, Source
from .http import fetch_page, sanitize_filename, stream_to_file

# Pinterest serves resized derivatives under /236x/, /474x/ … the originals live
# under /originals/.
SIZE_SEGMENT = re.compile(r"/\d+x\d*/")


class PinterestSource(Source):
    name = "pinterest"
    label = "Pinterest"
    domains = ("pinterest.com", "pin.it", "pinterest.co.uk", "pinterest.ca", "pinterest.fr")
    supports_info = True
    priority = 20
    note = "Single pins. Board downloads are not supported."

    def _scrape(self, url: str) -> tuple[str | None, str | None, str | None]:
        """Return (media_url, title, is_video_flag_as_content_type)."""
        try:
            html = fetch_page(url)
        except Exception as exc:  # noqa: BLE001
            raise DownloadError("Could not open that pin.") from exc

        soup = BeautifulSoup(html, "html.parser")

        def meta(*names: str) -> str | None:
            for name in names:
                tag = soup.find("meta", attrs={"property": name}) or soup.find(
                    "meta", attrs={"name": name}
                )
                if tag and tag.get("content"):
                    return tag["content"]
            return None

        title = meta("og:title", "twitter:title")
        video = meta("og:video", "og:video:url", "og:video:secure_url")
        if video:
            return video, title, "video"

        image = meta("og:image", "og:image:url", "twitter:image")
        if not image:
            image = self._from_json_ld(soup)
        if not image:
            raise DownloadError("Could not find any media on that pin.")
        return SIZE_SEGMENT.sub("/originals/", image), title, "image"

    @staticmethod
    def _from_json_ld(soup: BeautifulSoup) -> str | None:
        for tag in soup.find_all("script", attrs={"type": "application/ld+json"}):
            try:
                data = json.loads(tag.string or "{}")
            except json.JSONDecodeError:
                continue
            candidates = data if isinstance(data, list) else [data]
            for entry in candidates:
                image = entry.get("image") if isinstance(entry, dict) else None
                if isinstance(image, str):
                    return image
                if isinstance(image, list) and image:
                    return image[0]
        return None

    def fetch_info(self, url: str) -> MediaInfo | None:
        media_url, title, kind = self._scrape(url)
        return MediaInfo(
            url=url,
            source=self.name,
            title=(title or "Pinterest pin")[:120],
            thumbnail=media_url if kind == "image" else None,
            extra={"kind": kind},
        )

    def download(self, url: str, options: DownloadOptions, ctx: DownloadContext) -> list[Path]:
        media_url, title, kind = self._scrape(url)
        ext = ".mp4" if kind == "video" else Path(media_url.split("?")[0]).suffix or ".jpg"
        stem = sanitize_filename(title or "pinterest_pin")
        return [stream_to_file(media_url, ctx.work_dir / f"{stem}{ext}", ctx)]
