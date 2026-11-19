<!-- last_verified: 2026-11-19 -->
# Feature: Retention

## Purpose
Keep or remove each session according to its class, free the bytes of what is removed, and leave a per-day report and a tombstone manifest behind.

## Used By
- UI: `/retention` (policy, run form, reports list)
- API: `GET /api/retention/policy`, `POST /api/retention/runs`, `GET /api/retention/reports`, `GET /api/retention/reports/{day}`
- Job: `python -m app.jobs.retention [--as-of YYYY-MM-DD] [--apply]` (`make retention`, `make retention-apply`)

## Core Functions
- `services/api/app/service/retention.py`: `policy`, `decide`, `run`, `list_reports`, `get_report`
- `services/api/app/repo/session_store.py`: `delete_all_versions`
- `services/api/app/jobs/retention.py`: CLI
- `apps/web/src/components/retention/retention-panel.tsx`

## Canonical Files
- Pattern exemplar: `services/api/app/service/retention.py`

## Inputs
- `as_of`: optional date (default today, UTC)
- `dry_run`: boolean (default `true`)
- `RETENTION_DAYS_DEBUG` (1), `RETENTION_DAYS_STANDARD` (30), `RETENTION_DAYS_TRAINING` (365); `hold` is never removed

## Outputs
- `RetentionReport`: per class, the kept, removed and already-expired session ids; totals; bytes removed
- Side effects (applied runs only): every version of `recording.ogg`, `transcript.json`, `evaluation.json` deleted for each removed session; manifest set to `expired` with `retention.removed_at`; `reports/<as_of>.json` written

## Flow
- Load every manifest under `sessions/`
- `decide`: `expired` manifests are counted as already expired; `hold` and in-progress `recording` sessions are kept; otherwise remove when `retain_until` (end of recording + class days) falls on or before `as_of`
- Dry run: return the report, touch nothing
- Applied: delete versions, rewrite the manifest, write the report

## Edge Cases
- Re-running the same day -> previously removed sessions appear under `already_expired`; the report for that date is overwritten by the newer applied run, and the "Reports in B2" row is replaced in the client cache as soon as the run returns (`recordAppliedReport`), then refetched
- Each report key on `/retention` links to its preview on `/files` (`/files?preview=<key>`), where the JSON renders inline
- A class change after recording -> `retain_until` recomputed from the recording's end
- Versioned bucket -> deleting by version id removes the data, not just a delete marker
- `ARCHIVE_PREFIX` set -> retention only sees sessions under that prefix

## UX States (if applicable)
- Empty: "No applied runs yet"
- Loading: skeletons; run button reads "Running..." with `aria-busy` and a `role="status"` label
- Error: toast with the API detail

## Verification
- Test files: `services/api/tests/test_retention.py`, `services/api/live_tests/test_session_archive_e2e.py::test_retention_by_class`
- Required cases: decision per class at given as-of dates; `hold` never removed; expired manifests stay tombstones; dry run changes nothing; applied run removes media, keeps manifest and evidence, writes the report
- Focused verify command: `cd services/api && .venv/bin/python -m pytest tests/test_retention.py`
- Default pre-PR verify command: `pnpm verify`
- Full local verify command: `make test`
- Pass criteria: offline green; live suite removes exactly the backdated fixtures

## Related Docs
- [Session Library](session-library.md)
- [docs/RELIABILITY.md](../RELIABILITY.md)
