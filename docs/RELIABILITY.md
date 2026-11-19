<!-- last_verified: 2026-11-19 -->
# Reliability

Reliability expectations and practices for the session archive.

## Invariants

- **Manifest first.** `POST /api/sessions` writes `manifest.json` (status `recording`) before Egress starts. If dispatch or Egress start fails, the manifest stays with status `failed` and the reason, so no session exists without a record.
- **Retention keeps the record.** Retention deletes media and derivatives, never the manifest or the webhook evidence; the manifest becomes an `expired` tombstone with `retention.removed_at`. Only an explicit session delete removes everything.
- **Egress owns the recording.** The API never re-uploads audio, so there is one writer for `recording.ogg`.

## Webhook Retries and Dedupe

- LiveKit retries a webhook it could not deliver; the same event id can arrive more than once, and `egress_started` / `egress_ended` can arrive close together.
- Dedupe: recent event ids are kept in memory (bounded at 4096) and, across API restarts, an event whose evidence object (`webhooks/<event_id>.json`) already exists in B2 is a duplicate. Duplicates return `200` with `duplicate: true` and change nothing.
- If storing the evidence or the manifest fails, the event id is forgotten so LiveKit's retry is processed.
- Manifest read-modify-write cycles (create, webhooks, post-processing, edits, retention) are serialized per session with an in-process lock, and `create_session` merges the Egress id into whatever a webhook already wrote instead of overwriting it.
- Post-processing runs as a FastAPI background task after the webhook returns, so LiveKit never times out waiting on transcription. A failure there marks the session `failed` with the error; "Reprocess" runs it again.

## Health Checks

- `GET /api/health` reports `b2_connected` and `livekit_connected` and returns `healthy` or `degraded` (HTTP 200 either way). Both checks are cached for 5 seconds.
- The B2 client bounds connection attempts to 5 seconds, socket reads to 30 seconds, and standard retries to 3 total attempts. LiveKit server calls time out after 10 seconds (2 for the health probe).
- `make up` waits for Compose health checks (`redis-cli ping`, `GET /api/health`).

## Error Handling

- HTTP handlers return structured error responses: 400 bad input, 401 bad webhook signature, 404 unknown session, 409 wrong state, 502 LiveKit or storage failure.
- Uncaught exceptions are converted to a typed JSON 500 (`{"detail": "Internal server error"}`) by the catch-all in `timing_middleware`.
- **Error responses carry CORS headers.** `CORSMiddleware` is registered last in `main.py`, so it is outermost and wraps every response, including uncaught-exception 500s. Without that the browser would hide the real error behind an opaque network failure. Regression-guarded by `tests/test_error_handling.py`.

## Logging

- Structured JSON logging via Python stdlib, with a `request_id` per request.
- Session creation, every stored webhook, post-processing results and retention runs are logged at INFO; rejected webhooks and size mismatches at WARNING.

## Observability

- `/metrics` (Prometheus format): request counts and durations, `webhooks_total`, `webhook_errors_total`.
- `make logs` follows every Compose service, including Egress upload errors.

## Stateful Counters: durability caveats

- Webhook dedupe ids, the `/metrics` counters, rate-limit windows and the per-session locks live in process memory and reset on restart. The API runs as one process, which is what the per-session lock assumes; running several API replicas needs a shared lock (for example in Redis) before it is safe.
- Durable state is only what is in B2: manifests, derivatives, evidence and reports.

## Rate Limiting

- Per-IP fixed-window limiter (`app/runtime/ratelimit.py`); rejected requests get `429` with `Retry-After`. The webhook route is exempt.

## Graceful Degradation

- The session list and stats read manifests in parallel batches; a missing manifest is skipped, not an error.
- The `/files` listing is cached, warmed at startup and served stale-while-revalidate (`LIST_CACHE_TTL_SECONDS`, default 300). Recordings written by Egress appear after the next refresh or after any app write invalidates the cache.
- The UI shows worded loading states and inline errors with Retry, and polls sessions until they settle.

## Deployment

- Docker Compose only. Image tags are pinned (`docker-compose.yml`); after changing one, run `docker compose down` and `make up` again.
- Environment-specific configuration comes from `.env`; no values are committed.
