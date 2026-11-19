"use client";

import {
  useMutation,
  useQuery,
  useQueryClient,
  type QueryClient,
} from "@tanstack/react-query";
import {
  ApiError,
  createSession,
  deleteFile,
  deleteSession,
  getDownloadUrl,
  getFileDetail,
  getFiles,
  getHealth,
  getJoinToken,
  getPreviewUrl,
  getRetentionPolicy,
  getRetentionReports,
  getScripts,
  getSession,
  getSessions,
  getStats,
  reprocessSession,
  runRetention,
  updateSession,
  type SessionFilters,
} from "@/lib/api-client";
import type {
  ArchiveStats,
  FileMetadata,
  FileMetadataDetail,
  FileUrlResponse,
  RetentionReport,
  RetentionReportList,
  RetentionRunRequest,
  SessionCreate,
  SessionDetail,
  SessionList,
  SessionManifest,
  SessionUpdate,
} from "@livekit-voice-agent-recording-retention/shared";
import { isSettledStatus } from "@/lib/session-format";
import { qk } from "@/lib/generated/query-keys";

// Query keys are GENERATED from the API contract (`pnpm gen:api`) and their
// hierarchy is declared in `scripts/gen/api-gen.config.json`, so invalidating
// a parent key still reaches its children and no hook can invent a key the API
// cannot answer. Re-exported here because this module is the data layer's
// public surface: components and tests import `qk` from `@/lib/queries`.
//
// The caching policy below — staleTime, refetchInterval, retry, `enabled`
// gating, the query-vs-mutation choice, and the cache surgery in
// `dropDeletedFileFromCache` — is hand-written on purpose and is never
// generated.
export { qk };

export type Health = Awaited<ReturnType<typeof getHealth>>;

/**
 * Gate a query on something being open/visible. Deliberately the only option we
 * expose, so callers can't drift the caching policy per call site — the ⌘K
 * palette reuses `useFiles`' key (and therefore its cache) instead of fetching
 * its own private, smaller list.
 */
export interface QueryGate {
  enabled?: boolean;
}

export function useFiles(prefix = "", limit = 100, { enabled = true }: QueryGate = {}) {
  return useQuery<FileMetadata[], ApiError>({
    queryKey: qk.files(prefix, limit),
    queryFn: () => getFiles(prefix, limit),
    enabled,
  });
}

// Presigned preview URL — only fetched when `enabled` is true (e.g., when
// the dialog opens for a specific file). Kept short-lived (60s) because
// the URL itself has a presigned expiry and is cheap to regenerate.
export function usePreviewUrl(key: string | undefined, enabled: boolean) {
  return useQuery({
    queryKey: qk.preview(key ?? ""),
    queryFn: () => getPreviewUrl(key as string),
    enabled: enabled && !!key,
    staleTime: 60_000,
  });
}

// Rich metadata for an already-stored file. The server recomputes it on demand
// (a full object download), so it's only fetched when `enabled` — i.e. the
// preview dialog is open AND the user expands "Detailed metadata". Kept
// short-lived like the preview URL; cheap correctness under key overwrites.
export function useFileDetail(key: string | undefined, enabled: boolean) {
  return useQuery<FileMetadataDetail, ApiError>({
    queryKey: qk.detail(key ?? ""),
    queryFn: () => getFileDetail(key as string),
    enabled: enabled && !!key,
    staleTime: 60_000,
  });
}

// Health poll for the top-of-app B2 banner. `retry: false` and letting a
// failed fetch leave `data` undefined keeps a down API silent (the
// per-component ErrorState covers that); the banner only reacts to an up API
// reporting b2_connected: false. Polls every 60s and on window focus.
export function useHealth() {
  return useQuery<Health>({
    queryKey: qk.health(),
    queryFn: getHealth,
    refetchInterval: 60_000,
    staleTime: 30_000,
    retry: false,
  });
}

/**
 * Drop a deleted object from every cached file list, plus its own cached
 * preview/detail entries.
 *
 * Invalidation alone is not enough: the refetch re-lists the whole bucket and
 * took 5-6s in practice, so the success toast fired while the row was still
 * listed — and using that stale row's Preview 404'd. Editing the cache makes
 * the row disappear with the toast; the invalidation that follows still
 * reconciles against the server.
 *
 * Exported for tests — the mutation below is its only production caller.
 */
export function dropDeletedFileFromCache(qc: QueryClient, fileKey: string) {
  qc.setQueriesData<FileMetadata[]>(
    // Partial key: matches qk.files(prefix, limit) for every prefix/limit.
    { queryKey: [...qk.all, "files"] },
    (previous) =>
      previous ? previous.filter((file) => file.key !== fileKey) : previous,
  );
  // A presigned URL for a deleted key can only 404 now.
  qc.removeQueries({ queryKey: qk.preview(fileKey) });
  qc.removeQueries({ queryKey: qk.detail(fileKey) });
}

/**
 * Fetch a download URL for one file.
 *
 * A mutation, not a query: each call mints a fresh presigned URL that must
 * never be cached or replayed. Being a mutation is also
 * what gives the UI an honest pending state — the old code awaited the presign
 * inside a plain click handler, so a slow round trip left the screen completely
 * unchanged and a user could not tell a working download from a dead button.
 *
 * The caller performs the navigation (see `lib/browser-download.ts`) and gets
 * `isPending` / `variables` for the pending row.
 */
export function useDownloadUrl() {
  return useMutation<FileUrlResponse, ApiError, FileMetadata>({
    mutationFn: (file) => getDownloadUrl(file.key),
  });
}

export function useDeleteFile() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (fileKey: string) => deleteFile(fileKey),
    onSuccess: (_data, fileKey) => {
      // Remove the row immediately, then reconcile everything (lists, stats,
      // activity) against the server in the background.
      dropDeletedFileFromCache(qc, fileKey);
      qc.invalidateQueries({ queryKey: qk.all });
    },
  });
}

// --- Session archive ------------------------------------------------------

/**
 * Per-session cache key. The generated `qk.session()` carries no path
 * parameter (the generator derives keys from query parameters only), so the
 * session id is appended here; invalidating `qk.session()` still reaches every
 * session's entry.
 */
export function sessionKey(sessionId: string) {
  return [...qk.session(), sessionId] as const;
}

// Dashboard figures. Polls while the tab is open so a session recorded from
// the CLI (`make demo`) shows up without a manual refresh.
export function useArchiveStats() {
  return useQuery<ArchiveStats, ApiError>({
    queryKey: qk.stats(),
    queryFn: getStats,
    refetchInterval: 15_000,
  });
}

export function useScripts() {
  return useQuery({
    queryKey: qk.scripts(),
    queryFn: getScripts,
    staleTime: 5 * 60_000,
  });
}

export function useSessions(filters: SessionFilters = {}) {
  return useQuery<SessionList, ApiError>({
    queryKey: qk.sessions(
      filters.date,
      filters.session_class,
      filters.status,
      filters.cursor,
      filters.limit,
    ),
    queryFn: () => getSessions(filters),
    // A recording session becomes processed on its own; keep the table honest.
    refetchInterval: (query) =>
      query.state.data?.items.some((s) => !isSettledStatus(s.status)) ? 5_000 : false,
  });
}

/**
 * One session's manifest, derivatives and a fresh presigned playback URL.
 * Polls every 3s until the session settles (processed, failed or expired),
 * because the webhook and post-processing update it in the background.
 */
export function useSession(sessionId: string | undefined) {
  return useQuery<SessionDetail, ApiError>({
    queryKey: sessionKey(sessionId ?? ""),
    queryFn: () => getSession(sessionId as string),
    enabled: !!sessionId,
    refetchInterval: (query) => {
      const status = query.state.data?.manifest.status;
      return status && isSettledStatus(status) ? false : 3_000;
    },
  });
}

function invalidateArchive(qc: QueryClient) {
  qc.invalidateQueries({ queryKey: [...qk.all, "sessions"] });
  qc.invalidateQueries({ queryKey: qk.stats() });
  // The bucket explorer lists the same objects.
  qc.invalidateQueries({ queryKey: [...qk.all, "files"] });
}

export function useCreateSession() {
  const qc = useQueryClient();
  return useMutation<SessionManifest, ApiError, SessionCreate>({
    mutationFn: createSession,
    onSuccess: () => invalidateArchive(qc),
  });
}

export function useUpdateSession(sessionId: string) {
  const qc = useQueryClient();
  return useMutation<SessionManifest, ApiError, SessionUpdate>({
    mutationFn: (update) => updateSession(sessionId, update),
    onSuccess: () => invalidateArchive(qc),
  });
}

export function useDeleteSession() {
  const qc = useQueryClient();
  return useMutation<void, ApiError, string>({
    mutationFn: deleteSession,
    onSuccess: (_data, sessionId) => {
      qc.removeQueries({ queryKey: sessionKey(sessionId) });
      invalidateArchive(qc);
    },
  });
}

/**
 * Show a reprocessed session as processing (`recorded`, error cleared) the
 * moment Reprocess is clicked, mirroring what the API does, instead of leaving
 * the old Failed badge and error up until the next poll.
 */
export function markSessionReprocessing(qc: QueryClient, sessionId: string) {
  qc.setQueryData<SessionDetail>(sessionKey(sessionId), (current) =>
    current
      ? { ...current, manifest: { ...current.manifest, status: "recorded", error: null } }
      : current,
  );
}

export function useReprocessSession(sessionId: string) {
  const qc = useQueryClient();
  return useMutation<SessionManifest, ApiError, void, { previous?: SessionDetail }>({
    mutationFn: () => reprocessSession(sessionId),
    onMutate: async () => {
      await qc.cancelQueries({ queryKey: sessionKey(sessionId) });
      const previous = qc.getQueryData<SessionDetail>(sessionKey(sessionId));
      markSessionReprocessing(qc, sessionId);
      return { previous };
    },
    onError: (_error, _vars, context) => {
      if (context?.previous) qc.setQueryData(sessionKey(sessionId), context.previous);
    },
    onSuccess: () => invalidateArchive(qc),
  });
}

// A join token is single-use and short-lived: a mutation, never cached.
export function useJoinToken(sessionId: string) {
  return useMutation({
    mutationFn: (identity: string) => getJoinToken(sessionId, identity),
  });
}

export function useRetentionPolicy() {
  return useQuery({
    queryKey: qk.retentionPolicy(),
    queryFn: getRetentionPolicy,
    staleTime: 5 * 60_000,
  });
}

export function useRetentionReports() {
  return useQuery({
    queryKey: qk.retentionReports(),
    queryFn: getRetentionReports,
  });
}

/**
 * Put an applied run's report into the cached "Reports in B2" list right away,
 * replacing the same day's row, so the table agrees with the success toast
 * instead of showing the previous report until the refetch (a B2 list plus one
 * read per report) returns. Dry runs write nothing and change nothing.
 */
export function recordAppliedReport(qc: QueryClient, report: RetentionReport) {
  if (report.dry_run || !report.report_key) return;
  const row = {
    date: report.date,
    key: report.report_key,
    kept_total: report.kept_total,
    removed_total: report.removed_total,
    generated_at: report.generated_at,
  };
  qc.setQueryData<RetentionReportList>(qk.retentionReports(), (current) => {
    const others = (current?.items ?? []).filter((r) => r.key !== row.key);
    return { items: [row, ...others].sort((a, b) => b.date.localeCompare(a.date)) };
  });
}

export function useRunRetention() {
  const qc = useQueryClient();
  return useMutation<RetentionReport, ApiError, RetentionRunRequest>({
    mutationFn: runRetention,
    onSuccess: (report) => {
      if (!report.dry_run) {
        recordAppliedReport(qc, report);
        qc.invalidateQueries({ queryKey: [...qk.all, "retention"] });
        invalidateArchive(qc);
      }
    },
  });
}
