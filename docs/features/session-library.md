<!-- last_verified: 2026-11-19 -->
# Feature: Session Library

## Purpose
Browse, play, edit, reprocess and delete archived sessions: the sample's own explorer, scoped to the `sessions/` prefix (the full-bucket explorer stays at `/files`).

## Used By
- UI: `/sessions` (table), `/sessions/[sessionId]` (detail)
- API: `GET /api/sessions`, `GET /api/sessions/{session_id}`, `PATCH /api/sessions/{session_id}`, `DELETE /api/sessions/{session_id}`, `POST /api/sessions/{session_id}/reprocess`

## Core Functions
- `services/api/app/service/sessions.py`: `list_sessions`, `get_detail`, `update_session`, `delete_session`, `prepare_reprocess`
- `services/api/app/service/manifests.py`: `list_manifest_keys`, `summary`
- `apps/web/src/components/sessions/sessions-table.tsx`, `session-detail.tsx`, `session-evidence.tsx`, `session-edit-form.tsx`
- `apps/web/src/lib/queries.ts`: `useSessions`, `useSession`, `useUpdateSession`, `useDeleteSession`, `useReprocessSession`

## Canonical Files
- Pattern exemplar: `apps/web/src/components/sessions/session-detail.tsx`

## Inputs
- List: `date`, `session_class`, `status`, `cursor` (a session id), `limit` (1 to 200, default 50)
- Edit: `session_class`, `label`

## Outputs
- `SessionList` (`items`, `next_cursor`); `SessionDetail` (manifest, presigned `recording_url`, transcript, evaluation, webhook evidence)
- Side effects: edit rewrites the manifest; delete removes every version under the session prefix; reprocess schedules post-processing (202)

## Flow
- List manifest keys under `sessions/` (one paginated `list_objects_v2`), newest first by session id; load manifests in parallel batches until the page is filled
- Detail adds a 15-minute inline presigned GET when the recording exists
- Delete stops a live room first, then deletes all versions

## Edge Cases
- Malformed or unknown session id -> 404 (ids are validated before any key is built)
- Changing the class of an expired session -> 409
- Reprocess while recording, expired, or before the recording is in B2 -> 409
- Recording sessions refresh on their own until settled

## UX States (if applicable)
- Empty: "No sessions match" with a link to `/sessions/new`
- Loading: skeleton rows
- Error: `ErrorState` with Retry

## Verification
- Test files: `services/api/tests/test_sessions_api.py`, `apps/web/src/lib/session-format.test.ts`, `apps/web/src/lib/session-schema.test.ts`, `apps/web/src/lib/queries.test.ts`
- Focused verify command: `cd services/api && .venv/bin/python -m pytest tests/test_sessions_api.py`
- Default pre-PR verify command: `pnpm verify`
- Pass criteria: list, filter, cursor paging, detail, patch, delete and reprocess cases green

## Related Docs
- [File Browser](file-browser.md)
- [Retention](retention.md)
