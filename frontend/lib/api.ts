/** Typed client for the FastAPI backend. Mirrors backend/app/schemas.py. */

export type JobStatus =
  | "queued"
  | "running"
  | "completed"
  | "failed"
  | "cancelled"
  | "expired";

export interface DownloadOptions {
  quality: string;
  audio_only: boolean;
  audio_format: string;
  playlist: boolean;
  start_time?: number | null;
  duration?: number | null;
}

export interface MediaFile {
  id: string;
  filename: string;
  size_bytes: number;
  content_type: string;
  download_url: string;
}

export interface JobProgress {
  percent: number;
  speed_bytes_per_sec: number;
  eta_seconds: number | null;
  downloaded_bytes: number;
  total_bytes: number | null;
  stage: string;
}

export interface Job {
  id: string;
  url: string;
  source: string;
  status: JobStatus;
  title: string | null;
  thumbnail: string | null;
  progress: JobProgress;
  files: MediaFile[];
  error: string | null;
  created_at: string;
  completed_at: string | null;
  expires_at: string | null;
}

export interface MediaInfo {
  url: string;
  source: string;
  title: string | null;
  uploader: string | null;
  thumbnail: string | null;
  duration_seconds: number | null;
  is_playlist: boolean;
  entry_count: number | null;
  available_qualities: string[];
  extra: Record<string, unknown>;
}

export interface SourceDescriptor {
  name: string;
  label: string;
  domains: string[];
  supports_quality: boolean;
  supports_audio_only: boolean;
  supports_playlist: boolean;
  supports_info: boolean;
  requires_operator_credentials: boolean;
  note: string | null;
  /** False when this instance is missing something the source needs. */
  configured: boolean;
  setup_hint: string | null;
}

export class ApiError extends Error {}

async function request<T>(path: string, init?: RequestInit): Promise<T> {
  const response = await fetch(path, {
    ...init,
    headers: { "Content-Type": "application/json", ...init?.headers },
  });
  if (!response.ok) {
    let detail = `Request failed (${response.status})`;
    try {
      const body = await response.json();
      if (typeof body.detail === "string") detail = body.detail;
      else if (Array.isArray(body.detail)) detail = body.detail[0]?.msg ?? detail;
    } catch {
      /* non-JSON error body; keep the generic message */
    }
    throw new ApiError(detail);
  }
  return response.status === 204 ? (undefined as T) : ((await response.json()) as T);
}

export const listSources = () => request<SourceDescriptor[]>("/api/sources");

export const fetchInfo = (url: string, signal?: AbortSignal) =>
  request<MediaInfo>("/api/info", {
    method: "POST",
    body: JSON.stringify({ url }),
    signal,
  });

export const createJob = (url: string, options: DownloadOptions) =>
  request<Job>("/api/jobs", {
    method: "POST",
    body: JSON.stringify({ url, options }),
  });

export const getJob = (id: string) => request<Job>(`/api/jobs/${id}`);

export const cancelJob = (id: string) =>
  request<void>(`/api/jobs/${id}`, { method: "DELETE" });

/**
 * Subscribe to a job's progress stream.
 * Returns an unsubscribe function. Falls back to polling if SSE fails, so the
 * UI still updates behind proxies that buffer event streams.
 */
export function subscribeToJob(id: string, onUpdate: (job: Job) => void): () => void {
  let closed = false;
  let poller: ReturnType<typeof setInterval> | undefined;

  const source = new EventSource(`/api/jobs/${id}/events`);

  const startPolling = () => {
    if (closed || poller) return;
    poller = setInterval(async () => {
      try {
        const job = await getJob(id);
        onUpdate(job);
        if (isFinal(job.status)) stop();
      } catch {
        stop();
      }
    }, 1500);
  };

  const stop = () => {
    closed = true;
    source.close();
    if (poller) clearInterval(poller);
  };

  source.onmessage = (event) => {
    if (closed) return;
    const job = JSON.parse(event.data) as Job;
    onUpdate(job);
    if (isFinal(job.status)) stop();
  };
  source.onerror = () => {
    // EventSource retries on its own; polling covers the case where it cannot.
    if (!closed) startPolling();
  };

  return stop;
}

export const isFinal = (status: JobStatus) =>
  status === "completed" || status === "failed" || status === "cancelled" || status === "expired";

export function formatBytes(bytes: number): string {
  if (!bytes) return "0 B";
  const units = ["B", "KB", "MB", "GB"];
  const exponent = Math.min(Math.floor(Math.log(bytes) / Math.log(1024)), units.length - 1);
  return `${(bytes / 1024 ** exponent).toFixed(exponent === 0 ? 0 : 1)} ${units[exponent]}`;
}

export function formatDuration(seconds: number | null | undefined): string {
  if (seconds == null || !Number.isFinite(seconds)) return "";
  const total = Math.round(seconds);
  const h = Math.floor(total / 3600);
  const m = Math.floor((total % 3600) / 60);
  const s = total % 60;
  const pad = (n: number) => String(n).padStart(2, "0");
  return h > 0 ? `${h}:${pad(m)}:${pad(s)}` : `${m}:${pad(s)}`;
}
