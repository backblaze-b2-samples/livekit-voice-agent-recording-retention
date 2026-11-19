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
