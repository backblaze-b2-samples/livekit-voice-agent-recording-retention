<!-- last_verified: 2026-11-19 -->
# Feature: Session Recording

## Purpose
Start a voice-agent session whose audio LiveKit Egress records and uploads directly to Backblaze B2, with a manifest in B2 from the first moment.

## Used By
- UI: `/sessions/new` (create form), `/sessions/[sessionId]` (join panel for interactive sessions)
- API: `POST /api/sessions`, `GET /api/scripts`, `POST /api/sessions/{session_id}/token`
- Job: the `agent` Compose service (`services/agent/agent.py`)

## Core Functions
- `services/api/app/service/sessions.py`: `create_session`, `join_token`
- `services/api/app/repo/livekit_api.py`: `create_room`, `dispatch_agent`, `start_egress`, `build_egress_request`, `build_s3_upload`, `create_join_token`
- `services/api/app/service/layout.py`: session id and key layout
- `services/agent/agent.py`: the scripted test agent (espeak-ng synthesis, `rtc.AudioSource`)
- `apps/web/src/components/sessions/session-create-form.tsx`, `join-panel.tsx`

## Canonical Files
- Pattern exemplar: `services/api/app/repo/livekit_api.py` (every LiveKit call, contained in `repo/`)

## Inputs
- `script_id`: string, one of the bundled scripts in `services/agent/scripts/*.json`
- `session_class`: `debug | standard | training | hold` (default `debug`)
- `mode`: `scripted | interactive` (default `scripted`)
- `label`: optional string, max 120 characters

## Outputs
- `SessionManifest` (201) with status `recording` and `egress.egress_id`
- Side effects: a LiveKit room named `s-<YYYYMMDD>-<6 hex>`; `sessions/<date>/<room>/manifest.json` in B2; an agent dispatch; an audio-only room composite Egress whose OGG file is uploaded by Egress to `sessions/<date>/<room>/recording.ogg`

## Flow
- Validate the script exists (400 otherwise, nothing created)
- Create the room (empty timeout 60 s, metadata names the script and mode)
- Write the manifest with status `recording` (the manifest-first invariant)
- Dispatch `session-archive-test-agent` with the same metadata
- Start Egress: `RoomCompositeEgressRequest(audio_only=True, file_outputs=[EncodedFileOutput(file_type=OGG, filepath=<literal key>, disable_manifest=True, s3=S3Upload(...))])`. The `S3Upload` carries the B2 key, `region=B2_REGION`, `endpoint=https://s3.<B2_REGION>.backblazeb2.com`, the bucket, path-style addressing and object metadata `source=b2ai-livekit-agent-session-archive`
- Merge the Egress id into the manifest (a webhook may already have updated it)
- The agent joins, waits until the room's Egress is `EGRESS_ACTIVE`, speaks each line, then deletes the room (scripted) or waits for the human to leave (interactive, up to 10 minutes)

## Edge Cases
- LiveKit unreachable when creating the room -> 502, no session exists
- Dispatch or Egress start fails -> 502, the manifest stays with status `failed` and the reason, and the room is deleted
- Join token for a scripted session, or after the room closed -> 409
- Nobody joins an interactive session within 2 minutes -> the agent closes the room after speaking

## UX States (if applicable)
- Defaults: once the scripts load, the form preselects `support-handoff` (else the first bundled script), so Start works without touching the form
- Loading: script select shows "Loading scripts..."; submit reads "Starting room and Egress..."
- Error: toast with the API's detail
- Success: toast, then redirect to the session page, which polls until settled

## Verification
- Test files: `services/api/tests/test_sessions_api.py`, `services/api/tests/test_layout_and_egress.py`, `services/api/live_tests/test_session_archive_e2e.py`
- Required cases: manifest written before Egress starts; unknown script is 400; failed Egress start leaves a `failed` manifest; Egress endpoint derived from region; literal file path under `ARCHIVE_PREFIX`
- Focused verify command: `cd services/api && .venv/bin/python -m pytest tests/test_sessions_api.py tests/test_layout_and_egress.py`
- Default pre-PR verify command: `pnpm verify`
- Full local verify command: `make test` (live, needs Docker and B2 credentials)
- Pass criteria: offline tests green; live suite reaches `processed` with the recording at the manifest's key

## Related Docs
- [README.md](../../README.md)
- [ARCHITECTURE.md](../../ARCHITECTURE.md)
- [docs/app-workflows.md](../app-workflows.md)
- [infra/livekit/README.md](../../infra/livekit/README.md)
