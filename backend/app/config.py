"""Runtime configuration, all overridable by environment variable."""
from __future__ import annotations

import os
import tempfile
from dataclasses import dataclass, field
from pathlib import Path


def _env_int(name: str, default: int) -> int:
    try:
        return int(os.environ.get(name, default))
    except ValueError:
        return default


def _env_bool(name: str, default: bool) -> bool:
    raw = os.environ.get(name)
    if raw is None:
        return default
    return raw.strip().lower() in {"1", "true", "yes", "on"}


def _env_list(name: str, default: list[str]) -> list[str]:
    raw = os.environ.get(name)
    if not raw:
        return default
    return [item.strip() for item in raw.split(",") if item.strip()]


@dataclass(frozen=True)
class Settings:
    # Where finished files live until they expire.
    download_dir: Path = field(
        default_factory=lambda: Path(
            os.environ.get("DOWNLOAD_DIR", Path(tempfile.gettempdir()) / "vid-downloadr")
        )
    )
    # A finished file is deleted this many seconds after it completes.
    file_ttl_seconds: int = field(default_factory=lambda: _env_int("FILE_TTL_SECONDS", 3600))
    # How often the reaper sweeps expired jobs.
    cleanup_interval_seconds: int = field(
        default_factory=lambda: _env_int("CLEANUP_INTERVAL_SECONDS", 300)
    )
    # Downloads running at the same time across the whole process.
    max_concurrent_downloads: int = field(
        default_factory=lambda: _env_int("MAX_CONCURRENT_DOWNLOADS", 3)
    )
    # Hard ceiling per download; yt-dlp refuses anything larger.
    max_filesize_mb: int = field(default_factory=lambda: _env_int("MAX_FILESIZE_MB", 2048))
    # Requests allowed per client IP per window.
    rate_limit_requests: int = field(default_factory=lambda: _env_int("RATE_LIMIT_REQUESTS", 20))
    rate_limit_window_seconds: int = field(
        default_factory=lambda: _env_int("RATE_LIMIT_WINDOW_SECONDS", 300)
    )
    # CORS origins for the Next frontend.
    allowed_origins: list[str] = field(
        default_factory=lambda: _env_list("ALLOWED_ORIGINS", ["http://localhost:3000"])
    )
    # Outbound proxy, e.g. http://user:pass@host:port. Hosted deployments usually
    # need one because platforms block datacenter IPs.
    proxy: str | None = field(default_factory=lambda: os.environ.get("PROXY") or None)
    # Path to a Netscape-format cookies.txt, handed to yt-dlp for age/bot gates.
    cookies_file: str | None = field(default_factory=lambda: os.environ.get("COOKIES_FILE") or None)
    # Path to an instaloader session file created offline by the operator.
    # There is deliberately no way for a website visitor to supply credentials.
    instagram_session_file: str | None = field(
        default_factory=lambda: os.environ.get("INSTAGRAM_SESSION_FILE") or None
    )
    instagram_username: str | None = field(
        default_factory=lambda: os.environ.get("INSTAGRAM_USERNAME") or None
    )
    # Operator-only fallback when no session file exists: the backend logs in
    # once at startup and caches the session. Never populated from a request.
    instagram_password: str | None = field(
        default_factory=lambda: os.environ.get("INSTAGRAM_PASSWORD") or None
    )
    # Allow the catch-all yt-dlp source to attempt any URL.
    enable_generic_source: bool = field(
        default_factory=lambda: _env_bool("ENABLE_GENERIC_SOURCE", True)
    )


settings = Settings()
settings.download_dir.mkdir(parents=True, exist_ok=True)
