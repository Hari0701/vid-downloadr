# vid-downloadr

Open-source, self-hostable media downloader. Paste a link, pick a format, get the file.

A **Next.js** frontend over a **FastAPI** backend. Sources are plugins: YouTube, Instagram,
Twitter/X and Pinterest ship in the box, and a catch-all yt-dlp source covers the thousand-plus
other sites yt-dlp recognises.

---

## Contents

- [Quick start](#quick-start)
- [Configuration](#configuration)
- [How it works](#how-it-works)
- [Adding a source](#adding-a-source)
- [API](#api)
- [Deployment](#deployment)
- [Running it honestly](#running-it-honestly)
- [License](#license)

---

## Quick start

### Docker (recommended)

```bash
docker compose up --build
```

The app is on <http://localhost:3000>; the API is on <http://localhost:8000> and its interactive
docs are at `/docs`.

### Local development

The backend needs Python 3.11+ and `ffmpeg` on PATH (yt-dlp uses it to mux video with audio and to
extract audio).

```bash
cd backend
python3 -m venv .venv && .venv/bin/pip install -r requirements.txt
PYTHONPATH=. .venv/bin/uvicorn app.main:app --reload --port 8000
```

```bash
cd frontend
npm install && npm run dev
```

Next proxies `/api/*` to the backend, so the browser only ever talks to one origin. Point it
elsewhere with `BACKEND_URL`.

Note that Next resolves rewrites at **build** time and bakes them into the route manifest, so
`BACKEND_URL` has to be set when you build the frontend, not when you start it. The frontend image
takes it as a build arg for exactly this reason.

Tests:

```bash
cd backend
.venv/bin/pip install -r requirements-dev.txt
.venv/bin/python -m pytest
```

They are network-free — a stub source stands in for the real downloaders.

---

## Configuration

Every value is an environment variable on the backend, and every one has a default. See
`backend/.env.example`.

| Variable | Default | What it does |
| --- | --- | --- |
| `DOWNLOAD_DIR` | system temp | Where finished files wait to be collected |
| `FILE_TTL_SECONDS` | `3600` | How long a finished file survives before deletion |
| `MAX_CONCURRENT_DOWNLOADS` | `3` | Worker threads doing real downloading |
| `MAX_FILESIZE_MB` | `2048` | Hard per-download ceiling |
| `RATE_LIMIT_REQUESTS` / `RATE_LIMIT_WINDOW_SECONDS` | `20` / `300` | Per-IP limit on the expensive endpoints |
| `ALLOWED_ORIGINS` | `http://localhost:3000` | CORS allow-list |
| `ENABLE_GENERIC_SOURCE` | `true` | Whether unknown links fall through to yt-dlp |
| `PROXY` | — | Outbound proxy for all downloaders |
| `COOKIES_FILE` | — | Netscape `cookies.txt` handed to yt-dlp |
| `INSTAGRAM_USERNAME` | — | Operator account used for every Instagram request |
| `INSTAGRAM_SESSION_FILE` | — | Session created offline, or where to cache one |
| `INSTAGRAM_PASSWORD` | — | Alternative to a session file, see below |

### About Instagram credentials

This service **never asks a visitor to log in**, and no visitor password reaches the API.

Instagram now refuses anonymous metadata requests almost everywhere, so the source needs a login to
do anything. The operator configures one login for the whole instance, in either of two ways:

```bash
# Preferred: make a session offline, keep secrets out of the environment
instaloader --login=<your-username>   # writes ~/.config/instaloader/session-<user>
```

```yaml
# docker-compose.yml — point at that session
environment:
  INSTAGRAM_USERNAME: your-username
  INSTAGRAM_SESSION_FILE: /data/instagram.session
volumes:
  - ~/.config/instaloader/session-your-username:/data/instagram.session:ro
```

Or set `INSTAGRAM_USERNAME` and `INSTAGRAM_PASSWORD` and the backend logs in once at startup,
caching the session to `INSTAGRAM_SESSION_FILE` if you set one so restarts do not re-authenticate.

Either way it is the *operator's* account doing every request. Use a throwaway one: Instagram bans
accounts for automated access, and a public instance will get it rate-limited fast. The frontend
reads `/api/sources` and greys Instagram out with a setup hint when no login is configured, so
nobody pastes a link into a dead end.

---

## How it works

```
Browser ──POST /api/jobs──▶ FastAPI ──▶ thread pool ──▶ Source plugin ──▶ temp dir
   │                            │                                            │
   └──GET .../events (SSE)◀─────┴── progress published from the worker        │
   └──GET .../files/{id} ◀───────────────────────────────────────────────────┘
                                        reaper deletes on a TTL
```

- A download is a **job**. `POST /api/jobs` returns immediately with an id; the work happens on a
  thread pool bounded by `MAX_CONCURRENT_DOWNLOADS`.
- Progress streams over **server-sent events**. The client falls back to polling if SSE cannot get
  through a proxy, and the stream re-checks job state on every keepalive so it can never strand a
  client on a job that already finished.
- Job state is deliberately **in-process**. Jobs are short-lived and their output is a local temp
  file, so there is nothing worth persisting. Running more than one replica means swapping
  `app/jobs.py` for Redis and a real queue — the public surface is designed to survive that.
- A background reaper deletes expired jobs and sweeps orphaned directories left by a crash.

---

## Adding a source

Adding a site is one file. Subclass `Source`, implement `download`, register it:

```python
# backend/app/sources/example.py
from pathlib import Path
from ..schemas import DownloadOptions
from .base import DownloadContext, Source
from .http import stream_to_file


class ExampleSource(Source):
    name = "example"
    label = "Example"
    domains = ("example.com",)
    supports_info = True
    priority = 20  # lower runs first; the yt-dlp catch-all sits at 1000

    def download(self, url: str, options: DownloadOptions, ctx: DownloadContext) -> list[Path]:
        return [stream_to_file(find_media_url(url), ctx.work_dir / "example.mp4", ctx)]
```

Add it to `SOURCES` in `backend/app/sources/__init__.py`. That is the whole change: the frontend
reads `/api/sources` and builds its controls from the capability flags each source advertises, so a
source that sets `supports_audio_only` gets the audio toggle without any frontend edit.

If the site is already supported by yt-dlp, you do not need a source at all — the generic catch-all
handles it.

---

## API

| Method | Path | Purpose |
| --- | --- | --- |
| `GET` | `/api/health` | Liveness and effective limits |
| `GET` | `/api/sources` | Registered sources and their capabilities |
| `POST` | `/api/info` | Metadata preview without downloading |
| `POST` | `/api/jobs` | Start a download; returns `202` and a job |
| `GET` | `/api/jobs/{id}` | Current job state |
| `GET` | `/api/jobs/{id}/events` | SSE progress stream |
| `GET` | `/api/jobs/{id}/files/{file_id}` | Download a finished file |
| `DELETE` | `/api/jobs/{id}` | Cancel a running job |

Full OpenAPI schema at `/docs`.

---

## Deployment

`docker compose up -d` behind a TLS-terminating reverse proxy is the whole story for a single box.
Two things to get right:

**Disable buffering on the SSE endpoint.** The backend already sends `X-Accel-Buffering: no`, but
nginx needs telling too:

```nginx
location /api/ {
    proxy_pass http://127.0.0.1:8000;
    proxy_buffering off;
    proxy_read_timeout 1h;
}
```

**Expect platforms to block your server.** YouTube and Instagram treat datacenter IPs as hostile and
will bot-check or rate-limit them, sometimes immediately. This is not something code fixes — set
`PROXY` to a residential proxy and/or supply `COOKIES_FILE`, and size your expectations
accordingly. The app surfaces these as readable errors rather than pretending they did not happen.

Splitting the tiers (frontend on Vercel, backend on a container host) works too: set `BACKEND_URL`
on the frontend and add its origin to `ALLOWED_ORIGINS` on the backend. The backend needs a writable
disk and is not a good fit for serverless functions — downloads outlive typical function timeouts.

---

## Running it honestly

This tool downloads media you point it at. That does not make every download lawful or fair.
Respect each platform's terms of service, copyright, and the people who made the thing you are
downloading. If you host a public instance, you are responsible for what it is used for — rate
limits and a short file TTL are in the box for a reason, and they are a floor, not a policy.

---

## License

MIT. See [LICENSE](LICENSE).
