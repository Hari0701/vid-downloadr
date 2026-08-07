"""Instagram posts, reels and carousels via instaloader.

Deliberate design note: this service never asks a visitor for Instagram
credentials. It runs anonymously by default, but Instagram has largely stopped serving
anonymous metadata, so in practice an operator session is required.
An operator may optionally point INSTAGRAM_SESSION_FILE at a session created
offline on their own machine (`instaloader --login=<user>`), which is used for
every request. There is no per-user login and no password ever reaches this API.
"""
from __future__ import annotations

import logging
from pathlib import Path
from urllib.parse import urlparse

import instaloader

from ..config import settings
from ..schemas import DownloadOptions, MediaInfo
from .base import DownloadContext, DownloadError, Source
from .http import sanitize_filename, stream_to_file

logger = logging.getLogger(__name__)


class InstagramSource(Source):
    name = "instagram"
    label = "Instagram"
    domains = ("instagram.com",)
    supports_info = True
    # Advertised to the frontend so the UI can warn before someone pastes a link.
    requires_operator_credentials = True
    priority = 20
    note = (
        "Instagram now refuses anonymous requests, so this source needs an "
        "operator-configured session. Visitors are never asked to log in."
    )

    def __init__(self) -> None:
        self._loader: instaloader.Instaloader | None = None

    def _get_loader(self) -> instaloader.Instaloader:
        if self._loader is not None:
            return self._loader
        loader = instaloader.Instaloader(
            quiet=True,
            download_comments=False,
            save_metadata=False,
            compress_json=False,
        )
        if settings.instagram_session_file and settings.instagram_username:
            try:
                loader.load_session_from_file(
                    settings.instagram_username, settings.instagram_session_file
                )
                logger.info("Loaded Instagram session for %s", settings.instagram_username)
            except Exception as exc:  # noqa: BLE001
                logger.warning("Could not load Instagram session, staying anonymous: %s", exc)
        self._loader = loader
        return loader

    @staticmethod
    def _shortcode(url: str) -> str | None:
        parts = [p for p in urlparse(url).path.split("/") if p]
        for marker in ("p", "reel", "reels", "tv"):
            if marker in parts:
                index = parts.index(marker)
                if index + 1 < len(parts):
                    return parts[index + 1]
        return None

    def _post(self, url: str) -> instaloader.Post:
        shortcode = self._shortcode(url)
        if not shortcode:
            raise DownloadError("That does not look like an Instagram post, reel or TV link.")
        try:
            return instaloader.Post.from_shortcode(self._get_loader().context, shortcode)
        except Exception as exc:  # noqa: BLE001
            raise DownloadError(_friendly(exc)) from exc

    def fetch_info(self, url: str) -> MediaInfo | None:
        post = self._post(url)
        is_carousel = post.typename == "GraphSidecar"
        return MediaInfo(
            url=url,
            source=self.name,
            title=(post.caption or "").strip().split("\n")[0][:120] or f"Instagram {post.shortcode}",
            uploader=post.owner_username,
            thumbnail=post.url,
            duration_seconds=getattr(post, "video_duration", None),
            is_playlist=is_carousel,
            entry_count=post.mediacount if is_carousel else 1,
            extra={"typename": post.typename, "caption": post.caption or ""},
        )

    def download(self, url: str, options: DownloadOptions, ctx: DownloadContext) -> list[Path]:
        post = self._post(url)
        stem = sanitize_filename(f"{post.owner_username}_{post.shortcode}")

        if post.typename == "GraphSidecar":
            nodes = list(post.get_sidecar_nodes())
            files: list[Path] = []
            for index, node in enumerate(nodes, start=1):
                ctx.check_cancelled()
                media_url = node.video_url if node.is_video else node.display_url
                ext = ".mp4" if node.is_video else ".jpg"
                files.append(
                    stream_to_file(media_url, ctx.work_dir / f"{stem}_{index}{ext}", ctx)
                )
                ctx.report(percent=index / len(nodes) * 100, speed=0.0, stage="downloading")
            return files

        media_url = post.video_url if post.is_video else post.url
        ext = ".mp4" if post.is_video else ".jpg"
        return [stream_to_file(media_url, ctx.work_dir / f"{stem}{ext}", ctx)]


def _friendly(exc: Exception) -> str:
    lowered = str(exc).lower()
    if "not exist" in lowered or "404" in lowered:
        return "That post does not exist."
    if "401" in lowered or "403" in lowered or "rate" in lowered or "429" in lowered:
        return "Instagram rate-limited this server. Try again in a few minutes."
    if "login" in lowered or "private" in lowered or "not accessible" in lowered:
        return "That post is private or requires a logged-in account."
    # Instagram now refuses anonymous metadata fetches almost everywhere, which
    # instaloader surfaces as a generic bad response. Say what actually has to
    # happen instead of blaming the link.
    if "fetching" in lowered and "failed" in lowered:
        return (
            "Instagram refused an anonymous request. This instance needs an "
            "operator-configured Instagram session to fetch posts."
        )
    return "Instagram refused the request."
