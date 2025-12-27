"""vid-downloadr API."""
from __future__ import annotations

import asyncio
import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from .config import settings
from .jobs import manager
from .routers import jobs as jobs_router
from .routers import sources as sources_router

logging.basicConfig(
    level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s: %(message)s"
)
logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    manager.bind_loop(asyncio.get_running_loop())
    logger.info("Serving downloads from %s", settings.download_dir)
    try:
        yield
    finally:
        manager.shutdown()


app = FastAPI(
    title="vid-downloadr",
    description="Open-source media downloader API.",
    version="2.0.0",
    lifespan=lifespan,
)

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
