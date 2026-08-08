"use client";

import { SourceDescriptor } from "@/lib/api";

/** Per-platform copy. Anything not listed falls back to the generic entry. */
export const PLATFORM_COPY: Record<
  string,
  { icon: string; blurb: string; placeholder: string }
> = {
  youtube: {
    icon: "▶",
    blurb: "Videos, Shorts, playlists, music",
    placeholder: "https://youtube.com/watch?v=…",
  },
  instagram: {
    icon: "◎",
    blurb: "Posts, reels and carousels",
    placeholder: "https://instagram.com/p/…",
  },
  twitter: {
    icon: "𝕏",
    blurb: "Images and video in a tweet",
    placeholder: "https://x.com/user/status/…",
  },
  pinterest: {
    icon: "◈",
    blurb: "A single pin",
    placeholder: "https://pinterest.com/pin/…",
  },
  generic: {
    icon: "∗",
    blurb: "A thousand other sites, via yt-dlp",
    placeholder: "https://…",
  },
};

export const copyFor = (name: string) => PLATFORM_COPY[name] ?? PLATFORM_COPY.generic;

interface Props {
  sources: SourceDescriptor[];
  selected: SourceDescriptor | null;
  onSelect: (source: SourceDescriptor) => void;
}

export default function PlatformPicker({ sources, selected, onSelect }: Props) {
  if (sources.length === 0) {
    return (
      <div className="grid gap-2 sm:grid-cols-3">
        {[0, 1, 2, 3, 4].map((key) => (
          <div key={key} className="h-[4.5rem] animate-pulse rounded-xl bg-panel/60" />
        ))}
      </div>
    );
  }

  return (
    <fieldset>
      <legend className="mb-3 text-xs font-medium uppercase tracking-[0.2em] text-muted">
        1 · Where from?
      </legend>
      <div className="grid gap-2 sm:grid-cols-3">
        {sources.map((source) => {
          const copy = copyFor(source.name);
          const active = selected?.name === source.name;
          return (
            <button
              key={source.name}
              type="button"
              onClick={() => onSelect(source)}
              aria-pressed={active}
              // The label lives in nested spans, so name the control explicitly.
              aria-label={
                source.configured
                  ? `${source.label} — ${copy.blurb}`
                  : `${source.label} — not configured on this instance`
              }
              className={`group flex items-start gap-3 rounded-xl border p-3 text-left transition ${
                active
                  ? "border-accent bg-accent/10"
                  : "border-edge bg-panel/50 hover:border-edge-bright"
              }`}
            >
              <span
                aria-hidden
                className={`grid size-8 shrink-0 place-items-center rounded-lg text-sm ${
                  active ? "bg-accent text-white" : "bg-white/5 text-muted"
                }`}
              >
                {copy.icon}
              </span>
              <span className="min-w-0">
                <span className="flex items-center gap-1.5">
                  <span className="truncate text-sm font-medium text-white">{source.label}</span>
                  {!source.configured && (
                    <span
                      title="Not configured on this instance"
                      className="size-1.5 shrink-0 rounded-full bg-amber-400"
                    />
                  )}
                </span>
                <span className="mt-0.5 block text-xs leading-snug text-muted">{copy.blurb}</span>
              </span>
            </button>
          );
        })}
      </div>
    </fieldset>
  );
}
