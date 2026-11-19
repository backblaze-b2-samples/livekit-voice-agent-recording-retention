import { QueryClient } from "@tanstack/react-query";
import { beforeEach, describe, expect, it } from "vitest";
import {
  dropDeletedFileFromCache,
  markSessionReprocessing,
  qk,
  recordAppliedReport,
  sessionKey,
} from "@/lib/queries";
import type {
  FileMetadata,
  RetentionReport,
  RetentionReportList,
} from "@livekit-voice-agent-recording-retention/shared";

function file(key: string): FileMetadata {
  return {
    key,
    filename: key.split("/").pop() ?? key,
    folder: "uploads/",
    size_bytes: 10,
    size_human: "10 B",
    content_type: "text/plain",
    uploaded_at: "2026-07-28T00:00:00Z",
    url: null,
  };
}

describe("dropDeletedFileFromCache", () => {
  let qc: QueryClient;

  beforeEach(() => {
    qc = new QueryClient();
  });

  it("removes the deleted row from the default list", () => {
    qc.setQueryData(qk.files(), [file("uploads/a.txt"), file("uploads/b.txt")]);

    dropDeletedFileFromCache(qc, "uploads/a.txt");

    expect(qc.getQueryData<FileMetadata[]>(qk.files())).toEqual([
      file("uploads/b.txt"),
    ]);
  });

  it("removes it from every cached prefix/limit variant", () => {
    qc.setQueryData(qk.files(), [file("uploads/a.txt")]);
    qc.setQueryData(qk.files("uploads/", 100), [file("uploads/a.txt")]);
    qc.setQueryData(qk.files("", 25), [file("uploads/a.txt")]);

    dropDeletedFileFromCache(qc, "uploads/a.txt");

    expect(qc.getQueryData<FileMetadata[]>(qk.files())).toEqual([]);
    expect(qc.getQueryData<FileMetadata[]>(qk.files("uploads/", 100))).toEqual(
      [],
    );
    expect(qc.getQueryData<FileMetadata[]>(qk.files("", 25))).toEqual([]);
  });

  it("evicts the deleted key's presigned URL and detail so Preview can't 404", () => {
    qc.setQueryData(qk.preview("uploads/a.txt"), { url: "https://signed" });
    qc.setQueryData(qk.detail("uploads/a.txt"), { md5: "abc" });

    dropDeletedFileFromCache(qc, "uploads/a.txt");

    expect(qc.getQueryData(qk.preview("uploads/a.txt"))).toBeUndefined();
    expect(qc.getQueryData(qk.detail("uploads/a.txt"))).toBeUndefined();
  });

  it("leaves other files' cached previews alone", () => {
    qc.setQueryData(qk.preview("uploads/b.txt"), { url: "https://signed-b" });

    dropDeletedFileFromCache(qc, "uploads/a.txt");

    expect(qc.getQueryData(qk.preview("uploads/b.txt"))).toEqual({
      url: "https://signed-b",
    });
  });

  it("does not touch the session archive caches", () => {
    qc.setQueryData(qk.stats(), { total_sessions: 2 });
    qc.setQueryData(sessionKey("s-20261119-a1b2c3"), { manifest: {} });

    dropDeletedFileFromCache(qc, "uploads/a.txt");

    expect(qc.getQueryData(qk.stats())).toEqual({ total_sessions: 2 });
    expect(qc.getQueryData(sessionKey("s-20261119-a1b2c3"))).toEqual({ manifest: {} });
  });

  it("is a no-op for an unseeded cache", () => {
    expect(() =>
      dropDeletedFileFromCache(qc, "uploads/missing.txt"),
    ).not.toThrow();
    expect(qc.getQueryData(qk.files())).toBeUndefined();
  });
});

describe("sessionKey", () => {
  it("nests each session under the generated session-detail key", () => {
    expect(sessionKey("s-1").slice(0, qk.session().length)).toEqual([...qk.session()]);
    expect(sessionKey("s-1")).not.toEqual(sessionKey("s-2"));
  });
});

describe("recordAppliedReport", () => {
  const report = (overrides: Partial<RetentionReport>): RetentionReport => ({
    as_of: "2026-11-19",
    classes: [],
    date: "2026-11-19",
    dry_run: false,
    generated_at: "2026-11-19T15:16:00Z",
    kept_total: 5,
    removed_bytes: 0,
    removed_total: 0,
    report_key: "reports/2026-11-19.json",
    schema_version: 1,
    ...overrides,
  });

  it("replaces the same day's stale row with the run just applied", () => {
    const qc = new QueryClient();
    qc.setQueryData<RetentionReportList>(qk.retentionReports(), {
      items: [
        { date: "2026-11-19", key: "reports/2026-11-19.json", kept_total: 1, removed_total: 0, generated_at: "2026-11-19T14:51:00Z" },
        { date: "2026-11-18", key: "reports/2026-11-18.json", kept_total: 2, removed_total: 1, generated_at: "2026-11-18T10:00:00Z" },
      ],
    });

    recordAppliedReport(qc, report({}));

    const items = qc.getQueryData<RetentionReportList>(qk.retentionReports())?.items;
    expect(items?.map((r) => [r.date, r.kept_total, r.generated_at])).toEqual([
      ["2026-11-19", 5, "2026-11-19T15:16:00Z"],
      ["2026-11-18", 2, "2026-11-18T10:00:00Z"],
    ]);
  });

  it("ignores dry runs, which write no report", () => {
    const qc = new QueryClient();
    recordAppliedReport(qc, report({ dry_run: true, report_key: null }));
    expect(qc.getQueryData(qk.retentionReports())).toBeUndefined();
  });
});

describe("markSessionReprocessing", () => {
  it("flips a failed session's cached detail to processing with the old error cleared", () => {
    const qc = new QueryClient();
    const detail = {
      manifest: { session_id: "s-1", status: "failed", error: "post-processing failed: boom" },
      transcript: null,
    };
    qc.setQueryData(sessionKey("s-1"), detail);

    markSessionReprocessing(qc, "s-1");

    const after = qc.getQueryData<typeof detail>(sessionKey("s-1"));
    expect(after?.manifest.status).toBe("recorded");
    expect(after?.manifest.error).toBeNull();
    expect(after?.manifest.session_id).toBe("s-1");
  });

  it("is a no-op when the session is not cached", () => {
    const qc = new QueryClient();
    markSessionReprocessing(qc, "s-2");
    expect(qc.getQueryData(sessionKey("s-2"))).toBeUndefined();
  });
});
