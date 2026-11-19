// GENERATED FILE — DO NOT EDIT.
//
// Written by `pnpm gen:api` from:
//   docs/api/openapi.json
//   scripts/gen/api-gen.config.json
//
// Hand edits are discarded by the next `pnpm gen:api`. `pnpm gen:check`
// (part of `pnpm verify:web`) fails while this file disagrees with the
// contract. To change what is here, change the FastAPI route or Pydantic
// model and re-run `pnpm contract:export && pnpm gen:api`.

/** The verbs this app's routes actually use, narrowed from the contract. */
export type ApiClientRoute = {
  method: "delete" | "get" | "patch" | "post";
  path: string;
};

/**
 * Every frontend-callable operation in the contract, keyed by the name
 * `scripts/gen/api-gen.config.json` gives it. `as const` keeps each path and
 * verb a literal type, so a template-literal parameter can require a `{…}`
 * placeholder and a `.method.toUpperCase()` stays exact.
 */
export const API_CLIENT_ROUTES = {
  fileByKeyDelete: { method: "delete", path: "/api/files-by-key" },
  legacyFileDelete: { method: "delete", path: "/api/files/{key}" },
  sessionDelete: { method: "delete", path: "/api/sessions/{session_id}" },
  files: { method: "get", path: "/api/files" },
  fileByKeyDetail: { method: "get", path: "/api/files-by-key/detail" },
  fileByKeyDownload: { method: "get", path: "/api/files-by-key/download" },
  fileByKeyMetadata: { method: "get", path: "/api/files-by-key/metadata" },
  fileByKeyPreview: { method: "get", path: "/api/files-by-key/preview" },
  legacyFileMetadata: { method: "get", path: "/api/files/{key}" },
  legacyFileDownload: { method: "get", path: "/api/files/{key}/download" },
  legacyFilePreview: { method: "get", path: "/api/files/{key}/preview" },
  health: { method: "get", path: "/api/health" },
  retentionPolicy: { method: "get", path: "/api/retention/policy" },
  retentionReports: { method: "get", path: "/api/retention/reports" },
  retentionReport: { method: "get", path: "/api/retention/reports/{day}" },
  scripts: { method: "get", path: "/api/scripts" },
  sessions: { method: "get", path: "/api/sessions" },
  sessionDetail: { method: "get", path: "/api/sessions/{session_id}" },
  stats: { method: "get", path: "/api/stats" },
  sessionUpdate: { method: "patch", path: "/api/sessions/{session_id}" },
  retentionRun: { method: "post", path: "/api/retention/runs" },
  sessionCreate: { method: "post", path: "/api/sessions" },
  sessionReprocess: { method: "post", path: "/api/sessions/{session_id}/reprocess" },
  sessionToken: { method: "post", path: "/api/sessions/{session_id}/token" },
} as const satisfies Record<string, ApiClientRoute>;
