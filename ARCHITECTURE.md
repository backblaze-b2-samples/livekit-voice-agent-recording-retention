<!-- last_verified: 2026-11-19 -->
# Architecture

## Components

Five Docker Compose services (`docker-compose.yml`) plus the Next.js UI on the
host:

```
browser (Next.js on :3000) --REST--> api (:8000) --boto3--> Backblaze B2
   |  livekit-client (interactive join)    ^   \--livekit-api--> livekit (:7880)
   v                                        |                       |   ^
livekit (:7880, 7881, 50000-50019/udp) -----+ signed webhooks        |   | agent dispatch
   |  redis bus                                                      v   |
egress ------------- S3 PutObject / multipart (its own client) ---> Backblaze B2
agent (LiveKit Agents worker, espeak-ng) -- publishes audio --> livekit
```

The application components below are generated from `docs/exec-plans/sample.json`.

<!-- gen:begin arch-components -->
Record LiveKit voice-agent sessions through Egress directly to Backblaze B2, link each recording to its transcription and evaluation in a per-session manifest, and apply retention by session class.

- **apps/web/** — Next.js 16, React 19, Tailwind v4, shadcn/ui, TanStack Query, livekit-client
  - Session Recording (`/sessions/new`) — create a room, dispatch the test agent, and have Egress record it straight to B2
  - Session Library (`/sessions`) — browse sessions under sessions/, play recordings, edit class or label, reprocess, delete
  - Retention (`/retention`) — keep or remove sessions by class, with a per-day report in B2
  - File Browser (`/files`) — list, preview, download, delete any object in the bucket
  - Dashboard (`/`) — sessions by class and status, recorded minutes and bytes, last retention run
  - Settings (`/settings`) — theme plus labelled demo preference fields
- **services/api/** — FastAPI, Python 3.12, boto3, livekit-api, faster-whisper
  - REST API for every operation the frontend consumes, exported to `docs/api/openapi.json`
  - Backblaze B2 (S3-compatible API), written directly by LiveKit Egress access isolated in the `repo/` layer
  - Webhook Manifests — verified LiveKit webhooks, stored as evidence, keep each session manifest current
  - Transcription and Evaluation — local faster-whisper transcript, word error rate and expected-phrase check
  - Structured JSON logging with request tracing, plus `/health` and Prometheus `/metrics`
- **packages/shared/** — TypeScript types generated from the API contract by `pnpm gen:api`, consumed by `apps/web/` as a workspace dependency (pnpm workspaces plus Docker Compose)
<!-- gen:end arch-components -->

## Backend Layering

The API follows a strict layered architecture:

```
types/     Pydantic models — no logic, no imports from other layers
  |
config/    Settings (pydantic-settings) — depends only on types
  |
repo/      Adapters: boto3 B2 client, LiveKit server SDK, faster-whisper (no business logic)
  |
service/   Business logic — calls repo, returns types
  |
runtime/   FastAPI routes — calls service, never repo directly
```

### Layering Rules

1. Dependencies flow downward only: `types` -> `config` -> `repo` -> `service` -> `runtime`
2. No backward imports (e.g., service must not import from runtime)
3. `boto3`, the LiveKit SDK (`livekit`) and the model stack (`faster_whisper`, `ctranslate2`, `av`) only allowed in `repo/` layer
6. `app/jobs/` holds command-line entry points (`python -m app.jobs.retention`) that call the service layer
4. All boundary data uses Pydantic models (no raw dicts across layers)
5. Authored Python files under `services/api/app/` stay under 300 lines

### Directory Structure

<!-- gen:begin arch-directory -->
```
services/api/
  main.py                  App entrypoint, middleware, router registration
  app/
    types/                 Pydantic models, and the response-model base
    config/                Settings loaded from environment
    repo/                  B2 S3 client (data access layer)
    service/               Business logic
    runtime/               FastAPI route handlers
  scripts/                 Operational scripts (OpenAPI export, bucket CORS)
  tests/                   pytest tests (structural + integration)
```
<!-- gen:end arch-directory -->

## Boundary Invariants

- **No external SDK leakage**: `boto3`, `livekit-api` and `faster-whisper` are imported only in `app/repo/` (asserted by `tests/test_structure.py`). The model stack is imported lazily inside `repo/transcriber.py`, so the host venv `pnpm verify` uses does not need it.
- **Manifest first**: `POST /api/sessions` writes `manifest.json` before Egress starts, and a session that fails later keeps a `failed` manifest. Retention never deletes a manifest; only an explicit session delete does.
- **Egress writes the recording**: the API never uploads audio. It reads the recording back (streamed) to checksum and transcribe it.
- **No raw dicts at boundaries**: data crossing layers uses Pydantic models; the parsed webhook crosses `repo/` -> `service/` as frozen dataclasses (`app/types/webhook.py`).
- **No cross-layer mutable state**: configuration is read-only after init. Module-local state (listing cache, B2 and LiveKit health caches, webhook dedupe ids, per-session manifest locks, rate-limit and metrics counters) is guarded by a `threading.Lock`.
- **Validated inputs**: session ids must match `s-<YYYYMMDD>-<6 hex>` before any key is built from them; file keys reject path traversal; webhook bodies are verified byte for byte before parsing.

## Deployment

- **Docker Compose only.** `make up` builds and starts `redis`, `livekit`, `egress`, `agent` and `api`; `make web` runs the UI on the host. There is no hosted deployment target: the sample needs long-lived LiveKit, Egress and Redis containers, which serverless platforms do not run.
- Only `7880/tcp`, `7881/tcp`, `50000-50019/udp` (LiveKit) and `8000/tcp` (API) are published. Redis and Egress have no host ports; B2 credentials reach Egress over the private Compose network inside each recording request. See [infra/livekit/README.md](infra/livekit/README.md).

External provisioning and deployment remain explicit user-approved actions.

## Data Stores

<!-- gen:begin arch-data-stores -->
- **Backblaze B2 (S3-compatible API), written directly by LiveKit Egress** — the only data store; there is no application database
  - Every object this app writes lives under the `sessions/` key prefix of one bucket
  - Listing, per-key metadata and presigned URLs all come from the S3 surface below
  - The primary entity is `SessionManifest`; one session is one object
<!-- gen:end arch-data-stores -->

## External Services

<!-- gen:begin arch-external-services -->
- **Backblaze B2 (S3-compatible API), written directly by LiveKit Egress** — reached only through `services/api/app/repo/`, using:
  - `Egress PutObject / multipart upload` — LiveKit Egress's own S3 uploader writes sessions/<date>/<room>/recording.ogg directly to B2; the API never re-uploads it
  - `put_object` — manifest.json, transcript.json, evaluation.json, webhooks/<event_id>.json and reports/<date>.json
  - `get_object (streamed)` — SHA-256 of the recording, transcription input, and reading manifests and reports
  - `head_object` — recording size and ETag, checked against the webhook's size; the /api/health probe
  - `list_objects_v2 (paginated)` — session list (manifests under sessions/), reports list, and the full-bucket explorer
  - `list_object_versions + delete_object(VersionId)` — retention and session delete remove every version, so the bytes are actually gone
  - `presigned GET` — audio playback and downloads in the UI
<!-- gen:end arch-external-services -->

## Trust Boundaries

See [docs/SECURITY.md](docs/SECURITY.md) for full security documentation.

- **Browser -> API**: CORS-restricted to localhost origins. `CORSMiddleware` is outermost so error responses carry CORS headers too (see [docs/RELIABILITY.md](docs/RELIABILITY.md#error-handling)). A per-IP rate limiter sits inside it; the webhook route is exempt.
- **LiveKit -> API**: `POST /api/webhooks/livekit` accepts only bodies whose SHA-256 matches the JWT in `Authorization`, signed with `LIVEKIT_API_SECRET`. Anything else is a 401.
- **API -> LiveKit**: server API calls signed with the dev key pair; browser join tokens are scoped to one room, 30 minutes.
- **API -> Egress -> B2**: each Egress request carries an `S3Upload` with the B2 key, over the Compose network only.
- **API -> B2**: application key, signature v4, `user_agent_extra=b2ai-livekit-agent-session-archive`.
- **Browser -> B2**: presigned GET only (playback and downloads, 10 to 15 minutes).

## Data Flows

- **Create**: Browser -> `POST /api/sessions` -> create room -> write manifest (`recording`) -> dispatch agent -> start Egress (literal key, `S3Upload` from `B2_REGION`).
- **Record**: agent speaks -> deletes the room -> Egress uploads `recording.ogg` to B2.
- **Webhook**: LiveKit -> `POST /api/webhooks/livekit` -> verify -> dedupe -> store evidence -> update manifest (`recorded`) -> background post-processing.
- **Post-process**: `head_object` size check -> streamed SHA-256 -> download to a temp file -> faster-whisper -> `transcript.json` -> evaluation -> `evaluation.json` -> manifest (`processed`).
- **Retention**: `POST /api/retention/runs` or `make retention-apply` -> decide per manifest -> delete every version of the media and derivatives -> manifest (`expired`) -> `reports/<date>.json`.
- **Browse**: `/sessions` lists manifests under `sessions/`; `/files` lists the whole bucket.

## Observability

- Structured JSON logging with `request_id`; every webhook and session transition is logged.
- `/metrics` (Prometheus format): request count and latency, verified and rejected webhooks.
- `/api/health`: B2 connectivity and LiveKit reachability.
- `make logs` follows every Compose service.

## API Contract

<!-- gen:begin arch-api-contract -->
- Checked-in OpenAPI artifact: `docs/api/openapi.json`
- Export / check: `pnpm contract:export` / `pnpm contract:check`
- Generate the client seam from it: `pnpm gen:api` (drift gate: `pnpm gen:check`)
- FastAPI freshness test: `services/api/tests/test_openapi_contract.py`
- Frontend route drift test: `apps/web/src/lib/api-contract.test.ts`

The FastAPI routers and Pydantic models are the single source of truth. The
frontend's `API_CLIENT_ROUTES` registry, the `qk` query-key factory and the
shared TypeScript types are **generated** from the exported artifact by
`pnpm gen:api`, so the client cannot drift from the backend — there is no
hand-written copy left to disagree. The two contract tests are kept as a
belt-and-braces check that the generated files and the committed artifact are
still in step.

| Route | Returns | Generated client route |
| --- | --- | --- |
| `DELETE /api/files-by-key` | `DeleteFileResponse` | `fileByKeyDelete` |
| `DELETE /api/files/{key}` | `DeleteFileResponse` | `legacyFileDelete` |
| `DELETE /api/sessions/{session_id}` | — | `sessionDelete` |
| `GET /api/files` | `FileMetadata[]` | `files` |
| `GET /api/files-by-key/detail` | `FileMetadataDetail` | `fileByKeyDetail` |
| `GET /api/files-by-key/download` | `FileUrlResponse` | `fileByKeyDownload` |
| `GET /api/files-by-key/metadata` | `FileMetadata` | `fileByKeyMetadata` |
| `GET /api/files-by-key/preview` | `FileUrlResponse` | `fileByKeyPreview` |
| `GET /api/files/{key}` | `FileMetadata` | `legacyFileMetadata` |
| `GET /api/files/{key}/download` | `FileUrlResponse` | `legacyFileDownload` |
| `GET /api/files/{key}/preview` | `FileUrlResponse` | `legacyFilePreview` |
| `GET /api/health` | `HealthStatus` | `health` |
| `GET /api/retention/policy` | `RetentionPolicy` | `retentionPolicy` |
| `GET /api/retention/reports` | `RetentionReportList` | `retentionReports` |
| `GET /api/retention/reports/{day}` | `RetentionReport` | `retentionReport` |
| `GET /api/scripts` | `ScriptList` | `scripts` |
| `GET /api/sessions` | `SessionList` | `sessions` |
| `GET /api/sessions/{session_id}` | `SessionDetail` | `sessionDetail` |
| `GET /api/stats` | `ArchiveStats` | `stats` |
| `GET /metrics` | — | _server-only_ |
| `PATCH /api/sessions/{session_id}` | `SessionManifest` | `sessionUpdate` |
| `POST /api/retention/runs` | `RetentionReport` | `retentionRun` |
| `POST /api/sessions` | — | `sessionCreate` |
| `POST /api/sessions/{session_id}/reprocess` | — | `sessionReprocess` |
| `POST /api/sessions/{session_id}/token` | `JoinToken` | `sessionToken` |
| `POST /api/webhooks/livekit` | `WebhookAck` | _server-only_ |
<!-- gen:end arch-api-contract -->

## Canonical Files

<!-- gen:begin arch-canonical-files -->
Hand-written — this is the file to edit:

- Layered API handler: `services/api/app/runtime/`
- Service orchestration: `services/api/app/service/`
- B2 data access (repo layer): `services/api/app/repo/b2_client.py`
- Pydantic models: `services/api/app/types/` (`base.py` carries the response-model config)
- Config (pydantic-settings): `services/api/app/config/settings.py`
- Structural tests: `services/api/tests/test_structure.py`
- OpenAPI exporter: `services/api/scripts/export_openapi.py`
- Frontend API client — error policy, transport, fallback: `apps/web/src/lib/api-client.ts`
- Frontend data layer — caching, invalidation, polling: `apps/web/src/lib/queries.ts`
- Shared type barrel: `packages/shared/src/types.ts`
- Generator policy: `scripts/gen/api-gen.config.json`
- Sample manifest behind the generated docs: `docs/exec-plans/sample.json`

Generated — **never hand-edit**; change the source and re-run the command:

- `docs/api/openapi.json` — `pnpm contract:export` (source: the routers and models)
- `packages/shared/src/generated/api-types.ts` — `pnpm gen:api`
- `apps/web/src/lib/generated/api-routes.ts` — `pnpm gen:api`
- `apps/web/src/lib/generated/query-keys.ts` — `pnpm gen:api`
- The marker-delimited regions of this file, `AGENTS.md`, `README.md` and the 0 `infra/` runbooks — `pnpm gen:docs`
<!-- gen:end arch-canonical-files -->

## Core Features

<!-- gen:begin arch-core-features -->
- [Session Recording](docs/features/session-recording.md) — create a room, dispatch the test agent, and have Egress record it straight to B2
- [Session Library](docs/features/session-library.md) — browse sessions under sessions/, play recordings, edit class or label, reprocess, delete
- [Webhook Manifests](docs/features/webhook-manifests.md) — verified LiveKit webhooks, stored as evidence, keep each session manifest current
- [Transcription and Evaluation](docs/features/transcription-evaluation.md) — local faster-whisper transcript, word error rate and expected-phrase check
- [Retention](docs/features/retention.md) — keep or remove sessions by class, with a per-day report in B2
- [File Browser](docs/features/file-browser.md) — list, preview, download, delete any object in the bucket
- [Dashboard](docs/features/dashboard.md) — sessions by class and status, recorded minutes and bytes, last retention run
- [Settings](docs/features/settings.md) — theme plus labelled demo preference fields
<!-- gen:end arch-core-features -->

## References

<!-- gen:begin arch-references -->
- [docs/SECURITY.md](docs/SECURITY.md) — security principles and implementation
- [docs/RELIABILITY.md](docs/RELIABILITY.md) — reliability expectations
- [AGENTS.md](AGENTS.md) — architectural invariants and agent instructions
<!-- gen:end arch-references -->
