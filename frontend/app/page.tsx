"use client";

import { useCallback, useEffect, useRef, useState } from "react";
import DownloadForm from "@/components/DownloadForm";
import JobCard from "@/components/JobCard";
import { Features, Footer, Header, Hero } from "@/components/SiteChrome";
import {
  DownloadOptions,
  Job,
  SourceDescriptor,
  cancelJob,
  createJob,
  listSources,
  subscribeToJob,
} from "@/lib/api";

export default function Home() {
  const [sources, setSources] = useState<SourceDescriptor[]>([]);
  const [jobs, setJobs] = useState<Job[]>([]);
  const [loadError, setLoadError] = useState<string | null>(null);
  // One unsubscribe function per live job.
  const streams = useRef(new Map<string, () => void>());

  useEffect(() => {
    listSources()
      .then(setSources)
      .catch(() => setLoadError("Cannot reach the backend. Is the API running?"));
  }, []);

  // Tear every stream down on unmount so we do not leak EventSources.
  useEffect(() => {
    const open = streams.current;
    return () => {
      open.forEach((stop) => stop());
      open.clear();
    };
  }, []);

  const upsert = useCallback((job: Job) => {
    setJobs((current) => {
      const index = current.findIndex((item) => item.id === job.id);
      if (index === -1) return [job, ...current];
      const next = [...current];
      next[index] = job;
      return next;
    });
  }, []);

  const submit = useCallback(
    async (url: string, options: DownloadOptions) => {
      const job = await createJob(url, options);
      upsert(job);
      streams.current.set(job.id, subscribeToJob(job.id, upsert));
    },
    [upsert],
  );

  const cancel = useCallback(async (id: string) => {
    try {
      await cancelJob(id);
    } catch {
      /* already finished — the stream delivers the final state */
    }
  }, []);

  const dismiss = useCallback((id: string) => {
    streams.current.get(id)?.();
    streams.current.delete(id);
    setJobs((current) => current.filter((job) => job.id !== id));
  }, []);

  return (
    <>
      <div className="aurora" aria-hidden />
      <div className="grid-lines" aria-hidden />
      <Header />

      <main className="relative z-10 mx-auto w-full max-w-3xl px-5 pb-16">
        <Hero />

        {loadError ? (
          <p className="rounded-2xl border border-rose-500/30 bg-rose-500/10 px-4 py-3 text-sm text-rose-300">
            {loadError}
          </p>
        ) : (
          <DownloadForm sources={sources} onSubmit={submit} />
        )}

        {jobs.length > 0 && (
          <section className="mt-12">
            <h2 className="mb-3 text-xs font-medium uppercase tracking-[0.2em] text-muted">
              Downloads
            </h2>
            <ul className="flex flex-col gap-3">
              {jobs.map((job) => (
                <JobCard key={job.id} job={job} onCancel={cancel} onDismiss={dismiss} />
              ))}
            </ul>
          </section>
        )}

        <Features />
        <Footer />
      </main>
    </>
  );
}
