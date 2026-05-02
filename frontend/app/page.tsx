"use client";

import { useCallback, useEffect, useState } from "react";
import DownloadForm from "@/components/DownloadForm";
import { DownloadOptions, SourceDescriptor, createJob, listSources } from "@/lib/api";

export default function Home() {
  const [sources, setSources] = useState<SourceDescriptor[]>([]);
  const [loadError, setLoadError] = useState<string | null>(null);

  useEffect(() => {
    listSources()
      .then(setSources)
      .catch(() => setLoadError("Cannot reach the backend. Is the API running?"));
  }, []);

  const submit = useCallback(async (url: string, options: DownloadOptions) => {
    await createJob(url, options);
  }, []);

  return (
    <main className="mx-auto w-full max-w-3xl px-4 py-16">
      <h1 className="mb-6 text-3xl font-semibold tracking-tight">vid-downloadr</h1>
      {loadError ? (
        <p className="rounded-xl border border-rose-500/30 bg-rose-500/10 px-4 py-3 text-sm text-rose-300">
          {loadError}
        </p>
      ) : (
        <DownloadForm sources={sources} onSubmit={submit} />
      )}
    </main>
  );
}
