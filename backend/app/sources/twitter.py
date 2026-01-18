"""Twitter / X media through the public vxtwitter mirror."""
from __future__ import annotations

import re
from pathlib import Path

import requests

from ..schemas import DownloadOptions, MediaInfo
from .base import DownloadContext, DownloadError, Source
from .http import proxies, sanitize_filename, stream_to_file

TWEET_ID = re.compile(r"(?:twitter|x)\.com/[^/]{1,20}/(?:web|status(?:es)?)/(\d{1,20})")
API = "https://api.vxtwitter.com/Twitter/status/{tweet_id}"


class TwitterSource(Source):
    name = "twitter"
    label = "Twitter / X"
    domains = ("twitter.com", "x.com", "vxtwitter.com", "fxtwitter.com")
    supports_info = True
    priority = 20
    note = "Images and videos attached to a tweet."

    @staticmethod
    def _tweet_id(url: str) -> str | None:
        match = TWEET_ID.search(url)
        return match.group(1) if match else None

    def _payload(self, url: str) -> dict:
        tweet_id = self._tweet_id(url)
        if not tweet_id:
            raise DownloadError("That does not look like a link to a tweet.")
        try:
            response = requests.get(API.format(tweet_id=tweet_id), timeout=15, proxies=proxies())
            response.raise_for_status()
            return response.json()
        except requests.HTTPError as exc:
            status = exc.response.status_code if exc.response is not None else 0
            if status == 404:
                raise DownloadError("That tweet does not exist or was deleted.") from exc
            raise DownloadError("Could not read that tweet.") from exc
        except requests.RequestException as exc:
            raise DownloadError("Could not reach Twitter.") from exc

    def fetch_info(self, url: str) -> MediaInfo | None:
        data = self._payload(url)
        media = data.get("media_extended") or []
        return MediaInfo(
            url=url,
            source=self.name,
            title=(data.get("text") or "").strip().split("\n")[0][:120] or "Tweet",
            uploader=data.get("user_screen_name"),
            thumbnail=media[0].get("thumbnail_url") or media[0].get("url") if media else None,
            is_playlist=len(media) > 1,
            entry_count=len(media) or None,
            extra={"likes": data.get("likes"), "retweets": data.get("retweets")},
        )

    def download(self, url: str, options: DownloadOptions, ctx: DownloadContext) -> list[Path]:
        data = self._payload(url)
        media = data.get("media_extended") or []
        if not media:
            raise DownloadError("That tweet has no downloadable media.")

        handle = data.get("user_screen_name") or "tweet"
        stem = sanitize_filename(f"{handle}_{self._tweet_id(url)}")
        files: list[Path] = []
        for index, item in enumerate(media, start=1):
            ctx.check_cancelled()
            media_url = item.get("url")
            if not media_url:
                continue
            ext = ".mp4" if item.get("type") in {"video", "gif"} else ".jpg"
            suffix = f"_{index}" if len(media) > 1 else ""
            files.append(stream_to_file(media_url, ctx.work_dir / f"{stem}{suffix}{ext}", ctx))
            ctx.report(percent=index / len(media) * 100, speed=0.0, stage="downloading")

        if not files:
            raise DownloadError("None of the media in that tweet could be downloaded.")
        return files
