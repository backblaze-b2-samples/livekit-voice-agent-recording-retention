/**
 * Display helpers for the session archive. Pure functions, unit-tested.
 */

export const SESSION_CLASSES = ["debug", "standard", "training", "hold"] as const;
export type SessionClassName = (typeof SESSION_CLASSES)[number];

export const SESSION_STATUSES = [
  "recording",
  "recorded",
  "processed",
  "failed",
  "expired",
] as const;

export const SESSION_MODES = ["scripted", "interactive"] as const;

/** Statuses that change no further on their own (polling can stop). */
export function isSettledStatus(status: string): boolean {
  return status === "processed" || status === "failed" || status === "expired";
}

export function retentionLabel(retainDays: number | null | undefined): string {
  if (retainDays === null || retainDays === undefined) return "kept indefinitely";
  if (retainDays === 1) return "kept 1 day";
  return `kept ${retainDays} days`;
}

export function formatDuration(seconds: number | null | undefined): string {
  if (seconds === null || seconds === undefined) return "-";
  const total = Math.round(seconds);
  const minutes = Math.floor(total / 60);
  const rest = total % 60;
  return minutes > 0 ? `${minutes}m ${rest.toString().padStart(2, "0")}s` : `${rest}s`;
}

export function formatMinutes(seconds: number): string {
  return `${(seconds / 60).toFixed(1)} min`;
}

export function formatWer(wer: number | null | undefined): string {
  if (wer === null || wer === undefined) return "-";
  return `${(wer * 100).toFixed(1)}%`;
}

export function formatBytes(bytes: number | null | undefined): string {
  if (bytes === null || bytes === undefined) return "-";
  const units = ["B", "KB", "MB", "GB", "TB"];
  let value = bytes;
  let unit = 0;
  while (Math.abs(value) >= 1024 && unit < units.length - 1) {
    value /= 1024;
    unit += 1;
  }
  return `${value.toFixed(1)} ${units[unit]}`;
}

export function formatDateTime(value: string | null | undefined): string {
  if (!value) return "-";
  const date = new Date(value);
  return Number.isNaN(date.getTime())
    ? "-"
    : date.toISOString().replace("T", " ").slice(0, 16) + " UTC";
}

/** Badge variant per status, using the kit's Badge variants. */
export function statusVariant(
  status: string,
): "default" | "secondary" | "destructive" | "outline" {
  switch (status) {
    case "processed":
      return "default";
    case "failed":
      return "destructive";
    case "expired":
      return "outline";
    default:
      return "secondary";
  }
}

/** Today's date as YYYY-MM-DD in UTC, the unit retention runs in. */
export function todayUtc(now: Date = new Date()): string {
  return now.toISOString().slice(0, 10);
}

export interface SessionProgress {
  stage: string;
  detail: string;
}

/** What is running right now for a session that has not settled, or null when it has. */
export function sessionProgress(status: string, mode: string): SessionProgress | null {
  if (status === "recording") {
    return mode === "interactive"
      ? {
          stage: "Recording: the room is live",
          detail: "Join below. Egress writes the recording to B2 when the room closes.",
        }
      : {
          stage: "Recording: the agent is speaking the script",
          detail: "Egress writes the recording to B2 when the room closes, usually within a minute.",
        };
  }
  if (status === "recorded") {
    return {
      stage: "Processing: checksum, transcription and evaluation",
      detail: "The recording is in B2. Whisper transcribes it and the script is scored; this page updates on its own.",
    };
  }
  return null;
}

/** Agent join, Egress upload and the webhook, on top of the script's spoken length. */
export const RECORDING_OVERHEAD_S = 15;
/** Model load and the checksum pass, on top of roughly real-time transcription. */
export const PROCESSING_OVERHEAD_S = 5;
/** Used when neither the script nor the recording gives a length. */
const FALLBACK_AUDIO_S = 30;

export interface SessionProgressValue {
  step: number;
  steps: number;
  label: string;
  /** Overall percent, 0-99: recording fills the first half, processing the second. */
  percent: number;
}

/**
 * A determinate, estimated overall progress for a session that has not
 * settled: recording is step 1 of 2 (elapsed vs the script's expected length),
 * processing step 2 of 2 (elapsed vs the recording's length). Each step stops
 * at 95% of its half until the real status moves on, so it never claims done.
 * Null for a live interactive room (a person decides its length) and for a
 * settled session.
 */
export function sessionProgressValue({
  status,
  mode,
  elapsedS,
  scriptDurationS,
  recordingDurationS,
}: {
  status: string;
  mode: string;
  elapsedS: number;
  scriptDurationS?: number | null;
  recordingDurationS?: number | null;
}): SessionProgressValue | null {
  const fraction = (expected: number) => Math.min(Math.max(elapsedS, 0) / expected, 0.95);
  if (status === "recording" && mode === "scripted") {
    const expected = (scriptDurationS ?? FALLBACK_AUDIO_S) + RECORDING_OVERHEAD_S;
    return { step: 1, steps: 2, label: "Step 1 of 2: recording", percent: Math.round(fraction(expected) * 50) };
  }
  if (status === "recorded") {
    const expected = (recordingDurationS ?? scriptDurationS ?? FALLBACK_AUDIO_S) + PROCESSING_OVERHEAD_S;
    return { step: 2, steps: 2, label: "Step 2 of 2: processing", percent: 50 + Math.round(fraction(expected) * 50) };
  }
  return null;
}

export interface FailureGuidance {
  title: string;
  action: string;
}

/** A human-readable reading of a failed session's raw error, plus what to do next. */
export function failureGuidance(error: string | null | undefined): FailureGuidance {
  const raw = error ?? "";
  if (raw.startsWith("post-processing failed")) {
    return {
      title: "The recording is safe in B2, but transcription or evaluation failed.",
      action:
        "Check the api logs (docker compose logs api) for the cause, fix it, then click Reprocess to run checksum, transcription and evaluation again.",
    };
  }
  if (raw.startsWith("LiveKit start failed")) {
    return {
      title: "The session could not start: LiveKit refused the room, agent or Egress.",
      action:
        "Check that the Compose stack is up (docker compose ps) and LiveKit is reachable, then start a new session.",
    };
  }
  return {
    title: "The recording did not complete, so there is nothing to process.",
    action:
      "Check the egress logs (docker compose logs egress) and the B2 credentials, then start a new session.",
  };
}
