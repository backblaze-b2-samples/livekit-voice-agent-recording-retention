/**
 * Which inline preview the Files dialog can render for an object. Pure, so the
 * mapping is unit-tested without a browser.
 *
 * The stored content type wins; the key's extension is the fallback for
 * objects stored as `application/octet-stream` (an Egress recording can be).
 */
export type PreviewKind = "image" | "pdf" | "audio" | "text";

const AUDIO_EXTENSIONS = new Set(["ogg", "oga", "opus", "mp3", "m4a", "wav", "webm"]);
const TEXT_EXTENSIONS = new Set(["json", "txt", "md", "csv", "log"]);

function extension(filename: string): string {
  const dot = filename.lastIndexOf(".");
  return dot === -1 ? "" : filename.slice(dot + 1).toLowerCase();
}

export function previewKind(contentType: string, filename: string): PreviewKind | null {
  const type = contentType.toLowerCase();
  if (type.startsWith("image/")) return "image";
  if (type === "application/pdf") return "pdf";
  if (type.startsWith("audio/")) return "audio";
  if (type.startsWith("text/") || type === "application/json") return "text";
  const ext = extension(filename);
  if (AUDIO_EXTENSIONS.has(ext)) return "audio";
  if (TEXT_EXTENSIONS.has(ext)) return "text";
  return null;
}
