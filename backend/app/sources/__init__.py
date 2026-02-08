"""Source registry.

To add a site: write a Source subclass in this package and add it to SOURCES.
Ordering does not matter — resolution sorts by `priority`, so the generic
yt-dlp catch-all always runs last.
"""
from __future__ import annotations

from .base import DownloadContext, DownloadError, Source
from .instagram import InstagramSource
from .pinterest import PinterestSource
from .twitter import TwitterSource
from .ytdlp_source import GenericSource, YouTubeSource

SOURCES: list[Source] = [
    YouTubeSource(),
    InstagramSource(),
    TwitterSource(),
    PinterestSource(),
    GenericSource(),
]


def all_sources() -> list[Source]:
    return sorted(SOURCES, key=lambda s: s.priority)


def resolve(url: str) -> Source | None:
    """First source (by priority) that claims the URL."""
    for source in all_sources():
        try:
            if source.matches(url):
                return source
        except Exception:  # noqa: BLE001 - a broken matcher must not break resolution
            continue
    return None


__all__ = [
    "DownloadContext",
    "DownloadError",
    "Source",
    "SOURCES",
    "all_sources",
    "resolve",
]
