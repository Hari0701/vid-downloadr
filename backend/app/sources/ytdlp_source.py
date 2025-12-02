"""yt-dlp backed sources: YouTube plus a catch-all for everything else it knows."""
from __future__ import annotations

import logging
from pathlib import Path

import yt_dlp

from ..config import settings
from ..schemas import DownloadOptions, MediaInfo
from .base import DownloadContext, DownloadError, Source

logger = logging.getLogger(__name__)


class YtDlpSource(Source):
    """Shared yt-dlp plumbing. Subclasses only narrow the domain list."""

    name = "ytdlp"
    label = "yt-dlp"
    supports_quality = True
    supports_audio_only = True
    supports_playlist = True
    supports_info = True
    priority = 50

    def _base_opts(self) -> dict:
        opts: dict = {
            "quiet": True,
            "no_warnings": True,
            "noprogress": True,
            "restrictfilenames": True,
            "noplaylist": True,
            "retries": 3,
            "socket_timeout": 30,
            # Never let a single request fill the disk.
            "max_filesize": settings.max_filesize_mb * 1024 * 1024,
        }
        if settings.proxy:
            opts["proxy"] = settings.proxy
        if settings.cookies_file:
            opts["cookiefile"] = settings.cookies_file
        return opts

    def fetch_info(self, url: str) -> MediaInfo | None:
        opts = self._base_opts() | {"skip_download": True, "extract_flat": "in_playlist"}
        try:
            with yt_dlp.YoutubeDL(opts) as ydl:
                info = ydl.extract_info(url, download=False)
        except Exception as exc:  # noqa: BLE001 - yt-dlp raises many types
            raise DownloadError(_friendly(exc)) from exc

        if info is None:
            return None

        entries = info.get("entries")
        qualities = sorted(
            {
                f"{fmt['height']}p"
                for fmt in (info.get("formats") or [])
                if isinstance(fmt.get("height"), int)
            },
            key=lambda q: int(q.rstrip("p")),
        )
        return MediaInfo(
            url=url,
            source=self.name,
            title=info.get("title"),
            uploader=info.get("uploader") or info.get("channel"),
            thumbnail=info.get("thumbnail"),
            duration_seconds=info.get("duration"),
            is_playlist=bool(entries),
            entry_count=len(entries) if entries else None,
            available_qualities=qualities,
            extra={"extractor": info.get("extractor_key")},
        )

    def download(self, url: str, options: DownloadOptions, ctx: DownloadContext) -> list[Path]:
        opts = self._base_opts()
        opts["outtmpl"] = {"default": str(ctx.work_dir / "%(title).150B.%(ext)s")}
        opts["noplaylist"] = not options.playlist

        if options.audio_only:
            opts["format"] = "bestaudio/best"
            opts["postprocessors"] = [
                {
                    "key": "FFmpegExtractAudio",
                    "preferredcodec": options.audio_format,
                    "preferredquality": "256",
                }
            ]
        elif options.quality == "best":
            opts["format"] = "bestvideo+bestaudio/best"
        else:
            height = int(options.quality.rstrip("pP"))
            opts["format"] = (
                f"bestvideo[height<={height}]+bestaudio/best[height<={height}]/best"
            )
            opts["merge_output_format"] = "mp4"

        if options.start_time is not None or options.duration is not None:
            start = options.start_time or 0.0
            end = start + options.duration if options.duration else None
            opts["download_ranges"] = yt_dlp.utils.download_range_func(
                None, [(start, end if end is not None else float("inf"))]
            )
            opts["force_keyframes_at_cuts"] = True

        def hook(d: dict) -> None:
            ctx.check_cancelled()
            if d.get("status") == "downloading":
                total = d.get("total_bytes") or d.get("total_bytes_estimate")
                downloaded = d.get("downloaded_bytes") or 0
                percent = (downloaded / total * 100) if total else 0.0
                ctx.report(
                    percent=percent,
                    speed=d.get("speed") or 0.0,
                    downloaded=downloaded,
                    total=total,
                    stage="downloading",
                )
            elif d.get("status") == "finished":
                ctx.report(percent=100.0, speed=0.0, stage="processing")

        opts["progress_hooks"] = [hook]

        try:
            with yt_dlp.YoutubeDL(opts) as ydl:
                ydl.download([url])
        except DownloadError:
            raise
        except Exception as exc:  # noqa: BLE001
            logger.warning("yt-dlp failed for %s: %s", url, exc)
            raise DownloadError(_friendly(exc)) from exc

        files = sorted(p for p in ctx.work_dir.iterdir() if p.is_file() and not p.name.endswith(".part"))
        if not files:
            raise DownloadError("The download produced no files.")
        return files


class YouTubeSource(YtDlpSource):
    name = "youtube"
    label = "YouTube"
    domains = ("youtube.com", "youtu.be", "music.youtube.com", "m.youtube.com")
    priority = 10
    note = "Hosted servers are often bot-checked by YouTube; set COOKIES_FILE or PROXY if you see failures."


def _friendly(exc: Exception) -> str:
    """Turn yt-dlp's noisy errors into something worth showing a user."""
    text = str(exc)
    lowered = text.lower()
    if "sign in to confirm" in lowered or "bot" in lowered:
        return "The site asked this server to prove it is not a bot. Try again later."
    if "private" in lowered or "login" in lowered or "members-only" in lowered:
        return "This content is private or requires an account."
    if "unavailable" in lowered or "not exist" in lowered or "404" in lowered:
        return "That content is unavailable or the link is wrong."
    if "unsupported url" in lowered or "no suitable" in lowered:
        return "That link is not supported."
    if "max_filesize" in lowered or "larger than" in lowered:
        return f"That file is larger than the {settings.max_filesize_mb} MB limit."
    if "geo" in lowered and "restrict" in lowered:
        return "This content is blocked in the server's region."
    # Strip yt-dlp's "ERROR: " prefix and any ANSI noise.
    return text.replace("ERROR: ", "").strip()[:300] or "The download failed."
