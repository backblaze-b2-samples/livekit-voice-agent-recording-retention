<!-- last_verified: 2026-11-19 -->
# Feature: Webhook Manifests

## Purpose
Keep each session's `manifest.json` in B2 current from LiveKit's signed webhooks, and keep the raw webhook as evidence of where Egress put the file.

## Used By
- API: `POST /api/webhooks/livekit` (server-only; listed in `serverOnly` in `scripts/gen/api-gen.config.json`)
- Caller: the LiveKit server (`webhook.urls` in `infra/livekit/livekit.yaml`)

## Core Functions
- `services/api/app/runtime/webhooks.py`: reads the raw body, maps verification failures to 401, schedules post-processing
- `services/api/app/service/webhooks.py`: `receive`, dedupe, `_apply`
- `services/api/app/repo/livekit_api.py`: `verify_webhook` (`WebhookReceiver(TokenVerifier(key, secret)).receive(body, auth)`)
- `services/api/app/service/manifests.py`: `session_lock`, `retention_for`, `ns_to_seconds`

## Canonical Files
- Pattern exemplar: `services/api/app/service/webhooks.py`

## Inputs
- Raw body (`application/webhook+json`), never re-serialized before verification
- `Authorization`: JWT signed with `LIVEKIT_API_SECRET` whose `sha256` claim is the base64 SHA-256 of the body

## Outputs
- `WebhookAck` (`received`, `event`, `duplicate`)
- Side effects: `sessions/<date>/<room>/webhooks/<event_id>.json` (the verified body, byte for byte); manifest updates; a background post-processing task after a complete `egress_ended`

## Flow
- Verify the token and body hash; 401 when missing, unsigned, signed with another secret, or tampered
- Ignore events for rooms this app did not create (room name must match `s-<YYYYMMDD>-<6 hex>` and have a manifest)
- Act on `egress_started`, `egress_updated`, `egress_ended`; store `room_finished` as evidence only
- Dedupe by event id: in memory, and across restarts by the evidence object already being in B2
- Store the evidence, then under the per-session lock update `egress.*` and `egress.webhook`
- On `egress_ended` with `EGRESS_COMPLETE`: copy `file_results[0]` (`location`, `filename`, `size`, `duration` in ns -> seconds), set status `recorded`, re-anchor `retain_until` on the end time, schedule post-processing
- On any other end status: set status `failed` with Egress's error

## Edge Cases
- Duplicate delivery -> `duplicate: true`, no second write, post-processing scheduled once
- Evidence write fails -> the event id is forgotten so LiveKit's retry is processed
- `location` does not end with the expected key -> logged as a warning, manifest keeps both
- `duration` arrives as a string in protobuf JSON -> parsed through the proto, converted with `ns_to_seconds`

## Verification
- Test files: `services/api/tests/test_webhooks.py`
- Required cases: real signature accepted; tampered body 401; unsigned and wrong-secret 401; retry deduplicated; dedupe survives restart; failed Egress marks `failed`; foreign rooms ignored
- Focused verify command: `cd services/api && .venv/bin/python -m pytest tests/test_webhooks.py`
- Default pre-PR verify command: `pnpm verify`
- Pass criteria: all of the above green; live suite finds `egress.webhook` and its evidence object

## Related Docs
- [docs/SECURITY.md](../SECURITY.md)
- [docs/RELIABILITY.md](../RELIABILITY.md)
- [ARCHITECTURE.md](../../ARCHITECTURE.md)
