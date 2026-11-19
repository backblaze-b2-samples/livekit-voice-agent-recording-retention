<!-- last_verified: 2026-11-19 -->
# Security

Security principles and implementation for the LiveKit Agent Session Archive.
This is a local demo. It makes no compliance claims: retention here is a cost
and hygiene policy, not a legal-hold, consent or PII-redaction control.

## Trust Boundaries

- **Browser -> API**: CORS-restricted to localhost origins (the Compose `api` service sets `^http://localhost:[0-9]+$`), methods `GET/POST/PATCH/DELETE/OPTIONS`. `allow_credentials` is `False`.
- **LiveKit -> API**: the webhook route accepts only signed bodies (see below).
- **API -> LiveKit**: server API calls signed with `LIVEKIT_API_KEY` / `LIVEKIT_API_SECRET`.
- **API -> B2**: `B2_APPLICATION_KEY_ID` + `B2_APPLICATION_KEY`, signature v4.
- **API -> Egress -> B2**: each Egress request carries an `S3Upload` with the B2 key. It travels from the API to LiveKit and Egress over the private Compose network only; Redis and Egress publish no host ports.
- **Browser -> B2**: presigned GET only (inline for playback, attachment for downloads, 10 to 15 minutes).

## Webhook Signature Verification

- `POST /api/webhooks/livekit` reads the **raw body** and verifies it with `WebhookReceiver(TokenVerifier(key, secret)).receive(body, authorization)` (`services/api/app/repo/livekit_api.py`). The JWT in `Authorization` must be signed with `LIVEKIT_API_SECRET` and its `sha256` claim must equal the SHA-256 of the exact body.
- Missing, unsigned, wrong-secret and tampered bodies get `401` and change nothing. Tests sign real tokens and tamper with the body (`tests/test_webhooks.py`).
- Only rooms this app created (`s-<YYYYMMDD>-<6 hex>` with an existing manifest) are acted on.
- The verified body is stored unchanged as evidence (`webhooks/<event_id>.json`).

## LiveKit Dev Keys

- `LIVEKIT_API_KEY` / `LIVEKIT_API_SECRET` exist for the local Compose stack only. Pick your own values; never reuse them on a reachable server.
- They reach the containers as environment variables from `.env` (`LIVEKIT_KEYS`, `LIVEKIT_WEBHOOK_API_KEY`, `EGRESS_CONFIG_BODY`); `infra/livekit/livekit.yaml` holds no secret.
- Browser join tokens are scoped to one room, valid for 30 minutes, and minted only for `interactive` sessions that are still recording.

## Authentication & Multi-Tenancy

- **No auth by design.** Every `/api` route is unauthenticated: anyone who can reach port 8000 can create sessions, delete them, run retention and browse the whole bucket. Keep the stack on your machine.
- Adding auth to a clone must cover every route and scope listings to the caller's own prefixes; a login screen alone is not enough. See the notes in `runtime/files.py` and `runtime/sessions.py`.

## Input Validation

- Session ids must match `s-<YYYYMMDD>-<6 hex>` before any B2 key is built from them, so a crafted id cannot address another prefix.
- Request bodies are Pydantic models (`SessionCreate`, `SessionUpdate`, `JoinTokenRequest`, `RetentionRunRequest`); classes and modes are closed sets.
- Egress gets a literal file path built by the API; no LiveKit filename templates.

## Rate Limiting

- Per-IP fixed-window limiter (`app/runtime/ratelimit.py`), configurable via `RATE_LIMIT_PER_MINUTE` (reads) and `RATE_LIMIT_WRITE_PER_MINUTE` (creates, edits, deletes, downloads, previews). The LiveKit webhook route is exempt: the server is one trusted client that sends every room event.
- In-process, per replica; see [RELIABILITY.md](RELIABILITY.md).

## File Key Validation

- Empty keys and path traversal patterns (`../`, `%2e%2e`, backslashes, null bytes) are rejected on the `/api/files` routes.
- Optional prefix confinement: `ALLOWED_KEY_PREFIX` restricts key-addressed reads and deletes when the bucket is shared.

## Response Hardening

- Interactive API docs (`/docs`, `/redoc`, `/openapi.json`) are on by default; set `ENABLE_DOCS=false` to hide them.

## CI Permissions

- `.github/workflows/ci.yml` sets `permissions: contents: read` at the workflow level, so `GITHUB_TOKEN` is read-only in every job. Widen per job, never at the top level.

## Secrets Management

- All secrets are loaded from environment variables (pydantic-settings, Compose `env_file`).
- Never committed to source control; `.env.example` documents the variables with placeholders.
- Container images contain no secrets; they are injected at `docker compose up`.

## Dependency and Secret Detection

- [`.github/dependabot.yml`](../.github/dependabot.yml) opens weekly update PRs for the pnpm workspace and `services/api` Python dependencies. Image tags in `docker-compose.yml` and the agent's `requirements.txt` are pinned by hand; bump them deliberately.
- [`.pre-commit-config.yaml`](../.pre-commit-config.yaml) runs a pinned `detect-secrets` hook against staged changes.
- GitHub secret scanning and push protection are provider-level settings an administrator enables; do not represent them as enabled until confirmed.

## Agent Security Rules

- Never commit `.env`, credentials, or API keys
- Never print them either: the canonical rule lives in
  [AGENTS.md §12, Secret Handling](../AGENTS.md#12-secret-handling) (agents
  read AGENTS.md first); don't restate it here. The link is anchored and
  `pnpm check:agent-docs` verifies that it still resolves.
- The user request and trusted repository instructions are authoritative; see
  [AGENTS.md, Instruction Authority](../AGENTS.md#instruction-authority).
- Never weaken webhook verification or input validation without explicit instruction
- Always validate at system boundaries
