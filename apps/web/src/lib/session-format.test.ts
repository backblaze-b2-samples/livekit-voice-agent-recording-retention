import { describe, expect, it } from "vitest";

import {
  failureGuidance,
  sessionProgress,
  sessionProgressValue,
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

  it("describes the running stage until a session settles", () => {
    expect(sessionProgress("recording", "scripted")?.stage).toMatch(/^Recording/);
    expect(sessionProgress("recording", "interactive")?.stage).toMatch(/room is live/);
    expect(sessionProgress("recorded", "scripted")?.stage).toMatch(/^Processing/);
    for (const status of ["processed", "failed", "expired"]) {
      expect(sessionProgress(status, "scripted")).toBeNull();
    }
  });

  it("gives a determinate overall progress that advances and never claims done", () => {
    // Scripted recording: step 1 of 2, elapsed vs the script's estimate plus overhead.
    const start = sessionProgressValue({ status: "recording", mode: "scripted", elapsedS: 0, scriptDurationS: 20 });
    const mid = sessionProgressValue({ status: "recording", mode: "scripted", elapsedS: 15, scriptDurationS: 20 });
    const late = sessionProgressValue({ status: "recording", mode: "scripted", elapsedS: 600, scriptDurationS: 20 });
    expect(start).toMatchObject({ step: 1, steps: 2, percent: 0 });
    expect(mid!.percent).toBeGreaterThan(start!.percent);
    expect(late!.percent).toBeLessThan(50);
    expect(late!.percent).toBeGreaterThan(mid!.percent);

    // Processing: step 2 of 2, from 50% upward, capped below 100%.
    const p0 = sessionProgressValue({ status: "recorded", mode: "scripted", elapsedS: 0, recordingDurationS: 23 });
    const p1 = sessionProgressValue({ status: "recorded", mode: "scripted", elapsedS: 12, recordingDurationS: 23 });
    const pLate = sessionProgressValue({ status: "recorded", mode: "scripted", elapsedS: 900, recordingDurationS: 23 });
    expect(p0).toMatchObject({ step: 2, steps: 2, percent: 50 });
    expect(p1!.percent).toBeGreaterThan(50);
    expect(pLate!.percent).toBeLessThan(100);
    expect(p1!.label).toMatch(/Step 2 of 2/);
  });

  it("has no determinate progress for a live interactive room or a settled session", () => {
    expect(sessionProgressValue({ status: "recording", mode: "interactive", elapsedS: 5 })).toBeNull();
    for (const status of ["processed", "failed", "expired"]) {
      expect(sessionProgressValue({ status, mode: "scripted", elapsedS: 5 })).toBeNull();
    }
  });

  it("turns a raw failure into a readable reason and a next step", () => {
    const post = failureGuidance("post-processing failed: open() got an unexpected keyword");
    expect(post.title).toMatch(/safe in B2/);
    expect(post.action).toMatch(/Reprocess/);
    expect(failureGuidance("LiveKit start failed: boom").action).toMatch(/new session/);
    expect(failureGuidance("Egress ended with EGRESS_FAILED").title).toMatch(/did not complete/);
    expect(failureGuidance(null).action).toMatch(/new session/);
  });

  it("uses the UTC date", () => {
    expect(todayUtc(new Date("2026-11-19T23:30:00Z"))).toBe("2026-11-19");
  });
});
