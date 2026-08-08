"use client";

import { useEffect, useState } from "react";
import { Job, formatBytes } from "@/lib/api";

const STATUS_STYLES: Record<Job["status"], string> = {
  queued: "bg-white/10 text-white/60",
  running: "bg-accent/20 text-accent-soft",
  completed: "bg-emerald-500/15 text-emerald-300",
  failed: "bg-rose-500/15 text-rose-300",
  cancelled: "bg-white/10 text-white/45",
  expired: "bg-white/10 text-white/40",
};

/** Live countdown to the moment the server deletes the file. */
function useExpiry(expiresAt: string | null): string | null {
  const [label, setLabel] = useState<string | null>(null);

  useEffect(() => {
    if (!expiresAt) {
      setLabel(null);
      return;
    }
    const tick = () => {
      const remaining = new Date(expiresAt).getTime() - Date.now();
      if (remaining <= 0) {
        setLabel("expired");
        return;
      }
      const minutes = Math.floor(remaining / 60000);
      setLabel(minutes >= 1 ? `${minutes} min left` : "under a minute left");
    };
    tick();
    const timer = setInterval(tick, 30000);
    return () => clearInterval(timer);
  }, [expiresAt]);

  return label;
}

interface Props {
  job: Job;
  onCancel: (id: string) => void;
  onDismiss: (id: string) => void;
}

export default function JobCard({ job, onCancel, onDismiss }: Props) {
  const expiry = useExpiry(job.status === "completed" ? job.expires_at : null);
  const active = job.status === "queued" || job.status === "running";
  const percent = Math.min(job.progress.percent, 100);

  return (
    <li className="rounded-2xl border border-edge bg-panel/70 p-4 backdrop-blur">
      <div className="flex items-start gap-3">
        {job.thumbnail ? (
          // eslint-disable-next-line @next/next/no-img-element
          <img src={job.thumbnail} alt="" className="h-14 w-24 shrink-0 rounded-lg object-cover" />
        ) : (
          <div className="grid h-14 w-24 shrink-0 place-items-center rounded-lg bg-surface text-xs text-white/25">
            {job.source}
          </div>
        )}

        <div className="min-w-0 flex-1">
          <div className="flex items-start justify-between gap-3">
            <p className="truncate text-sm font-medium">{job.title ?? job.url}</p>
            <span className={`shrink-0 rounded-md px-2 py-0.5 text-xs ${STATUS_STYLES[job.status]}`}>
              {job.status}
            </span>
          </div>
          <p className="mt-0.5 truncate text-xs text-white/35">{job.url}</p>

          {active && (
            <div className="mt-3">
              <div
                className={`relative h-1.5 overflow-hidden rounded-full bg-white/10 ${
                  // No percentage yet: show a sweep instead of a bar stuck at zero.
                  percent === 0 ? "shimmer" : ""
                }`}
              >
                <div
                  className="progress-fill h-full rounded-full bg-gradient-to-r from-accent to-fuchsia-500"
                  style={{ width: `${percent}%` }}
                />
              </div>
              <p className="mt-1.5 flex gap-2 text-xs text-white/40">
                <span>{percent.toFixed(0)}%</span>
                <span>·</span>
                <span>{job.progress.stage}</span>
                {job.progress.speed_bytes_per_sec > 0 && (
                  <>
                    <span>·</span>
                    <span>{formatBytes(job.progress.speed_bytes_per_sec)}/s</span>
                  </>
                )}
                {job.progress.total_bytes ? (
                  <>
                    <span>·</span>
                    <span>
                      {formatBytes(job.progress.downloaded_bytes)} /{" "}
                      {formatBytes(job.progress.total_bytes)}
                    </span>
                  </>
                ) : null}
              </p>
            </div>
          )}

          {job.error && <p className="mt-2 text-sm text-rose-400">{job.error}</p>}

          {job.files.length > 0 && (
            <ul className="mt-3 flex flex-col gap-2">
              {job.files.map((file) => (
                <li key={file.id}>
                  <a
                    href={file.download_url}
                    download={file.filename}
                    aria-label={`Download ${file.filename}`}
                    className="flex items-center justify-between gap-3 rounded-lg border border-edge bg-surface/70 px-3 py-2 text-sm transition hover:border-accent"
                  >
                    <span className="truncate">{file.filename}</span>
                    <span className="shrink-0 text-xs text-white/40">
                      {formatBytes(file.size_bytes)} ↓
                    </span>
                  </a>
                </li>
              ))}
            </ul>
          )}

          <div className="mt-3 flex items-center gap-3 text-xs">
            {expiry && <span className="text-white/30">Deleted from the server in {expiry}</span>}
            <span className="flex-1" />
            {active ? (
              <button onClick={() => onCancel(job.id)} className="text-white/40 hover:text-rose-300">
                Cancel
              </button>
            ) : (
              <button onClick={() => onDismiss(job.id)} className="text-white/30 hover:text-white/70">
                Clear
              </button>
            )}
          </div>
        </div>
      </div>
    </li>
  );
}
