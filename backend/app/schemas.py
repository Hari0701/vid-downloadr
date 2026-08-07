"""Wire format shared with the frontend."""
from __future__ import annotations

from datetime import datetime
from enum import Enum
from typing import Any, Literal

from pydantic import BaseModel, Field, field_validator


class JobStatus(str, Enum):
    queued = "queued"
    running = "running"
    completed = "completed"
    failed = "failed"
    cancelled = "cancelled"
    expired = "expired"


class DownloadOptions(BaseModel):
    """Per-request knobs. Sources ignore what does not apply to them."""

    quality: Literal["360p", "480p", "720p", "1080p", "1440p", "2160p", "best"] = "720p"
    audio_only: bool = False
    audio_format: Literal["mp3", "m4a", "opus", "wav"] = "mp3"
    playlist: bool = False
    # Trim the result: seconds from the start / total seconds to keep.
    start_time: float | None = Field(default=None, ge=0)
    duration: float | None = Field(default=None, gt=0)


class DownloadRequest(BaseModel):
    url: str
    options: DownloadOptions = Field(default_factory=DownloadOptions)

    @field_validator("url")
    @classmethod
    def _must_be_http(cls, value: str) -> str:
        value = value.strip()
        if not value.startswith(("http://", "https://")):
            raise ValueError("URL must start with http:// or https://")
        if len(value) > 2048:
            raise ValueError("URL is too long")
        return value


class MediaFile(BaseModel):
    """One downloadable artifact produced by a job."""

    id: str
    filename: str
    size_bytes: int
    content_type: str
    download_url: str


class JobProgress(BaseModel):
    percent: float = 0.0
    speed_bytes_per_sec: float = 0.0
    eta_seconds: float | None = None
    downloaded_bytes: int = 0
    total_bytes: int | None = None
    stage: str = "queued"


class Job(BaseModel):
    id: str
    url: str
    source: str
    status: JobStatus
    title: str | None = None
    thumbnail: str | None = None
    progress: JobProgress = Field(default_factory=JobProgress)
    files: list[MediaFile] = Field(default_factory=list)
    error: str | None = None
    created_at: datetime
    completed_at: datetime | None = None
    expires_at: datetime | None = None


class MediaInfo(BaseModel):
    """Metadata preview shown before the user commits to a download."""

    url: str
    source: str
    title: str | None = None
    uploader: str | None = None
    thumbnail: str | None = None
    duration_seconds: float | None = None
    is_playlist: bool = False
    entry_count: int | None = None
    available_qualities: list[str] = Field(default_factory=list)
    extra: dict[str, Any] = Field(default_factory=dict)


class SourceDescriptor(BaseModel):
    """Advertised capabilities, so the UI can enable the right controls."""

    name: str
    label: str
    domains: list[str]
    supports_quality: bool = False
    supports_audio_only: bool = False
    supports_playlist: bool = False
    supports_info: bool = False
    requires_operator_credentials: bool = False
    note: str | None = None
    # False when the instance is missing something the source needs (a login,
    # a cookie file). The UI surfaces setup_hint instead of letting a user try.
    configured: bool = True
    setup_hint: str | None = None
