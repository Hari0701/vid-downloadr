"""The contract every source plugin implements.

Adding a site means writing one subclass and registering it. Nothing else in the
backend needs to change.
"""
from __future__ import annotations

import re
from abc import ABC, abstractmethod
from dataclasses import dataclass
from pathlib import Path
from typing import Callable
from urllib.parse import urlparse

from ..schemas import DownloadOptions, MediaInfo, SourceDescriptor


class DownloadError(Exception):
    """Raised by a source when a download cannot be completed.

    The message is shown to the user, so keep it human-readable and free of
    internal detail.
    """


@dataclass
class DownloadContext:
    """Everything a source needs to do its work and report back."""

    work_dir: Path
    # report(percent, speed_bytes_per_sec, downloaded, total, stage)
    report: Callable[..., None]
    # Raises if the job has been cancelled; call it between chunks.
    check_cancelled: Callable[[], None]


class Source(ABC):
    name: str = "source"
    label: str = "Source"
    domains: tuple[str, ...] = ()
    supports_quality: bool = False
    supports_audio_only: bool = False
    supports_playlist: bool = False
    supports_info: bool = False
    requires_operator_credentials: bool = False
    note: str | None = None
    # Lower runs first; the generic catch-all sits at the bottom.
    priority: int = 100

    def matches(self, url: str) -> bool:
        """Default: match on registered domain suffixes."""
        host = (urlparse(url).hostname or "").lower()
        host = re.sub(r"^www\.", "", host)
        return any(host == d or host.endswith("." + d) for d in self.domains)

    def fetch_info(self, url: str) -> MediaInfo | None:
        """Cheap metadata probe. Return None when the source cannot preview."""
        return None

    @abstractmethod
    def download(self, url: str, options: DownloadOptions, ctx: DownloadContext) -> list[Path]:
        """Download into ctx.work_dir and return the produced files."""

    def descriptor(self) -> SourceDescriptor:
        return SourceDescriptor(
            name=self.name,
            label=self.label,
            domains=list(self.domains),
            supports_quality=self.supports_quality,
            supports_audio_only=self.supports_audio_only,
            supports_playlist=self.supports_playlist,
            supports_info=self.supports_info,
            requires_operator_credentials=self.requires_operator_credentials,
            note=self.note,
        )
