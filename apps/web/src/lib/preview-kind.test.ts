import { describe, expect, it } from "vitest";

import { previewKind } from "./preview-kind";

describe("previewKind", () => {
  it("uses the stored content type first", () => {
    expect(previewKind("image/png", "a.png")).toBe("image");
    expect(previewKind("application/pdf", "a.pdf")).toBe("pdf");
    expect(previewKind("audio/ogg", "recording.ogg")).toBe("audio");
    expect(previewKind("application/json", "2026-11-19.json")).toBe("text");
    expect(previewKind("text/plain; charset=utf-8", "notes.txt")).toBe("text");
  });

  it("falls back to the extension for octet-stream objects", () => {
    expect(previewKind("application/octet-stream", "recording.ogg")).toBe("audio");
    expect(previewKind("application/octet-stream", "report.JSON")).toBe("text");
    expect(previewKind("application/octet-stream", "blob.bin")).toBeNull();
    expect(previewKind("application/octet-stream", "no-extension")).toBeNull();
  });
});
