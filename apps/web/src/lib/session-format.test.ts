import { describe, expect, it } from "vitest";

import {
  formatBytes,
  formatDuration,
  formatWer,
  isSettledStatus,
  retentionLabel,
  statusVariant,
  todayUtc,
} from "./session-format";

describe("session-format", () => {
  it("knows which statuses are settled", () => {
    expect(isSettledStatus("recording")).toBe(false);
    expect(isSettledStatus("recorded")).toBe(false);
    expect(isSettledStatus("processed")).toBe(true);
    expect(isSettledStatus("failed")).toBe(true);
    expect(isSettledStatus("expired")).toBe(true);
  });

  it("describes retention, including hold", () => {
    expect(retentionLabel(null)).toBe("kept indefinitely");
    expect(retentionLabel(1)).toBe("kept 1 day");
    expect(retentionLabel(30)).toBe("kept 30 days");
  });

  it("formats durations, WER and sizes", () => {
    expect(formatDuration(21.4)).toBe("21s");
    expect(formatDuration(125)).toBe("2m 05s");
    expect(formatDuration(null)).toBe("-");
    expect(formatWer(0.125)).toBe("12.5%");
    expect(formatWer(undefined)).toBe("-");
    expect(formatBytes(48_213)).toBe("47.1 KB");
  });

  it("maps statuses to badge variants", () => {
    expect(statusVariant("failed")).toBe("destructive");
    expect(statusVariant("processed")).toBe("default");
    expect(statusVariant("recording")).toBe("secondary");
  });

  it("uses the UTC date", () => {
    expect(todayUtc(new Date("2026-11-19T23:30:00Z"))).toBe("2026-11-19");
  });
});
