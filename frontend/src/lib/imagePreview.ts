/** Uploaded-photo previews live only in this tab's memory, never in history/storage. */
const previews = new Map<string, { url: string; expires: number }>();
const MAX_PREVIEWS = 3;
const PREVIEW_LIFETIME = 60 * 60 * 1000;

export function forgetImagePreview(jobId: string) {
  const entry = previews.get(jobId);
  if (entry) URL.revokeObjectURL(entry.url);
  previews.delete(jobId);
}

function prune() {
  for (const [id, entry] of previews) {
    if (entry.expires <= Date.now()) forgetImagePreview(id);
  }
}

export function rememberImagePreview(jobId: string, mediaType: string, encoded: string) {
  try {
    prune();
    forgetImagePreview(jobId);
    while (previews.size >= MAX_PREVIEWS) forgetImagePreview(previews.keys().next().value!);
    const bytes = Uint8Array.from(atob(encoded), (character) => character.charCodeAt(0));
    const url = URL.createObjectURL(new Blob([bytes], { type: mediaType }));
    previews.set(jobId, { url, expires: Date.now() + PREVIEW_LIFETIME });
  } catch {
    // A preview failure must not discard a successfully accepted image job.
  }
}

export function getImagePreview(jobId: string | undefined): string | undefined {
  prune();
  return jobId ? previews.get(jobId)?.url : undefined;
}
