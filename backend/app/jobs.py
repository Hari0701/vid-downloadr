"""In-memory job store, worker pool and progress fan-out.

State lives in this process on purpose: jobs are short-lived and their output is
a temp file on local disk, so there is nothing worth persisting. If you ever run
more than one backend replica, swap this module for Redis + a real queue and
keep the same public surface.
"""
from __future__ import annotations

import asyncio
import logging
import mimetypes
import shutil
import threading
import uuid
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timedelta, timezone
from pathlib import Path

from .config import settings
from .schemas import DownloadOptions, Job, JobProgress, JobStatus, MediaFile
from .sources import DownloadContext, DownloadError, resolve

logger = logging.getLogger(__name__)


def _now() -> datetime:
    return datetime.now(timezone.utc)


class JobCancelled(Exception):
    """Raised inside a worker when the client cancels."""


class JobRecord:
    """A job plus the server-side bits the API never sees."""

    def __init__(self, job: Job, work_dir: Path) -> None:
        self.job = job
        self.work_dir = work_dir
        self.cancel_event = threading.Event()
        self.paths: dict[str, Path] = {}


class JobManager:
    def __init__(self) -> None:
        self._jobs: dict[str, JobRecord] = {}
        self._lock = threading.Lock()
        self._pool = ThreadPoolExecutor(
            max_workers=settings.max_concurrent_downloads, thread_name_prefix="download"
        )
        self._subscribers: dict[str, set[asyncio.Queue]] = {}
        self._loop: asyncio.AbstractEventLoop | None = None

    # -- lifecycle -------------------------------------------------------

    def bind_loop(self, loop: asyncio.AbstractEventLoop) -> None:
        """Remember the API event loop so worker threads can publish into it."""
        self._loop = loop

    def shutdown(self) -> None:
        for record in list(self._jobs.values()):
            record.cancel_event.set()
        self._pool.shutdown(wait=False, cancel_futures=True)

    # -- creation --------------------------------------------------------

    def create(self, url: str, options: DownloadOptions) -> Job:
        source = resolve(url)
        if source is None:
            raise ValueError("No downloader knows how to handle that link.")

        job_id = uuid.uuid4().hex
        work_dir = settings.download_dir / job_id
        work_dir.mkdir(parents=True, exist_ok=True)

        job = Job(
            id=job_id,
            url=url,
            source=source.name,
            status=JobStatus.queued,
            created_at=_now(),
            progress=JobProgress(stage="queued"),
        )
        record = JobRecord(job, work_dir)
        with self._lock:
            self._jobs[job_id] = record

        self._pool.submit(self._run, job_id, url, options)
        return job

    def get(self, job_id: str) -> Job | None:
        record = self._jobs.get(job_id)
        return record.job if record else None

    def list_jobs(self) -> list[Job]:
        with self._lock:
            return [r.job for r in self._jobs.values()]

    def file_path(self, job_id: str, file_id: str) -> Path | None:
        record = self._jobs.get(job_id)
        if record is None or record.job.status is not JobStatus.completed:
            return None
        path = record.paths.get(file_id)
        return path if path and path.exists() else None

    def cancel(self, job_id: str) -> bool:
        record = self._jobs.get(job_id)
        if record is None or record.job.status in {
            JobStatus.completed,
            JobStatus.failed,
            JobStatus.cancelled,
        }:
            return False
        record.cancel_event.set()
        record.job.status = JobStatus.cancelled
        record.job.completed_at = _now()
        self._publish(job_id)
        return True

    # -- worker ----------------------------------------------------------

    def _run(self, job_id: str, url: str, options: DownloadOptions) -> None:
        record = self._jobs.get(job_id)
        if record is None:
            return
        job = record.job
        source = resolve(url)
        if source is None:  # pragma: no cover - create() already checked
            self._fail(job_id, "No downloader knows how to handle that link.")
            return

        job.status = JobStatus.running
        job.progress.stage = "starting"
        self._publish(job_id)

        def check_cancelled() -> None:
            if record.cancel_event.is_set():
                raise JobCancelled

        def report(
            percent: float = 0.0,
            speed: float = 0.0,
            downloaded: int = 0,
            total: int | None = None,
            stage: str = "downloading",
            eta: float | None = None,
        ) -> None:
            job.progress = JobProgress(
                percent=round(max(0.0, min(percent, 100.0)), 2),
                speed_bytes_per_sec=speed or 0.0,
                eta_seconds=eta,
                downloaded_bytes=downloaded,
                total_bytes=total,
                stage=stage,
            )
            self._publish(job_id, throttle=True)

        ctx = DownloadContext(
            work_dir=record.work_dir, report=report, check_cancelled=check_cancelled
        )

        try:
            # Metadata first so the UI can show a title while bytes move.
            if source.supports_info:
                try:
                    info = source.fetch_info(url)
                    if info:
                        job.title = info.title
                        job.thumbnail = info.thumbnail
                        self._publish(job_id)
                except Exception as exc:  # noqa: BLE001 - preview is best-effort
                    logger.debug("info probe failed for %s: %s", url, exc)

            check_cancelled()
            files = source.download(url, options, ctx)
            check_cancelled()

            job.files = [self._register_file(record, path) for path in files if path.exists()]
            if not job.files:
                raise DownloadError("The download produced no files.")

            job.status = JobStatus.completed
            job.progress = JobProgress(percent=100.0, stage="done")
            job.completed_at = _now()
            job.expires_at = job.completed_at + timedelta(seconds=settings.file_ttl_seconds)
            if not job.title:
                job.title = job.files[0].filename
            self._publish(job_id)

        except JobCancelled:
            job.status = JobStatus.cancelled
            job.completed_at = _now()
            shutil.rmtree(record.work_dir, ignore_errors=True)
            self._publish(job_id)
        except DownloadError as exc:
            self._fail(job_id, str(exc))
        except Exception as exc:  # noqa: BLE001
            logger.exception("Unexpected failure on job %s", job_id)
            self._fail(job_id, f"Unexpected error: {exc}"[:300])

    def _register_file(self, record: JobRecord, path: Path) -> MediaFile:
        file_id = uuid.uuid4().hex[:12]
        record.paths[file_id] = path
        content_type = mimetypes.guess_type(path.name)[0] or "application/octet-stream"
        return MediaFile(
            id=file_id,
            filename=path.name,
            size_bytes=path.stat().st_size,
            content_type=content_type,
            download_url=f"/api/jobs/{record.job.id}/files/{file_id}",
        )

    def _fail(self, job_id: str, message: str) -> None:
        record = self._jobs.get(job_id)
        if record is None:
            return
        record.job.status = JobStatus.failed
        record.job.error = message
        record.job.completed_at = _now()
        record.job.expires_at = record.job.completed_at + timedelta(minutes=10)
        shutil.rmtree(record.work_dir, ignore_errors=True)
        self._publish(job_id)

    # -- progress fan-out ------------------------------------------------

    def subscribe(self, job_id: str) -> asyncio.Queue:
        queue: asyncio.Queue = asyncio.Queue(maxsize=64)
        self._subscribers.setdefault(job_id, set()).add(queue)
        return queue

    def unsubscribe(self, job_id: str, queue: asyncio.Queue) -> None:
        subscribers = self._subscribers.get(job_id)
        if subscribers:
            subscribers.discard(queue)
            if not subscribers:
                self._subscribers.pop(job_id, None)

    def _publish(self, job_id: str, throttle: bool = False) -> None:
        """Push the current job state to every SSE subscriber.

        Called from worker threads, so the queue put is bounced onto the API
        loop. Progress updates use put_nowait and are dropped when a slow client
        backs up — the next tick carries the same information.
        """
        record = self._jobs.get(job_id)
        loop = self._loop
        if record is None or loop is None:
            return
        subscribers = self._subscribers.get(job_id)
        if not subscribers:
            return
        payload = record.job.model_copy(deep=True)

        def deliver() -> None:
            for queue in list(self._subscribers.get(job_id, ())):
                try:
                    queue.put_nowait(payload)
                except asyncio.QueueFull:
                    if not throttle:
                        # Terminal states must not be dropped: make room.
                        try:
                            queue.get_nowait()
                            queue.put_nowait(payload)
                        except (asyncio.QueueEmpty, asyncio.QueueFull):
                            pass

        loop.call_soon_threadsafe(deliver)

    # -- retention -------------------------------------------------------

    def reap(self) -> int:
        """Delete expired jobs and their files. Returns how many were removed."""
        now = _now()
        removed = 0
        with self._lock:
            for job_id, record in list(self._jobs.items()):
                expires = record.job.expires_at
                if expires is None or expires > now:
                    continue
                shutil.rmtree(record.work_dir, ignore_errors=True)
                record.job.status = JobStatus.expired
                record.job.files = []
                self._jobs.pop(job_id, None)
                removed += 1

        # Sweep orphaned directories left behind by a crash or restart.
        cutoff = now.timestamp() - settings.file_ttl_seconds
        for path in settings.download_dir.iterdir():
            if path.is_dir() and path.name not in self._jobs and path.stat().st_mtime < cutoff:
                shutil.rmtree(path, ignore_errors=True)
        return removed


manager = JobManager()
