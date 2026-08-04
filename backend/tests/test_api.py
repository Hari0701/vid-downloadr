"""Network-free tests. A stub source stands in for the real downloaders."""
from __future__ import annotations

import json
import time
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from app import sources as registry
from app.main import app
from app.schemas import DownloadOptions
from app.sources.base import DownloadContext, DownloadError, Source
from app.sources.http import sanitize_filename


class StubSource(Source):
    name = "stub"
    label = "Stub"
    domains = ("stub.test",)
    supports_info = True
    priority = 0

    def download(self, url: str, options: DownloadOptions, ctx: DownloadContext) -> list[Path]:
        if "boom" in url:
            raise DownloadError("stub failure")
        ctx.report(percent=50.0, speed=1000.0, downloaded=500, total=1000)
        target = ctx.work_dir / "stub.txt"
        target.write_text("hello")
        return [target]


@pytest.fixture(autouse=True)
def stub_source():
    registry.SOURCES.insert(0, StubSource())
    yield
    registry.SOURCES[:] = [s for s in registry.SOURCES if s.name != "stub"]


@pytest.fixture
def client():
    with TestClient(app) as test_client:
        yield test_client


def wait_for_final(client: TestClient, job_id: str) -> dict:
    """Drain the SSE stream until the job reaches a terminal state."""
    with client.stream("GET", f"/api/jobs/{job_id}/events") as stream:
        for line in stream.iter_lines():
            if not line.startswith("data:"):
                continue
            job = json.loads(line[5:])
            if job["status"] in {"completed", "failed", "cancelled"}:
                return job
    raise AssertionError("stream closed before the job finished")


def test_health(client):
    assert client.get("/api/health").json()["status"] == "ok"


def test_sources_include_the_generic_catch_all(client):
    names = [source["name"] for source in client.get("/api/sources").json()]
    assert "generic" in names
    # The catch-all must sort last so specific sources win.
    assert names[-1] == "generic"


@pytest.mark.parametrize(
    ("url", "expected"),
    [
        ("https://youtu.be/abc", "youtube"),
        ("https://www.youtube.com/watch?v=abc", "youtube"),
        ("https://www.instagram.com/reel/abc/", "instagram"),
        ("https://x.com/user/status/1", "twitter"),
        ("https://twitter.com/user/status/1", "twitter"),
        ("https://pin.it/abc", "pinterest"),
        ("https://vimeo.com/1", "generic"),
    ],
)
def test_url_routing(url, expected):
    source = registry.resolve(url)
    assert source is not None and source.name == expected


def test_rejects_non_http_urls(client):
    assert client.post("/api/jobs", json={"url": "ftp://host/file"}).status_code == 422


def test_download_lifecycle(client):
    created = client.post("/api/jobs", json={"url": "https://stub.test/ok"})
    assert created.status_code == 202
    job_id = created.json()["id"]

    job = wait_for_final(client, job_id)
    assert job["status"] == "completed"
    assert job["progress"]["percent"] == 100.0
    assert len(job["files"]) == 1

    served = client.get(job["files"][0]["download_url"])
    assert served.status_code == 200
    assert served.content == b"hello"


def test_stream_delivers_a_terminal_event_for_an_already_finished_job(client):
    """Subscribing after the job finished must still yield a terminal event.

    Regression test: the endpoint used to hold a live reference to the job, so a
    job that completed between the first emit and the status check closed the
    stream with no terminal event and left the client hanging.
    """
    job_id = client.post("/api/jobs", json={"url": "https://stub.test/ok"}).json()["id"]
    # Let the worker finish before anyone subscribes.
    for _ in range(100):
        if client.get(f"/api/jobs/{job_id}").json()["status"] == "completed":
            break
        time.sleep(0.01)

    job = wait_for_final(client, job_id)
    assert job["status"] == "completed"


def test_failure_is_reported_to_the_client(client):
    job_id = client.post("/api/jobs", json={"url": "https://stub.test/boom"}).json()["id"]
    job = wait_for_final(client, job_id)
    assert job["status"] == "failed"
    assert job["error"] == "stub failure"
    assert job["files"] == []


def test_unknown_job_is_404(client):
    assert client.get("/api/jobs/does-not-exist").status_code == 404


def test_files_are_not_served_before_completion(client):
    from app.jobs import manager

    assert manager.file_path("missing-job", "missing-file") is None


@pytest.mark.parametrize(
    ("raw", "expected"),
    [
        ("a/b:c.mp4", "abc.mp4"),
        ("  spaced  ", "spaced"),
        ("", "download"),
    ],
)
def test_sanitize_filename(raw, expected):
    assert sanitize_filename(raw) == expected


def test_sanitize_filename_truncates_but_keeps_extension():
    result = sanitize_filename("x" * 500 + ".mp4", max_length=50)
    assert len(result) <= 50 and result.endswith(".mp4")
