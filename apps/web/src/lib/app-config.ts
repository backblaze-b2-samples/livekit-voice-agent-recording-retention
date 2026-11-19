// Single source of truth for app identity. Rename here to rebrand a clone of this starter.
export const APP_NAME = "LiveKit Agent Session Archive";
export const APP_DESCRIPTION =
  "Voice-agent session recordings, manifests and retention on Backblaze B2";

/**
 * URL- and storage-safe form of APP_NAME ("My Sample App" -> "my-sample-app").
 * Derived, never declared a second time: anything that needs an app-namespaced
 * identifier (a `localStorage` key, a cache prefix) builds on this, so a
 * rebrand cannot leave one stale copy behind for a grep to miss.
 */
export const APP_SLUG = APP_NAME.toLowerCase()
  .replace(/[^a-z0-9]+/g, "-")
  .replace(/^-+|-+$/g, "");
