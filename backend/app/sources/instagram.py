"""Instagram posts, reels and carousels via instaloader.

Deliberate design note: this service never asks a visitor for Instagram
credentials, and no visitor password ever reaches this API.

Instagram has stopped serving anonymous metadata, so the operator of an instance
configures one login for the whole instance: either a session file created
offline (`instaloader --login=<user>`) or a username/password pair in the
environment, which is used once at startup and then cached as a session.
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
        "Instagram now refuses anonymous requests, so this instance needs an "
        "operator-configured login. Visitors are never asked for credentials."
    )

    def __init__(self) -> None:
        self._loader: instaloader.Instaloader | None = None
        self._authenticated = False

    def _get_loader(self) -> instaloader.Instaloader:
        """Build the loader once, logged in if the operator configured it.

        Two ways in, both operator-only and both resolved here at startup rather
        than per request:

        1. INSTAGRAM_SESSION_FILE — a session created offline, nothing secret in
           the environment. Preferred.
        2. INSTAGRAM_USERNAME + INSTAGRAM_PASSWORD — log in directly, and cache
           the resulting session to INSTAGRAM_SESSION_FILE if that path is set,
           so a restart does not trigger a fresh login.
        """
        if self._loader is not None:
            return self._loader

        loader = instaloader.Instaloader(
            quiet=True,
            download_comments=False,
            save_metadata=False,
            compress_json=False,
        )
        username = settings.instagram_username
        session_file = settings.instagram_session_file

        if username and session_file and Path(session_file).exists():
            try:
                loader.load_session_from_file(username, session_file)
                logger.info("Loaded Instagram session for %s", username)
                self._authenticated = True
            except Exception as exc:  # noqa: BLE001
                logger.warning("Could not load the Instagram session file: %s", exc)

        if not self._authenticated and username and settings.instagram_password:
            try:
                loader.login(username, settings.instagram_password)
                logger.info("Logged in to Instagram as %s", username)
                self._authenticated = True
                if session_file:
                    # Cache it so a restart reuses the session instead of
                    # logging in again, which is what gets accounts flagged.
                    try:
                        Path(session_file).parent.mkdir(parents=True, exist_ok=True)
                        loader.save_session_to_file(session_file)
                    except Exception as exc:  # noqa: BLE001
                        logger.warning("Could not cache the Instagram session: %s", exc)
            except Exception as exc:  # noqa: BLE001
                logger.warning("Instagram login failed, continuing anonymously: %s", exc)

        if not self._authenticated:
            logger.info("Instagram is running anonymously; most requests will be refused")

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

    def is_configured(self) -> bool:
        """Whether this instance has an Instagram login to work with."""
        if not settings.instagram_username:
            return False
        return bool(settings.instagram_password) or bool(
            settings.instagram_session_file and Path(settings.instagram_session_file).exists()
        )

    def setup_hint(self) -> str | None:
        if self.is_configured():
            return None
        return (
            "This instance has no Instagram login configured, so Instagram links "
            "will fail. The operator sets INSTAGRAM_USERNAME with either "
            "INSTAGRAM_PASSWORD or INSTAGRAM_SESSION_FILE."
        )

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
