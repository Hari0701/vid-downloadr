"""vid-downloadr API."""
from __future__ import annotations

import asyncio
import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from .config import settings
from .jobs import manager
from .ratelimit import RateLimitMiddleware
from .routers import jobs as jobs_router
from .routers import sources as sources_router

logging.basicConfig(
    level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s: %(message)s"
)
logger = logging.getLogger(__name__)


async def _reaper() -> None:
    """Delete expired downloads on a loop so disk use stays bounded."""
    while True:
        try:
            await asyncio.sleep(settings.cleanup_interval_seconds)
            removed = await asyncio.to_thread(manager.reap)
            if removed:
                logger.info("Reaped %d expired job(s)", removed)
        except asyncio.CancelledError:
            raise
        except Exception:  # noqa: BLE001 - the reaper must never die
            logger.exception("Cleanup pass failed")


@asynccontextmanager
async def lifespan(app: FastAPI):
    manager.start(asyncio.get_running_loop())
    task = asyncio.create_task(_reaper())
    logger.info("Serving downloads from %s", settings.download_dir)
    try:
        yield
    finally:
        task.cancel()
        manager.shutdown()


app = FastAPI(
    title="vid-downloadr",
    description="Open-source media downloader API.",
    version="2.0.0",
    lifespan=lifespan,
)

app.add_middleware(RateLimitMiddleware)
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.allowed_origins,
    allow_credentials=False,
    allow_methods=["GET", "POST", "DELETE", "OPTIONS"],
    allow_headers=["*"],
)

app.include_router(sources_router.router)
app.include_router(jobs_router.router)


@app.get("/api/health", tags=["meta"])
def health() -> dict:
    return {
        "status": "ok",
        "version": app.version,
        "active_jobs": len(manager.list_jobs()),
        "limits": {
            "max_filesize_mb": settings.max_filesize_mb,
            "file_ttl_seconds": settings.file_ttl_seconds,
            "max_concurrent_downloads": settings.max_concurrent_downloads,
        },
    }
