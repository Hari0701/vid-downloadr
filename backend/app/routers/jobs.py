"""Job creation, live progress and file delivery."""
from __future__ import annotations

import asyncio
import json
from urllib.parse import quote

from fastapi import APIRouter, HTTPException
from fastapi.responses import FileResponse, StreamingResponse

from ..jobs import manager
from ..schemas import DownloadRequest, Job, JobStatus

router = APIRouter(prefix="/api/jobs", tags=["jobs"])

# Terminal states end the SSE stream.
FINAL = {JobStatus.completed, JobStatus.failed, JobStatus.cancelled, JobStatus.expired}


@router.post("", response_model=Job, status_code=202)
def create_job(request: DownloadRequest) -> Job:
    try:
        return manager.create(request.url, request.options)
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    except RuntimeError as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc


@router.get("/{job_id}", response_model=Job)
def get_job(job_id: str) -> Job:
    job = manager.get(job_id)
    if job is None:
        raise HTTPException(status_code=404, detail="That job has finished expiring or never existed.")
    return job


@router.delete("/{job_id}", status_code=204)
def cancel_job(job_id: str) -> None:
    if not manager.cancel(job_id):
        raise HTTPException(status_code=409, detail="That job cannot be cancelled.")


@router.get("/{job_id}/events")
async def job_events(job_id: str) -> StreamingResponse:
    """Server-sent events carrying the full job object on every change."""
    job = manager.get(job_id)
    if job is None:
        raise HTTPException(status_code=404, detail="Unknown job.")

    queue = manager.subscribe(job_id)

    async def stream():
        try:
            # Emit current state immediately so a late subscriber is never blank.
            # This must be a snapshot: manager.get returns the live job, which the
            # worker thread keeps mutating. Testing the live object after the yield
            # would let a job that finished in the meantime look "already final"
            # and close the stream without ever emitting its terminal event.
            snapshot = job.model_copy(deep=True)
            yield _sse(snapshot)
            if snapshot.status in FINAL:
                return

            # Completion may have landed between subscribe() and now, in which
            # case it is in neither the snapshot nor the queue. Re-read once.
            current = manager.get(job_id)
            if current is None:
                return
            if current.status in FINAL:
                yield _sse(current)
                return
            while True:
                # No is_disconnected() poll here: it reports a disconnect as soon
                # as the request body is consumed, which would close the stream
                # on a job that is still running. Starlette cancels this
                # generator when the client actually goes away, and the finally
                # block below unsubscribes.
                try:
                    update = await asyncio.wait_for(queue.get(), timeout=15)
                except asyncio.TimeoutError:
                    # Re-read the job rather than trusting the pub/sub alone, so a
                    # dropped notification can never strand the client on a stream
                    # that will never close.
                    current = manager.get(job_id)
                    if current is None:
                        return
                    if current.status in FINAL:
                        yield _sse(current)
                        return
                    # Comment frame keeps proxies from closing an idle stream.
                    yield ": keepalive\n\n"
                    continue
                yield _sse(update)
                if update.status in FINAL:
                    return
        finally:
            manager.unsubscribe(job_id, queue)

    return StreamingResponse(
        stream(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache, no-transform",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",
        },
    )


@router.get("/{job_id}/files/{file_id}")
def download_file(job_id: str, file_id: str) -> FileResponse:
    path = manager.file_path(job_id, file_id)
    if path is None:
        raise HTTPException(status_code=404, detail="That file is gone or has expired.")
    # RFC 5987 so non-ASCII titles survive the header.
    disposition = f"attachment; filename*=UTF-8''{quote(path.name)}"
    return FileResponse(
        path,
        filename=path.name,
        headers={"Content-Disposition": disposition},
    )


def _sse(job: Job) -> str:
    return f"data: {json.dumps(job.model_dump(mode='json'))}\n\n"
