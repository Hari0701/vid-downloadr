"""Capability discovery and the pre-download metadata preview."""
from __future__ import annotations

from fastapi import APIRouter, HTTPException

from ..schemas import DownloadRequest, MediaInfo, SourceDescriptor
from ..sources import DownloadError, all_sources, resolve

router = APIRouter(prefix="/api", tags=["sources"])


@router.get("/sources", response_model=list[SourceDescriptor])
def list_sources() -> list[SourceDescriptor]:
    """What this deployment can handle. The UI uses this to build its controls."""
    return [source.descriptor() for source in all_sources()]


@router.post("/info", response_model=MediaInfo)
def probe(request: DownloadRequest) -> MediaInfo:
    """Look up title, thumbnail and available qualities without downloading."""
    source = resolve(request.url)
    if source is None:
        raise HTTPException(status_code=422, detail="No downloader knows how to handle that link.")
    if not source.supports_info:
        return MediaInfo(url=request.url, source=source.name)
    try:
        info = source.fetch_info(request.url)
    except DownloadError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    except Exception as exc:  # noqa: BLE001
        raise HTTPException(status_code=502, detail="Could not read that link.") from exc
    if info is None:
        raise HTTPException(status_code=422, detail="Nothing downloadable was found at that link.")
    return info
