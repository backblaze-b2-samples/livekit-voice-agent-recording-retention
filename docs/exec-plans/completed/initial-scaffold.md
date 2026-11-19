# Scaffold plan: `livekit-voice-agent-recording-retention`

Starter kit: `backblaze-b2-samples/vibe-coding-starter-kit` at commit
`580420193e82d34fdf9a9d7611967d356023bbca` (2026-11-19). The starter kit is the
ceiling: keep its B2 scaffolding, strip what this app does not need, add the
LiveKit session-archive surface.

Publish name: `livekit-voice-agent-recording-retention` (org `backblaze-b2-samples`).
Attribution token (S3 `user_agent_extra` and every `utm_content`):
`b2ai-livekit-agent-session-archive`.

---

## 1. Purpose

A runnable reference for archiving voice-agent sessions on Backblaze B2. A local
LiveKit stack (server, Egress, Redis) runs in Docker Compose. A minimal scripted
test agent speaks in a room, and **LiveKit Egress writes the session recording
directly to B2** through its own S3-compatible uploader, configured with the B2
endpoint derived from `B2_REGION`. When Egress finishes, the LiveKit webhook tells
a FastAPI receiver where the file landed; the receiver writes a per-session
`manifest.json` next to the recording that links the recording (location, size,
duration, SHA-256), a local Whisper transcription, and a deterministic evaluation
of the session against its script. A retention job then keeps or removes each
session according to its class and writes a per-day report to B2. It is for AI
engineers running LiveKit Agents who need recordings, transcripts and evaluation
results in one durable, inexpensive, S3-compatible store, with a retention story,
and no hosted model or speech provider.

---

## 2. Architecture delta from the starter kit

| KEEP (as-is) | TRIM (remove) | ADD (new) |
|---|---|---|
| UI kit and design system: `apps/web/src/components/ui/**`, `globals.css`, `/design` page | `/upload` route, `components/upload/**`, `upload-queue-context.tsx`, `upload-*` libs and their tests, `e2e/upload.spec.ts` (sessions are created by recording, not upload; nothing in this app uploads from the browser) | `docker-compose.yml` with `redis`, `livekit`, `egress`, `agent`, `api` services, plus `infra/livekit/livekit.yaml` and `infra/livekit/egress.yaml` templates |
| **Full-bucket explorer** `/files` (`app/files/**`, `components/files/**`, sidebar entry). **Non-negotiable keep**: browses `sessions/`, `reports/` and anything else in the bucket | Backend upload path: `runtime/upload.py`, `service/upload.py`, `repo/b2_upload.py`, `types/upload.py`, presigned PUT, upload tests (`test_upload_*`, `test_presign_disposition` if upload-only) | **`/sessions`**: the sample-specific asset explorer scoped to the `sessions/` prefix. Table of sessions (date, room, class, status, duration, WER) and a detail view with an audio player (presigned GET), manifest, transcript, evaluation, webhook evidence, and actions |
| Layout: sidebar, header, command palette, health banner, theme provider, error/loading/not-found | `service/metadata.py` image/PDF extraction (Pillow, pypdf) and `docs/features/metadata-extraction.md`, unless the kept file browser's detail panel imports it; if it does, keep only what `/files` needs | **`/sessions/new`**: create form (script, class, mode) |
| `/settings` (theme + demo preferences) and its form, the in-repo form exemplar | Dashboard's upload chart and recent-uploads semantics (rewrite, keep the route) | **Join panel** on a session in `interactive` mode: `livekit-client` (Apache-2.0) joins the room with the browser mic using a token from the API |
| Backend layering `types -> config -> repo -> service -> runtime`; one cached boto3 client in `repo/`; structured logging; rate limit; health probe; OpenAPI contract (`pnpm contract:export`, `pnpm gen:api`); `pnpm verify` gates; `check:agent-docs` | `infra/vercel/`, `infra/railway/`, `vercel.json`, `railway.json`, `apps/web/vercel.json`, `services/api/vercel.json`, `services/api/railway.json`, `services/api/index.py` and `test_vercel_entrypoint.py` (this app needs long-lived LiveKit, Egress and Redis containers; it ships as Docker Compose only). If `pnpm gen:check` or `check:agent-docs` require a target, keep `railway` and record why | **`/retention`**: per-class policy table, "Run retention" (dry run on by default, optional as-of date), list of `reports/<date>.json` with kept/removed per class |
| Presigned GET for playback and downloads | Starter `docs/images/b2-starterkit-*.png` references (screenshots come in a later step; set `screenshots: []`) | Dashboard rewrite: sessions by class and status, total recorded minutes and bytes, last retention report, recent sessions |
| `.env.example` pattern, `scripts/doctor.mjs`, `scripts/setup.mjs` | | `Makefile`: `up`, `down`, `logs`, `demo`, `test`, `retention` |
| | | Backend: `repo/livekit_api.py` (rooms, dispatch, egress, tokens, webhook verification), `repo/session_store.py` (manifest, transcript, evaluation, webhook evidence, reports in B2), `repo/transcriber.py` (faster-whisper, lazy import), `service/sessions.py`, `service/postprocess.py`, `service/retention.py`, `runtime/sessions.py`, `runtime/webhooks.py`, `runtime/retention.py`, `jobs/retention.py` CLI |
| | | `services/agent/`: the minimal test agent (LiveKit Agents worker), its `Dockerfile`, `requirements.txt` with pinned versions, bundled script files |
| | | `services/api/Dockerfile` (the `api` compose service is the webhook receiver and the REST API the web UI calls) |
| | | `services/api/live_tests/test_session_archive_e2e.py` (the `make test` live suite) |

**Bucket-explorer note:** no tension. `/files` stays verbatim as the full-bucket
explorer; `/sessions` is the additional explorer scoped to `sessions/`.

### Pinned versions (confirmed 2026-11-19, each released at least two weeks earlier)

| Component | Pin | Notes |
|---|---|---|
| LiveKit server | `livekit/livekit-server:v1.13.11` | amd64 and arm64 images |
| LiveKit Egress | `livekit/egress:v1.15.0` | amd64 and arm64. v1.15.0 includes the storage-library fix that sets AWS SDK request checksums to "when required" for non-AWS endpoints, which third-party S3 stores need, and records audio-only room composites through the SDK source (no Chrome) |
| Redis | latest `redis:7.2.x-alpine` patch tag | 7.2 is the last BSD-licensed line; run unmodified |
| `livekit-agents` (agent) | `1.8.10` | pins `livekit==1.1.21` exactly, so the agent image uses `livekit==1.1.21` |
| `livekit-api` (agent and api) | `1.2.2` | agents requires `livekit-api<2` |
| `livekit` rtc SDK (agent) | `1.1.21` | forced by agents 1.8.10 |
| `faster-whisper` (api) | `1.2.1` | MIT; model `tiny.en` (MIT weights) |
| `livekit-client` (web) | latest 2.x release at least two weeks old | Apache-2.0 |

The builder re-confirms each tag exists (`docker manifest inspect`, PyPI JSON)
before writing it, and writes the exact versions into `docker-compose.yml`,
`requirements*.txt`/lock files and the README.

### Compose topology

- One bridge network. `livekit` runs with `--config /etc/livekit.yaml`, keys from
  `LIVEKIT_API_KEY` / `LIVEKIT_API_SECRET`, `redis.address: redis:6379`, and
  `webhook: { api_key: <LIVEKIT_API_KEY>, urls: [http://api:8000/api/webhooks/livekit] }`.
- `egress` gets its config through `EGRESS_CONFIG_BODY` built from env:
  `api_key`, `api_secret`, `ws_url: ws://livekit:7880`, `redis.address`. **No B2
  credentials in the Egress service config**: each egress request carries an
  `S3Upload` built by the API (see section 3), so the endpoint and region are
  visible in audited Python code.
- `agent` (LiveKit Agents worker) connects to `ws://livekit:7880`.
- `api` publishes `8000`; the web dev server (`pnpm dev:web`) points at it via
  `NEXT_PUBLIC_API_URL=http://localhost:8000` (the Makefile sets it).
- Browser join: publish `7880/tcp`, `7881/tcp` and a small UDP range set in
  `rtc.port_range_start/end`; enable the loopback candidate so a browser on the
  host reaches the server while containers use the bridge address. The builder
  verifies the agent and egress connect inside Compose (that is what `make test`
  needs). Browser join is a human validation check; if Docker Desktop networking
  blocks it, document the exact working setting rather than changing the
  container topology.

---

## 3. B2 surface (S3-compatible API only, no b2-native calls)

Two S3 clients touch B2:

1. **Egress's built-in uploader** (Go, inside the `livekit/egress` image) does
   `PutObject` / multipart upload of the recording. It is configured per request
   with `S3Upload(access_key=B2_APPLICATION_KEY_ID, secret=B2_APPLICATION_KEY,
   region=B2_REGION, endpoint=f"https://s3.{B2_REGION}.backblazeb2.com",
   bucket=B2_BUCKET_NAME)`. This is the sample's point: Egress itself writes to
   B2. Egress does not expose a user-agent setting; the README's standards
   evidence states that, and the builder checks the `S3Upload` proto and Egress
   config for any user-agent or custom-header option and uses it if one exists.
2. **The app's single cached boto3 client** in `repo/b2_client.py`, with
   `Config(user_agent_extra="b2ai-livekit-agent-session-archive")` and the endpoint
   derived from `B2_REGION`. The agent image has no S3 client.

| S3 operation | Used for |
|---|---|
| Egress `PutObject` / multipart (Egress's client) | write `sessions/<date>/<room>/recording.ogg` |
| `put_object` | `manifest.json`, `transcript.json`, `evaluation.json`, `webhooks/<event_id>.json`, `reports/<date>.json` |
| `get_object` (streamed) | SHA-256 of the recording, transcription input, read manifests and reports |
| `head_object` | recording size and ETag check against the webhook's `size`; health probe |
| `list_objects_v2` (paginated) | session list (manifests under `sessions/`), reports list, full-bucket explorer |
| `list_object_versions` + `delete_object(VersionId=...)` | retention removal and session delete: remove every version so the bytes are actually gone, not just hidden |
| presigned GET | audio playback and downloads in the UI |

Every key is prefixed by `ARCHIVE_PREFIX` (default empty). The live test sets it to
`e2e/<run-id>/` so a test run, including its retention run, only ever touches its own
prefix in a shared bucket, and cleans that prefix up at the end.

### B2 layout

```
<ARCHIVE_PREFIX>sessions/<YYYY-MM-DD>/<room>/recording.ogg     # written by Egress
<ARCHIVE_PREFIX>sessions/<YYYY-MM-DD>/<room>/manifest.json     # written at session start, updated after
<ARCHIVE_PREFIX>sessions/<YYYY-MM-DD>/<room>/transcript.json
<ARCHIVE_PREFIX>sessions/<YYYY-MM-DD>/<room>/evaluation.json
<ARCHIVE_PREFIX>sessions/<YYYY-MM-DD>/<room>/webhooks/<event_id>.json   # raw verified webhook evidence
<ARCHIVE_PREFIX>reports/<YYYY-MM-DD>.json                      # retention report
```

Room name: `s-<YYYYMMDD>-<6 hex>`; the session id is the room name, and the date
segment is derived from it (UTC). Egress gets a literal `filepath` (no templates) so
the key is deterministic.

### Manifest (the invariant: every session has one)

Written by `POST /api/sessions` **before** Egress starts (`status: recording`), then
updated by the webhook and post-processing. Retention never deletes a manifest: it
removes the media and derivatives and marks the manifest `status: expired` with
`retention.removed_at`. Only an explicit user delete removes a session entirely.

```json
{
  "schema_version": 1,
  "session_id": "s-20261119-a1b2c3",
  "date": "2026-11-19",
  "session_class": "standard",
  "script_id": "support-handoff",
  "mode": "scripted",
  "label": "",
  "status": "recording | recorded | processed | failed | expired",
  "created_at": "...",
  "egress": { "egress_id": "...", "status": "EGRESS_COMPLETE", "started_at": "...", "ended_at": "...",
              "webhook": { "event_id": "...", "event": "egress_ended", "received_at": "...", "evidence_key": "..." } },
  "recording": { "key": "...", "location": "<file_results[0].location>", "filename": "...",
                 "size_bytes": 0, "duration_s": 0.0, "sha256": "...", "etag": "...", "content_type": "audio/ogg" },
  "transcription": { "key": "...", "model": "faster-whisper tiny.en", "device": "cpu", "language": "en", "word_count": 0 },
  "evaluation": { "key": "...", "wer": 0.0, "expected_phrases_found": 0, "expected_phrases_total": 0, "passed": true },
  "retention": { "session_class": "standard", "retain_days": 30, "retain_until": "...", "removed_at": null }
}
```

`duration_s` comes from Egress `file_results[].duration` (int64 nanoseconds,
serialized as strings in protobuf JSON; cast). The receiver also cross-checks size
with `head_object`.

### API endpoints (recorded once; routers and Pydantic models implement this, `pnpm gen:api` derives the web seam)

| Path | Method | Request model | Response model |
|---|---|---|---|
| `/api/health` | GET | none | `HealthResponse` (kept; adds LiveKit reachability) |
| `/api/files`, `/api/files/...` (kept list, detail, download, delete routes) | as in kit | as in kit | as in kit |
| `/api/stats` | GET | none | `ArchiveStats` (replaces the upload stats: sessions per class and status, recorded seconds and bytes, last report summary) |
| `/api/scripts` | GET | none | `ScriptList` (`items: ScriptInfo[]`: id, title, line count, expected duration) |
| `/api/sessions` | POST | `SessionCreate` (`script_id`, `session_class`, `mode: scripted \| interactive`, `label?`) | `SessionManifest` (201) |
| `/api/sessions` | GET | query `date?`, `session_class?`, `status?`, `cursor?`, `limit?` | `SessionList` (`items: SessionSummary[]`, `next_cursor`) |
| `/api/sessions/{session_id}` | GET | none | `SessionDetail` (`manifest`, `recording_url?`, `transcript?`, `evaluation?`) |
| `/api/sessions/{session_id}` | PATCH | `SessionUpdate` (`session_class?`, `label?`) | `SessionManifest` (recomputes `retain_until`) |
| `/api/sessions/{session_id}` | DELETE | none | 204 (all versions of every object under the session prefix) |
| `/api/sessions/{session_id}/reprocess` | POST | none | `SessionManifest` (202; reruns checksum, transcription, evaluation) |
| `/api/sessions/{session_id}/token` | POST | `JoinTokenRequest` (`identity`) | `JoinToken` (`url`, `token`, `room`) (interactive sessions only, while `status: recording`) |
| `/api/webhooks/livekit` | POST | raw body + `Authorization` header (`application/webhook+json`) | `WebhookAck` (server-only; listed in `SERVER_ONLY_OPERATIONS`) |
| `/api/retention/policy` | GET | none | `RetentionPolicy` (per class: `retain_days`, `null` = keep indefinitely) |
| `/api/retention/runs` | POST | `RetentionRunRequest` (`as_of?: date`, `dry_run: bool = true`) | `RetentionReport` |
| `/api/retention/reports` | GET | none | `RetentionReportList` |
| `/api/retention/reports/{date}` | GET | none | `RetentionReport` |

The kit's upload and presign-PUT routes are removed. Webhook handling: verify with
`WebhookReceiver(TokenVerifier(key, secret)).receive(raw_body_str, auth_header)` on
the raw body (never re-serialized); reject unsigned or mismatched bodies with 401;
dedupe by event id (retries are normal); act on `egress_started`, `egress_ended`
(and `room_finished` for status only); post-processing runs as a background task so
the webhook returns quickly.

---

## 4. Key features

No external API provider and no Genblaze (the description does not mention Genblaze,
and requires no hosted model or speech provider key). Only `B2_*` and local LiveKit
dev keys are needed.

1. **Egress recording straight to B2** · `deployment: local`. Audio-only room
   composite egress (`RoomCompositeEgressRequest(audio_only=True,
   file_outputs=[EncodedFileOutput(file_type=OGG, filepath=..., s3=S3Upload(...))])`),
   started by the API right after it creates the room and dispatches the agent. Cost:
   $0 beyond B2 storage.
2. **Minimal scripted test agent** · `deployment: local`. A LiveKit Agents 1.8.10
   worker (explicit dispatch, agent name `session-archive-test-agent`) joins the room,
   synthesizes each scripted line with the `espeak-ng` command-line synthesizer
   (installed from the distro package and run unmodified as a separate process, so no
   model weights or voice licenses are involved), publishes it through
   `rtc.AudioSource` / `LocalAudioTrack`, then closes the room in `scripted` mode. In
   `interactive` mode it greets, speaks the script with pauses, and the room closes
   when the human leaves (empty timeout). Scripts are short bundled JSON files with
   lines and expected phrases, written for the sample (no third-party data). CPU only;
   no GPU involved.
3. **Webhook receiver and per-session manifest** · `deployment: local`. Verifies the
   signed webhook, stores the raw event as evidence, records the file location from
   `file_results`, computes SHA-256 by streaming the object from B2, and writes the
   manifest.
4. **Local transcription and evaluation** · `deployment: local`. faster-whisper
   `tiny.en` (model `WHISPER_MODEL`, default `tiny.en`) transcribes the recording.
   Device: `WHISPER_DEVICE=auto` picks CUDA when available, else CPU (CTranslate2 has no
   Apple MPS backend, so Apple Silicon runs on CPU; noted in the README). Evaluation is
   deterministic: word error rate against the script plus expected-phrase coverage,
   with a pass threshold (`EVAL_MAX_WER`, default 0.5, tuned to espeak plus tiny.en).
   Cost: $0. Imports are lazy so `pytest` runs without the model.
5. **Retention by session class** · `deployment: local`. Classes and default
   `retain_days`: `debug` 1, `standard` 30, `training` 365, `hold` never. Overridable
   via `RETENTION_DAYS_DEBUG`, `RETENTION_DAYS_STANDARD`, `RETENTION_DAYS_TRAINING`.
   Runs from the UI, the API, or `make retention` (`python -m app.jobs.retention
   [--as-of YYYY-MM-DD] [--apply]`, dry run by default). Writes
   `reports/<date>.json` with kept and removed sessions per class.
6. **Session library plus full-bucket explorer** · `deployment: local`. `/sessions`
   (scoped to `sessions/`) and the kept `/files`.

### Primary-entity lifecycle

Primary entity: **Session** (schema `SessionManifest`). All five verbs are in the UI;
`omitted_ui_verbs` is empty.

| Verb | UI surface | Effect |
|---|---|---|
| create | `/sessions/new` | create room, write manifest, dispatch agent, start Egress |
| read | `/sessions` table and detail (audio player, manifest, transcript, evaluation, webhook evidence) | list manifests; presigned GET |
| edit | detail: change class or label | rewrite manifest, recompute `retain_until` |
| delete | detail and row action, confirm dialog | remove all versions under the session prefix |
| run | detail: "Reprocess" (checksum, transcription, evaluation); `/retention`: "Run retention" | rewrite derivatives and manifest; retention report |

### Form UX conventions

Exemplar: `apps/web/src/components/settings/settings-form.tsx`.

- **Create form** (`/sessions/new`): `script_id` is a `Select` fed by `/api/scripts`;
  `session_class` is a `RadioGroup` (debug, standard, training, hold) with each
  class's retention shown; `mode` is a segmented control (scripted, interactive);
  `label` is free text. Default guidance via placeholder and `FormDescription`:
  "For a first run choose the `support-handoff` script, `debug` class and `scripted`
  mode." Guidance only, no autofill button.
- **Edit form** (detail panel): opens pre-filled; `session_class` `RadioGroup`,
  `label` free text.
- **Retention run form**: `dry_run` `Switch` (on by default), optional `as_of` date
  input with "defaults to today" description.

---

## 5. Doc transforms

- **Rewrite:** `README.md` (purpose; prerequisites: Docker, a B2 bucket and key;
  quick start `cp .env.example .env`, `make up`, `make demo`; the Compose topology;
  B2 layout; manifest example; retention classes; **B2 standards audit evidence**
  with file references, including the note that Egress's Go uploader has no
  user-agent setting; pinned versions table; how `make test` works and what it
  asserts; human validation steps (join a room once, play the recording); licenses:
  LiveKit Apache-2.0, boto3 Apache-2.0, faster-whisper MIT, espeak-ng GPL-3.0 run
  unmodified as a separate program in the agent image, Redis 7.2 BSD run unmodified;
  related repositories `b2-voice-ai-reference-architectures` and
  `video-dubbing-b2-language-variants`; When to use / When not to use; FAQ).
  `ARCHITECTURE.md`, `PRODUCT.md`, `AGENTS.md` repo map, `docs/app-workflows.md`,
  `docs/dev-workflows.md` (compose workflow), `docs/SECURITY.md` (webhook signature
  verification, dev keys are local only, no compliance claims), `docs/RELIABILITY.md`
  (webhook retries and dedupe, manifest-first invariant), `docs/verification.md`
  (`make test` live suite vs offline `pnpm verify`), `docs/features/dashboard.md`.
- **Delete:** `docs/features/file-upload.md`, `docs/features/metadata-extraction.md`
  (unless metadata stays for `/files`), `infra/vercel/README.md`, `infra/railway/README.md`.
- **Keep:** `docs/features/file-browser.md`, `docs/features/settings.md`,
  `docs/design-system.md`, `docs/frontend-conventions.md`.
- **New:** `docs/features/session-recording.md`, `docs/features/webhook-manifests.md`,
  `docs/features/transcription-evaluation.md`, `docs/features/retention.md`,
  `docs/features/session-library.md`, plus `infra/livekit/README.md` (config files,
  ports, networking).
- **Out of scope here:** the PR linking this sample from
  `b2-voice-ai-reference-architectures` belongs to a later publishing step.

### Declared identity (`docs/exec-plans/sample.json`)

| Field | Value |
|---|---|
| `schema_version` | `1` |
| `name` | `LiveKit Agent Session Archive` (equals `APP_NAME`) |
| `slug` | `livekit-voice-agent-recording-retention` |
| `package_scope` | `@livekit-voice-agent-recording-retention` |
| `purpose` | Record LiveKit voice-agent sessions through Egress directly to Backblaze B2, link each recording to its transcription and evaluation in a per-session manifest, and apply retention by session class. |
| `tagline` | LiveKit Egress recordings, manifests and retention on Backblaze B2. |
| `primary_entity` | `{ "schema": "SessionManifest", "singular": "session", "plural": "sessions" }` |
| `features` | Session Recording (`/sessions/new`), Session Library (`/sessions`), Webhook Manifests (null route), Transcription and Evaluation (null route), Retention (`/retention`), File Browser (`/files`), Dashboard (`/`), Settings (`/settings`), each pointing at its doc |
| `b2_surface` | the operations in section 3, with Egress's upload listed first |
| `b2_key_prefix` | `sessions/` |
| `stack` | web: Next.js 16, React 19, Tailwind v4, shadcn/ui, TanStack Query, livekit-client; api: FastAPI, Python 3.12, boto3, livekit-api, faster-whisper; storage: Backblaze B2 (S3-compatible API), written directly by LiveKit Egress; package_manager: pnpm workspaces plus Docker Compose |
| `deployment_targets` | `[]` (Docker Compose only; see trim note) |
| `env_vars` | `B2_APPLICATION_KEY_ID`, `B2_APPLICATION_KEY`, `B2_BUCKET_NAME`, `B2_REGION` (required); `B2_PUBLIC_URL_BASE` (optional, commented in `.env.example`); `LIVEKIT_API_KEY`, `LIVEKIT_API_SECRET` (required, local dev values documented as placeholders); `LIVEKIT_URL` (internal, default `ws://livekit:7880`); `LIVEKIT_PUBLIC_URL` (browser, default `ws://localhost:7880`); `ARCHIVE_PREFIX`; `WHISPER_MODEL`; `WHISPER_DEVICE`; `EVAL_MAX_WER`; `RETENTION_DAYS_DEBUG`, `RETENTION_DAYS_STANDARD`, `RETENTION_DAYS_TRAINING`; `NEXT_PUBLIC_API_URL` |
| `attribution_token` | `b2ai-livekit-agent-session-archive` |
| `repo` | `{ "org": "backblaze-b2-samples", "name": "livekit-voice-agent-recording-retention" }` |
| `screenshots` | `[]` |

The builder writes `docs/exec-plans/sample.json` from this table as its first act,
before `pnpm gen:docs`.

### Tests

- **Offline (`pnpm verify`)**: unit tests with stubs for the manifest builder,
  webhook verification (sign real tokens with `livekit-api` and assert 401 on a
  tampered body), webhook dedupe, ns-to-seconds conversion, retention decisions per
  class at given as-of dates (including `hold` never removed and expired manifests
  kept as tombstones), egress request construction (endpoint derived from region,
  literal filepath under `ARCHIVE_PREFIX`), and evaluation WER. Contract tests stay
  green. The web keeps its unit tests for the new libs.
- **Live (`make test`)**: requires `.env` with B2 test credentials. Brings up
  Compose, sets `ARCHIVE_PREFIX=e2e/<run-id>/`, creates one `scripted` session,
  waits for `processed`, then asserts: the webhook was delivered (manifest has
  `egress.webhook` and the evidence object exists); the object exists at the
  manifest's key and the webhook location points at it; SHA-256 of the downloaded
  object equals the manifest; `size_bytes` matches `head_object`; the duration
  measured by decoding the file with PyAV (BSD) is within 1.0 s of
  `duration_s`; transcription and evaluation exist and evaluation passed. Retention:
  seed fixture manifests (with small placeholder recordings) for all four classes
  with backdated `ended_at` under the same run prefix, run retention with an as-of
  date, assert which are removed and kept per class, that removed sessions keep an
  `expired` manifest, and that `reports/<date>.json` matches. Finally deletes the run
  prefix. `make demo` runs one scripted session and prints its manifest.
- B2 standards: run `/b2-doctor` and paste the evidence into the README.

---

## 6. Rename table

| From | To |
|---|---|
| `vibe-coding-starter-kit` (package names, workspace filters, URLs, slugs) | `livekit-voice-agent-recording-retention` (repo URLs use `livekit-voice-agent-recording-retention`) |
| `@vibe-coding-starter-kit/web`, `@vibe-coding-starter-kit/shared` | `@livekit-voice-agent-recording-retention/web`, `@livekit-voice-agent-recording-retention/shared` |
| `vibe_coding_starter_kit` (snake, if present) | `livekit_voice_agent_recording_retention` |
| `Vibe Coding Starter Kit` (`APP_NAME`; API title, localStorage namespace and CORS rule id derive from it) | `LiveKit Agent Session Archive` |
| `APP_DESCRIPTION` | `Voice-agent session recordings, manifests and retention on Backblaze B2` |
| `b2ai-oss-start` (S3 `user_agent_extra`, every `utm_content`, sidebar link) | `b2ai-livekit-agent-session-archive` |
| Image tags and workflow names using the old slug | `livekit-voice-agent-recording-retention` |
| Any non-standard B2 env names left in the kit | `B2_APPLICATION_KEY_ID`, `B2_APPLICATION_KEY`, `B2_BUCKET_NAME`, `B2_REGION`, `B2_PUBLIC_URL_BASE` (endpoint derived from `B2_REGION`, no hardcoded region) |

---

## Implementation notes

- **Must not change:** Egress itself writes recordings to B2 (the API never re-uploads
  a recording), and every session has a manifest from the moment it is created.
- The S3 `S3Upload` request carries B2 credentials from the API to LiveKit over the
  local Compose network only; document this and keep LiveKit ports other than signal
  and media unpublished.
- The `api` image installs `faster-whisper` and `av`; host `pytest` must not need
  them (lazy imports, stubs).
- Out of scope: hosted model or speech providers, a production agent, call-center
  integrations, compliance claims.
- No binary assets (screenshots, audio files) are created in this step; scripts are
  text and audio is synthesized at run time.
- Backend invariants from the kit: boto3 only in `repo/`; `livekit-api` only in
  `repo/`; files under 300 lines; Pydantic at boundaries; contract re-exported on
  every route change.

## Changes made during the initial build

- `slug` is `livekit-agent-session-archive` and the root package name matches it:
  the docs generator derives the slug from `APP_NAME`, and the UTM check requires
  `utm_content=b2ai-livekit-agent-session-archive`. The workspace scope stays
  `@livekit-voice-agent-recording-retention/*`.
- `scripts/gen-docs.mjs` generates a deployment guide only for declared targets, so
  `deployment_targets: []` works without the Vercel and Railway guides.
- Metadata extraction stays because the `/files` preview uses it.
- A dry retention run writes no report; only an applied run writes
  `reports/<date>.json`.
- Egress's uploader has no user-agent setting, so each recording carries object
  metadata `source=b2ai-livekit-agent-session-archive` instead.
