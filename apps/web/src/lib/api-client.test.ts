import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

import {
  ApiError,
  deleteFile,
  getDownloadUrl,
  getFile,
  getFileDetail,
  getPreviewUrl,
  createSession,
  deleteSession,
  getSessions,
} from "./api-client";

type FileKeyOperation = {
  call: (key: string) => Promise<unknown>;
  legacyPath: (key: string) => string;
  method: "GET" | "DELETE";
  name: string;
  path: string;
  unsafeFallbackKeys: { key: string }[];
};

const operations: FileKeyOperation[] = [
  {
    call: getFile,
    legacyPath: (key) => `/api/files/${encodeURIComponent(key)}`,
    method: "GET",
    name: "getFile",
    path: "/api/files-by-key/metadata",
    unsafeFallbackKeys: [
      "stats",
      "stats/activity",
      "payroll/download",
      "payroll/preview",
      "reports/download",
      "reports/preview",
      "../secret.txt",
      "uploads/%2e%2e/secret.txt",
    ].map((key) => ({ key })),
  },
  {
    call: getDownloadUrl,
    legacyPath: (key) => `/api/files/${encodeURIComponent(key)}/download`,
    method: "GET",
    name: "getDownloadUrl",
    path: "/api/files-by-key/download",
    unsafeFallbackKeys: ["../secret.txt", "uploads/%2e%2e/secret.txt"].map((key) => ({
      key,
    })),
  },
  {
    call: getPreviewUrl,
    legacyPath: (key) => `/api/files/${encodeURIComponent(key)}/preview`,
    method: "GET",
    name: "getPreviewUrl",
    path: "/api/files-by-key/preview",
    unsafeFallbackKeys: ["../secret.txt", "uploads/%2e%2e/secret.txt"].map((key) => ({
      key,
    })),
  },
  {
    call: deleteFile,
    legacyPath: (key) => `/api/files/${encodeURIComponent(key)}`,
    method: "DELETE",
    name: "deleteFile",
    path: "/api/files-by-key",
    unsafeFallbackKeys: ["../secret.txt", "uploads/%2e%2e/secret.txt"].map((key) => ({
      key,
    })),
  },
];

const keyCases = [
  "folder/file.txt",
  "folder/file #1?.txt",
  "folder/100% complete.txt",
  "../secret.txt",
  "uploads/%2e%2e/secret.txt",
  "stats",
  "stats/activity",
  "tenant-a/reports/download",
  "tenant-a/reports/preview",
].map((key) => ({ key }));

const fetchMock = vi.fn<typeof fetch>();

function jsonResponse(body: unknown) {
  return new Response(JSON.stringify(body), {
    headers: { "Content-Type": "application/json" },
    status: 200,
  });
}

function errorResponse(status: number, detail: string) {
  return new Response(JSON.stringify({ detail }), {
    headers: { "Content-Type": "application/json" },
    status,
  });
}

function requestedPath(callIndex = 0) {
  const [input] = fetchMock.mock.calls[callIndex];
  const url = new URL(input as string);
  return `${url.pathname}${url.search}`;
}

async function expectEmptyKeyRejected(call: FileKeyOperation["call"]) {
  try {
    await call("");
    throw new Error("Expected empty key to reject");
  } catch (error) {
    expect(error).toBeInstanceOf(ApiError);
    const apiError = error as ApiError;
    expect(apiError.message).toBe("File key is required");
    expect(apiError.status).toBe(400);
  }
}

beforeEach(() => {
  fetchMock.mockReset();
  fetchMock.mockResolvedValue(jsonResponse({}));
  vi.stubGlobal("fetch", fetchMock);
});

afterEach(() => {
  vi.unstubAllGlobals();
});

describe.each(operations)(
  "$name",
  ({ call, legacyPath, method, path, unsafeFallbackKeys }) => {
    it.each(keyCases)("sends '$key' as a query parameter", async ({ key }) => {
      await call(key);

      expect(requestedPath()).toBe(`${path}?${new URLSearchParams({ key })}`);
      const init = fetchMock.mock.calls[0][1];
      expect(init?.method ?? "GET").toBe(method);
    });

    it("rejects empty keys before making a request", async () => {
      await expectEmptyKeyRejected(call);

      expect(fetchMock).not.toHaveBeenCalled();
    });

    it("falls back to the legacy route when the query route is unavailable", async () => {
      const key = "uploads/report final.txt";
      fetchMock
        .mockResolvedValueOnce(errorResponse(404, "Not Found"))
        .mockResolvedValueOnce(jsonResponse({ key }));

      await call(key);

      expect(requestedPath(0)).toBe(`${path}?${new URLSearchParams({ key })}`);
      expect(requestedPath(1)).toBe(legacyPath(key));
      expect(fetchMock).toHaveBeenCalledTimes(2);
    });

    it("does not fall back when the current API reports a missing file", async () => {
      const key = "stats";
      fetchMock.mockResolvedValueOnce(errorResponse(404, "File not found"));

      await expect(call(key)).rejects.toMatchObject({
        message: "File not found",
        status: 404,
      });

      expect(fetchMock).toHaveBeenCalledTimes(1);
    });

    it.each(unsafeFallbackKeys)(
      "does not fall back for unsafe legacy path key '$key'",
      async ({ key }) => {
        fetchMock.mockResolvedValueOnce(errorResponse(404, "Not Found"));

        await expect(call(key)).rejects.toMatchObject({
          message: "Current API version required for this file key",
          status: 404,
        });

        expect(fetchMock).toHaveBeenCalledTimes(1);
      }
    );
  }
);

// getFileDetail is a new endpoint with NO legacy path fallback (an older backend
// wouldn't serve it under any route), so it's tested on its own rather than in
// the shared legacy-fallback harness above.
describe("getFileDetail", () => {
  it.each(keyCases)("sends '$key' as a query parameter", async ({ key }) => {
    await getFileDetail(key);

    expect(requestedPath()).toBe(
      `/api/files-by-key/detail?${new URLSearchParams({ key })}`
    );
    const init = fetchMock.mock.calls[0][1];
    expect(init?.method ?? "GET").toBe("GET");
  });

  it("rejects empty keys before making a request", async () => {
    await expectEmptyKeyRejected(getFileDetail);

    expect(fetchMock).not.toHaveBeenCalled();
  });

  it("does not fall back on 404 — it surfaces the error in one request", async () => {
    fetchMock.mockResolvedValueOnce(errorResponse(404, "Not Found"));

    await expect(getFileDetail("uploads/gone.png")).rejects.toMatchObject({
      status: 404,
    });

    expect(fetchMock).toHaveBeenCalledTimes(1);
  });
});

describe("session archive client", () => {
  it("drops empty filters from the session list query", async () => {
    fetchMock.mockResolvedValueOnce(jsonResponse({ items: [], next_cursor: null }));

    await getSessions({ session_class: "debug", status: "", limit: 20 });

    const [url] = fetchMock.mock.calls[0];
    expect(String(url)).toMatch(/\/api\/sessions\?session_class=debug&limit=20$/);
  });

  it("posts the create body as JSON", async () => {
    fetchMock.mockResolvedValueOnce(jsonResponse({ session_id: "s-20261119-a1b2c3" }));

    await createSession({ script_id: "support-handoff", session_class: "debug", mode: "scripted" });

    const [url, init] = fetchMock.mock.calls[0];
    expect(String(url)).toMatch(/\/api\/sessions$/);
    expect(init?.method).toBe("POST");
    expect(JSON.parse(String(init?.body))).toEqual({
      script_id: "support-handoff",
      session_class: "debug",
      mode: "scripted",
    });
  });

  it("treats a 204 delete as success without parsing a body", async () => {
    fetchMock.mockResolvedValueOnce(new Response(null, { status: 204 }));

    await expect(deleteSession("s-20261119-a1b2c3")).resolves.toBeUndefined();
    const [url, init] = fetchMock.mock.calls[0];
    expect(String(url)).toMatch(/\/api\/sessions\/s-20261119-a1b2c3$/);
    expect(init?.method).toBe("DELETE");
  });

  it("surfaces the API detail on a failed delete", async () => {
    fetchMock.mockResolvedValueOnce(errorResponse(404, "Session s-1 not found"));

    await expect(deleteSession("s-1")).rejects.toMatchObject({
      status: 404,
      message: "Session s-1 not found",
    });
  });
});
