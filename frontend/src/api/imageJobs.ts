import { useMutation, useQuery } from "@tanstack/react-query";
import { useState } from "react";

import { api, ApiError, unwrap, type Schemas } from "./client";

const STORAGE_KEY = "cookish.pending-image-job";
type PendingJob = { jobId: string; kind: Schemas["ImageKind"] };

function restore(): PendingJob | null {
  try {
    const value: unknown = JSON.parse(sessionStorage.getItem(STORAGE_KEY) ?? "null");
    if (value && typeof value === "object" && "jobId" in value && "kind" in value
      && typeof value.jobId === "string" && /^[0-9a-f-]{36}$/.test(value.jobId)
      && (value.kind === "receipt" || value.kind === "photo")) {
      return { jobId: value.jobId, kind: value.kind };
    }
  } catch { /* Storage can be unavailable in private browsing. */ }
  return null;
}

function remember(job: PendingJob | null) {
  try {
    if (job) sessionStorage.setItem(STORAGE_KEY, JSON.stringify(job));
    else sessionStorage.removeItem(STORAGE_KEY);
  } catch { /* In-memory polling still works when browser storage is disabled. */ }
}

/** Submission and polling are short requests; the worker owns the model deadline. */
export function useImageJobs() {
  const [pending, setPending] = useState<PendingJob | null>(restore);
  // Always re-authorize restored jobs. A previous signed-in user's cached result must
  // never be displayed while a fresh ownership check is still in flight.
  const [readerId] = useState(() => crypto.randomUUID());
  const submission = useMutation({
    mutationFn: async ({ body, key }: { body: Schemas["ParseImageRequest"]; key: string }) =>
      unwrap(await api.POST("/ai/image-jobs", {
        body, params: { header: { "Idempotency-Key": key } },
      })),
    // React Query repeats the same variables/key if the acknowledgement was lost.
    retry: (count, error) => count < 1 && !(error instanceof ApiError && error.code !== "UPSTREAM_UNAVAILABLE"),
    onSuccess: (job) => {
      const next = { jobId: job.job_id, kind: job.kind };
      remember(next);
      setPending(next);
    },
  });
  const status = useQuery({
    queryKey: ["image-job", pending?.jobId, readerId],
    gcTime: 0,
    enabled: pending !== null,
    queryFn: async ({ signal }) => unwrap(await api.GET("/ai/image-jobs/{job_id}", {
      params: { path: { job_id: pending!.jobId } }, signal,
    })),
    refetchInterval: (query) => {
      const job = query.state.data;
      if (query.state.status === "error" || job?.status === "completed" || job?.status === "failed") return false;
      return (job?.poll_after_seconds ?? 2) * 1000;
    },
    retry: (count, error) => count < 2 && !(error instanceof ApiError
      && ["NOT_FOUND", "UNAUTHENTICATED", "FORBIDDEN"].includes(error.code)),
  });

  function clear() {
    remember(null);
    setPending(null);
    submission.reset();
  }

  const job = status.data;
  const failed = job?.status === "failed";
  const active = submission.isPending || (pending !== null && !failed && job?.status !== "completed");
  return {
    job,
    pending,
    active,
    error: submission.error ?? status.error ?? (failed ? new Error(job.error?.message ?? "Image processing failed") : null),
    progress: submission.isPending ? "Uploading image…" : job?.status === "processing"
      ? "Reading your image…" : "Your image is queued…",
    submit: (body: Schemas["ParseImageRequest"]) =>
      submission.mutateAsync({ body, key: crypto.randomUUID() }),
    refresh: () => void status.refetch(),
    clear,
  };
}
