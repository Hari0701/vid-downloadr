FROM python:3.12-slim

# ffmpeg is required for muxing video+audio and for audio extraction.
RUN apt-get update \
 && apt-get install -y --no-install-recommends ffmpeg ca-certificates \
 && rm -rf /var/lib/apt/lists/*

WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY app ./app

# Downloads live here; mount a volume if you want them to survive a restart.
ENV DOWNLOAD_DIR=/data/downloads
RUN mkdir -p /data/downloads && useradd -m -u 10001 app && chown -R app /data
USER app

EXPOSE 8000
HEALTHCHECK --interval=30s --timeout=5s --start-period=10s \
  CMD python -c "import urllib.request;urllib.request.urlopen('http://127.0.0.1:8000/api/health')" || exit 1

CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
