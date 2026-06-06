"use client";

const FEATURES = [
  {
    title: "One paste, any platform",
    body: "YouTube, Instagram, X, Pinterest — plus every other site yt-dlp recognises, through a single catch-all source.",
  },
  {
    title: "Live progress, not a spinner",
    body: "Server-sent events stream percentage, speed and stage straight from the download thread, with polling as a fallback.",
  },
  {
    title: "Nothing kept",
    body: "Files live in a temp directory and are deleted on a timer. No accounts, no history, no analytics.",
  },
  {
    title: "One file per new site",
    body: "Sources are plugins with a shared interface. Subclass Source, register it, and the UI adapts to what it advertises.",
  },
];

export function Header() {
  return (
    <header className="sticky top-0 z-20 border-b border-edge/60 bg-surface/70 backdrop-blur-xl">
      <div className="mx-auto flex h-14 w-full max-w-5xl items-center gap-3 px-5">
        <div className="flex items-center gap-2">
          <span
            aria-hidden
            className="grid size-7 place-items-center rounded-lg bg-gradient-to-br from-accent to-fuchsia-500 text-sm font-bold text-white"
          >
            ↓
          </span>
          <span className="text-sm font-semibold tracking-tight">vid-downloadr</span>
        </div>
        <nav className="ml-auto flex items-center gap-5 text-sm text-muted">
          <a href="#how" className="hidden transition hover:text-white sm:block">
            How it works
          </a>
          <a href="/api/docs" className="hidden transition hover:text-white sm:block">
            API
          </a>
          <a
            href="https://github.com/"
            target="_blank"
            rel="noreferrer noopener"
            className="rounded-lg border border-edge-bright px-3 py-1.5 text-xs text-white/80 transition hover:border-accent hover:text-white"
          >
            GitHub
          </a>
        </nav>
      </div>
    </header>
  );
}

export function Hero() {
  return (
    <section className="pb-8 pt-14 text-center sm:pt-20">
      <span className="inline-flex items-center gap-2 rounded-full border border-edge-bright bg-panel/60 px-3 py-1 text-xs text-muted">
        <span className="size-1.5 rounded-full bg-emerald-400" />
        Open source · self-hostable · no account
      </span>
      <h1 className="gradient-text mx-auto mt-5 max-w-2xl text-balance text-4xl font-semibold leading-[1.1] tracking-tight sm:text-6xl">
        Download media from anywhere
      </h1>
      <p className="mx-auto mt-4 max-w-xl text-pretty text-base leading-relaxed text-muted">
        Paste a link, pick a format, get the file. Runs entirely on your own server — the media
        never touches a third-party service.
      </p>
    </section>
  );
}

export function Features() {
  return (
    <section id="how" className="mt-20 scroll-mt-20">
      <h2 className="text-center text-xs font-medium uppercase tracking-[0.2em] text-muted">
        How it works
      </h2>
      <div className="mt-6 grid gap-3 sm:grid-cols-2">
        {FEATURES.map((feature) => (
          <div
            key={feature.title}
            className="rounded-2xl border border-edge bg-panel/50 p-5 transition hover:border-edge-bright"
          >
            <h3 className="text-sm font-medium text-white">{feature.title}</h3>
            <p className="mt-2 text-sm leading-relaxed text-muted">{feature.body}</p>
          </div>
        ))}
      </div>
    </section>
  );
}

export function Footer() {
  return (
    <footer className="mt-20 border-t border-edge pt-8 text-xs leading-relaxed text-white/30">
      <p>
        Files are held only long enough for you to download them, then deleted. Download what you
        have the right to download, and respect each platform&apos;s terms and the rights of
        creators.
      </p>
      <p className="mt-3">MIT licensed. Self-host it, fork it, send patches.</p>
    </footer>
  );
}
