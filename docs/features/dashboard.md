<!-- last_verified: 2026-11-19 -->
# Feature: Dashboard

## Purpose
Give an at-a-glance view of the session archive: how many sessions per class and status, how much audio is stored, how evaluations went, and when retention last ran.

## Used By
- UI: `/` page (dashboard home)
- API: `GET /api/stats`, `GET /api/retention/policy`

## Core Functions
- `apps/web/src/components/dashboard/stats-cards.tsx`: four stat cards
- `apps/web/src/components/dashboard/class-breakdown.tsx`: sessions per class (with retention) and per status
- `apps/web/src/components/dashboard/recent-sessions-table.tsx`: the five newest sessions
- `apps/web/src/lib/queries.ts`: `useArchiveStats` (polls every 15 s)
- `services/api/app/service/stats.py`: `archive_stats`

## Canonical Files
- Pattern exemplar: `services/api/app/service/stats.py`

## Inputs
- None (reads every manifest under `sessions/` and the reports list)

## Outputs
- `ArchiveStats`: `total_sessions`, `by_class`, `by_status`, `recorded_seconds`, `recorded_bytes(_human)` (sessions not expired), `passed_evaluations`, `last_report`, `recent_sessions`

## Flow
- The API lists and loads the manifests, aggregates them and reads the newest report summary
- The page renders cards, the class/status breakdown and the recent table

## Edge Cases
- No sessions -> zeros and an empty-state table
- API unreachable -> inline `ErrorState` with Retry instead of zeros
- Expired sessions count in totals and statuses but not in recorded minutes or bytes

## UX States (if applicable)
- Empty: "No sessions yet"
- Loading: worded loading notice plus skeletons
- Error: `ErrorState`

## Verification
- Test files: `services/api/tests/test_error_handling.py::test_stats_b2_failure_returns_500`, `apps/web/src/lib/session-format.test.ts`
- Default pre-PR verify command: `pnpm verify`
- Pass criteria: stats endpoint returns a typed 500 on B2 failure; formatting helpers green

## Related Docs
- [docs/app-workflows.md](../app-workflows.md)
- [ARCHITECTURE.md](../../ARCHITECTURE.md)
