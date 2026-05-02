"use client";

import { useCallback, useEffect, useRef, useState } from "react";
import {
  ApiError,
  DownloadOptions,
  MediaInfo,
  SourceDescriptor,
  fetchInfo,
  formatDuration,
} from "@/lib/api";

const DEFAULT_QUALITIES = ["360p", "480p", "720p", "1080p", "1440p", "2160p", "best"];

const DEFAULT_OPTIONS: DownloadOptions = {
  quality: "720p",
  audio_only: false,
  audio_format: "mp3",
  playlist: false,
  start_time: null,
  duration: null,
};

interface Props {
  sources: SourceDescriptor[];
  onSubmit: (url: string, options: DownloadOptions) => Promise<void>;
}

/** Which registered source claims this URL, mirroring the backend's matcher. */
function detectSource(url: string, sources: SourceDescriptor[]): SourceDescriptor | null {
  let host: string;
  try {
    host = new URL(url).hostname.toLowerCase().replace(/^www\./, "");
  } catch {
    return null;
  }
  const match = sources.find((source) =>
    source.domains.some((domain) => host === domain || host.endsWith(`.${domain}`)),
  );
  return match ?? sources.find((source) => source.name === "generic") ?? null;
}

export default function DownloadForm({ sources, onSubmit }: Props) {
  const [url, setUrl] = useState("");
  const [options, setOptions] = useState<DownloadOptions>(DEFAULT_OPTIONS);
  const [info, setInfo] = useState<MediaInfo | null>(null);
  const [probing, setProbing] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [submitting, setSubmitting] = useState(false);
  const [showAdvanced, setShowAdvanced] = useState(false);
  const abortRef = useRef<AbortController | null>(null);

  const source = detectSource(url.trim(), sources);
  const isValidUrl = /^https?:\/\/\S+\.\S+/.test(url.trim());

  // Debounced metadata preview so the user sees what they are about to fetch.
  useEffect(() => {
    abortRef.current?.abort();
    setInfo(null);
    setError(null);
    if (!isValidUrl || !source?.supports_info) {
      setProbing(false);
      return;
    }
    const controller = new AbortController();
    abortRef.current = controller;
    setProbing(true);
    const timer = setTimeout(async () => {
      try {
        const result = await fetchInfo(url.trim(), controller.signal);
        if (controller.signal.aborted) return;
        setInfo(result);
        // Prefer a quality the media actually offers.
        if (result.available_qualities.length > 0) {
          setOptions((current) =>
            result.available_qualities.includes(current.quality)
              ? current
              : { ...current, quality: result.available_qualities.at(-1) ?? current.quality },
          );
        }
      } catch (err) {
        if (controller.signal.aborted) return;
        setError(err instanceof ApiError ? err.message : "Could not read that link.");
      } finally {
        if (!controller.signal.aborted) setProbing(false);
      }
    }, 600);

    return () => {
      clearTimeout(timer);
      controller.abort();
    };
  }, [url, isValidUrl, source?.supports_info, source?.name]);

  const submit = useCallback(
    async (event: React.FormEvent) => {
      event.preventDefault();
      if (!isValidUrl || submitting) return;
      setSubmitting(true);
      setError(null);
      try {
        await onSubmit(url.trim(), options);
        setUrl("");
        setInfo(null);
        setOptions((current) => ({ ...current, start_time: null, duration: null }));
      } catch (err) {
        setError(err instanceof ApiError ? err.message : "Could not start that download.");
      } finally {
        setSubmitting(false);
      }
    },
    [isValidUrl, onSubmit, options, submitting, url],
  );

  const qualities = info?.available_qualities.length
    ? [...info.available_qualities, "best"]
    : DEFAULT_QUALITIES;

  return (
    <form
      onSubmit={submit}
      className="rounded-2xl border border-edge-bright bg-panel/70 p-4 shadow-2xl shadow-black/40 backdrop-blur-xl sm:p-5"
    >
      <div className="flex flex-col gap-3 sm:flex-row">
        <div className="relative flex-1">
          <input
            value={url}
            onChange={(event) => setUrl(event.target.value)}
            placeholder="Paste a link — YouTube, Instagram, X, Pinterest, or anything yt-dlp knows"
            aria-label="Media URL"
            className="w-full rounded-xl border border-edge bg-surface/80 px-4 py-3 pr-24 text-sm outline-none placeholder:text-white/30 focus:border-accent"
          />
          {source && isValidUrl && (
            <span className="absolute right-3 top-1/2 -translate-y-1/2 rounded-md bg-accent/15 px-2 py-1 text-xs text-accent-soft">
              {source.label}
            </span>
          )}
        </div>
        <button
          type="submit"
          disabled={!isValidUrl || submitting}
          className="rounded-xl bg-accent px-6 py-3 text-sm font-medium text-white transition hover:bg-accent-soft disabled:cursor-not-allowed disabled:opacity-40"
        >
          {submitting ? "Starting…" : "Download"}
        </button>
      </div>

      {probing && <p className="mt-3 text-xs text-white/40">Reading link…</p>}

      {info && (
        <div className="mt-4 flex gap-3 rounded-xl border border-edge bg-surface/60 p-3">
          {info.thumbnail && (
            // Remote thumbnails come from many hosts; a plain img avoids
            // configuring every domain in next.config.
            // eslint-disable-next-line @next/next/no-img-element
            <img
              src={info.thumbnail}
              alt=""
              className="h-16 w-28 shrink-0 rounded-lg object-cover"
            />
          )}
          <div className="min-w-0">
            <p className="truncate text-sm font-medium">{info.title ?? "Untitled"}</p>
            <p className="mt-1 text-xs text-white/45">
              {[
                info.uploader,
                formatDuration(info.duration_seconds),
                info.is_playlist && info.entry_count ? `${info.entry_count} items` : null,
              ]
                .filter(Boolean)
                .join(" · ")}
            </p>
          </div>
        </div>
      )}

      <div className="mt-4 flex flex-wrap items-center gap-3 text-sm">
        {source?.supports_quality && !options.audio_only && (
          <label className="flex items-center gap-2">
            <span className="text-white/50">Quality</span>
            <select
              value={options.quality}
              onChange={(event) => setOptions({ ...options, quality: event.target.value })}
              className="rounded-lg border border-edge bg-surface px-2 py-1.5 outline-none focus:border-accent"
            >
              {qualities.map((quality) => (
                <option key={quality} value={quality}>
                  {quality}
                </option>
              ))}
            </select>
          </label>
        )}

        {source?.supports_audio_only && (
          <label className="flex items-center gap-2">
            <input
              type="checkbox"
              checked={options.audio_only}
              onChange={(event) => setOptions({ ...options, audio_only: event.target.checked })}
              className="size-4 accent-[var(--color-accent)]"
            />
            <span className="text-white/70">Audio only</span>
          </label>
        )}

        {source?.supports_audio_only && options.audio_only && (
          <select
            value={options.audio_format}
            onChange={(event) => setOptions({ ...options, audio_format: event.target.value })}
            className="rounded-lg border border-edge bg-surface px-2 py-1.5 outline-none focus:border-accent"
          >
            {["mp3", "m4a", "opus", "wav"].map((format) => (
              <option key={format} value={format}>
                {format}
              </option>
            ))}
          </select>
        )}

        {source?.supports_playlist && info?.is_playlist && (
          <label className="flex items-center gap-2">
            <input
              type="checkbox"
              checked={options.playlist}
              onChange={(event) => setOptions({ ...options, playlist: event.target.checked })}
              className="size-4 accent-[var(--color-accent)]"
            />
            <span className="text-white/70">Whole playlist</span>
          </label>
        )}

        {source?.supports_quality && (
          <button
            type="button"
            onClick={() => setShowAdvanced((value) => !value)}
            className="ml-auto text-xs text-white/40 hover:text-white/70"
          >
            {showAdvanced ? "Hide trim" : "Trim a section"}
          </button>
        )}
      </div>

      {showAdvanced && source?.supports_quality && (
        <div className="mt-3 flex flex-wrap gap-3 border-t border-edge pt-3 text-sm">
          <label className="flex items-center gap-2">
            <span className="text-white/50">Start (s)</span>
            <input
              type="number"
              min={0}
              step={0.1}
              value={options.start_time ?? ""}
              onChange={(event) =>
                setOptions({
                  ...options,
                  start_time: event.target.value === "" ? null : Number(event.target.value),
                })
              }
              className="w-24 rounded-lg border border-edge bg-surface px-2 py-1.5 outline-none focus:border-accent"
            />
          </label>
          <label className="flex items-center gap-2">
            <span className="text-white/50">Length (s)</span>
            <input
              type="number"
              min={0.1}
              step={0.1}
              value={options.duration ?? ""}
              onChange={(event) =>
                setOptions({
                  ...options,
                  duration: event.target.value === "" ? null : Number(event.target.value),
                })
              }
              className="w-24 rounded-lg border border-edge bg-surface px-2 py-1.5 outline-none focus:border-accent"
            />
          </label>
        </div>
      )}

      {error && <p className="mt-3 text-sm text-rose-400">{error}</p>}
      {source?.note && isValidUrl && !error && (
        <p className="mt-3 text-xs text-white/35">{source.note}</p>
      )}
    </form>
  );
}
