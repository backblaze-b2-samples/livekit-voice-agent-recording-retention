"use client";

import { useEffect, useState } from "react";
import { AlertTriangle, Loader2 } from "lucide-react";

import { Progress } from "@/components/ui/progress";
import { useScripts } from "@/lib/queries";
import { failureGuidance, sessionProgress, sessionProgressValue } from "@/lib/session-format";

/**
 * Seconds since the current stage began, ticking once a second. Recording
 * counts from the session's creation; processing from the moment this page saw
 * the session enter it (the manifest keeps no processing start, and a
 * Reprocess re-enters it long after the webhook).
 */
function useStageElapsed(status: string, createdAt: string): number {
  const [clock, setClock] = useState(() => ({ status, since: Date.now(), now: Date.now() }));
  useEffect(() => {
    const timer = setInterval(() => {
      const now = Date.now();
      setClock((prev) => (prev.status === status ? { ...prev, now } : { status, since: now, now }));
    }, 1_000);
    return () => clearInterval(timer);
  }, [status]);
  // Until the first tick after a status change, the new stage has just begun.
  const since = status === "recording" ? Date.parse(createdAt) : clock.status === status ? clock.since : clock.now;
  return Number.isNaN(since) ? 0 : Math.max(0, (clock.now - since) / 1_000);
}

function StageProgress({
  status,
  mode,
  createdAt,
  scriptId,
  recordingDurationS,
}: {
  status: string;
  mode: string;
  createdAt: string;
  scriptId: string;
  recordingDurationS: number | null | undefined;
}) {
  const scripts = useScripts();
  const elapsedS = useStageElapsed(status, createdAt);
  const value = sessionProgressValue({
    status,
    mode,
    elapsedS,
    scriptDurationS: scripts.data?.items.find((s) => s.id === scriptId)?.expected_duration_s,
    recordingDurationS,
  });
  if (!value) return null;
  return (
    <div className="mt-2 space-y-1">
      {/* The kit's Progress draws the bar but does not forward `value` to the
          Radix root, so the progressbar semantics live on this wrapper. */}
      <div
        role="progressbar"
        aria-label="Session progress"
        aria-valuemin={0}
        aria-valuemax={100}
        aria-valuenow={value.percent}
        aria-valuetext={`${value.label}, about ${value.percent}%`}
      >
        <Progress value={value.percent} aria-hidden="true" />
      </div>
      <p className="text-xs text-muted-foreground">
        {value.label} · about {value.percent}% (estimated)
      </p>
    </div>
  );
}

/**
 * The live state of a session above its detail cards: a spinner with the
 * current stage and an estimated step x/2 progress bar while it records or
 * processes, an explained failure with the
 * next step (raw error kept under "Details"), nothing once it has settled.
 */
export function SessionStateBanner({
  status,
  mode,
  error,
  createdAt,
  scriptId,
  recordingDurationS,
}: {
  status: string;
  mode: string;
  error: string | null | undefined;
  createdAt: string;
  scriptId: string;
  recordingDurationS: number | null | undefined;
}) {
  const progress = sessionProgress(status, mode);
  if (progress) {
    return (
      <div
        role="status"
        aria-live="polite"
        aria-busy="true"
        className="rounded-md border border-border bg-muted/40 p-3"
      >
        <p className="flex items-center gap-2 text-sm font-medium text-foreground">
          <Loader2 aria-hidden="true" className="h-4 w-4 animate-spin" />
          {progress.stage}
        </p>
        <p className="mt-1 text-xs text-muted-foreground">{progress.detail}</p>
        <StageProgress
          status={status}
          mode={mode}
          createdAt={createdAt}
          scriptId={scriptId}
          recordingDurationS={recordingDurationS}
        />
      </div>
    );
  }
  if (status !== "failed") return null;

  const guidance = failureGuidance(error);
  return (
    <div role="alert" className="rounded-md border border-destructive/40 p-3 text-sm">
      <p className="flex items-center gap-2 font-medium text-destructive">
        <AlertTriangle aria-hidden="true" className="h-4 w-4" />
        {guidance.title}
      </p>
      <p className="mt-1 text-muted-foreground">{guidance.action}</p>
      {error && (
        <details className="mt-2">
          <summary className="cursor-pointer text-xs text-muted-foreground">Details</summary>
          <pre className="mt-1 whitespace-pre-wrap break-all font-mono text-xs">{error}</pre>
        </details>
      )}
    </div>
  );
}
