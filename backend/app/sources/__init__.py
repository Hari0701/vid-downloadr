"""Source registry.

To add a site: write a Source subclass in this package and add it to SOURCES.
"""
from __future__ import annotations

from .base import DownloadContext, DownloadError, Source
from .instagram import InstagramSource
from .ytdlp_source import YouTubeSource

SOURCES: list[Source] = [
    YouTubeSource(),
    InstagramSource(),
]


def all_sources() -> list[Source]:
    return sorted(SOURCES, key=lambda s: s.priority)


def resolve(url: str) -> Source | None:
    """First source (by priority) that claims the URL."""
    for source in all_sources():
        if source.matches(url):
            return source
    return None


__all__ = ["DownloadContext", "DownloadError", "Source", "SOURCES", "all_sources", "resolve"]
