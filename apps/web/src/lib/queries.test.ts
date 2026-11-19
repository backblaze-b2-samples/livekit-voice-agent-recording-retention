import { QueryClient } from "@tanstack/react-query";
import { beforeEach, describe, expect, it } from "vitest";
import { dropDeletedFileFromCache, qk, sessionKey } from "@/lib/queries";
import type { FileMetadata } from "@livekit-voice-agent-recording-retention/shared";

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
