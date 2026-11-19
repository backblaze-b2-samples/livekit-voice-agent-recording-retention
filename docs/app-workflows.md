<!-- last_verified: 2026-11-19 -->
# App Workflows

User journeys inside the application. Every journey assumes the Compose stack is
up (`make up`) and the UI runs on the host (`make web`).

## Record a Session

- User opens `/sessions/new` (sidebar "New session", or "New session" on the dashboard)
- Picks a **script** from a select fed by `GET /api/scripts`; the description suggests `support-handoff`, `debug` and `scripted` for a first run (guidance only, nothing is pre-selected)
- Picks a **session class** from a radio group; each option shows how long that class is kept
- Picks a **mode** with a segmented control: `scripted` (the agent speaks and closes the room) or `interactive` (the user joins with the browser microphone)
- Optionally types a label, then "Start session"
- The API creates the room, writes `manifest.json` with status `recording`, dispatches the test agent and starts an audio-only Egress; the user lands on the session page
- Scripted: the page polls every 3 seconds and moves `recording` -> `recorded` (Egress finished, webhook received) -> `processed` (checksum, transcript and evaluation written), usually within a minute
- Interactive: the session page shows "Join with microphone"; the user talks, then "Leave room"; the agent closes the room and the same status sequence follows
- If LiveKit is unreachable the create fails with a toast; if Egress could not start, the session still exists with status `failed` and the reason
- See: [Session Recording](features/session-recording.md)

## Review a Session

- User opens `/sessions`: a table of sessions (newest first) with created time, class, status, duration, size and WER, filterable by class and status, paged with "Newer" / "Older"
- Rows still recording refresh on their own until they settle
- Opening a session shows an audio player (presigned GET), duration, size, Egress status, WER, the recording key (linked to its preview on `/files`) and SHA-256
- Tabs show the transcript with timestamps, the evaluation (WER, expected phrases found and missing, reference text), the stored webhook evidence and the raw manifest
- "Class and retention" shows the policy and `retain_until`; the edit form opens pre-filled, and saving a new class recomputes `retain_until`
- "Reprocess" reruns checksum, transcription and evaluation (enabled once a recording exists)
- "Delete" asks for confirmation, then removes every version of every object under the session prefix and returns to the list
- See: [Session Library](features/session-library.md)

## Apply Retention

- User opens `/retention`: the per-class policy, a "Run retention" form and the list of reports in B2
- The form has a **dry run** switch (on by default) and an optional **as of** date (defaults to today, UTC)
- A dry run shows what would be removed and kept per class, and deletes nothing
- An applied run deletes every version of each expired session's recording, transcript and evaluation, marks its manifest `expired`, writes `reports/<date>.json`, and the new report appears in the list
- Removed session ids link to their (now expired) session pages
- The same run is available from the CLI: `make retention` / `make retention-apply`
- See: [Retention](features/retention.md)

## Browse the Bucket

- User opens `/files`: the full-bucket explorer, as a folder tree (`sessions/<date>/<room>/...`, `reports/`, and anything else in the bucket)
- Clicking a file opens its preview (audio and JSON included) with download and delete actions; the session page links straight to its recording here
- Deleting a single object here does not update any manifest; to remove a session, delete it from its session page
- See: [File Browser](features/file-browser.md)

## View Dashboard

- User navigates to `/` (home)
- Stat cards: total sessions, recorded minutes and bytes (sessions not expired), passed evaluations, and the last applied retention run
- "Sessions by class and status": a bar per class with its count and retention, and a count per status
- "Recent sessions": the five newest sessions, each linking to its page
- The figures poll every 15 seconds, so a session recorded with `make demo` appears without a refresh
- If the API is down, the cards show an inline error with Retry instead of zeros
- See: [Dashboard](features/dashboard.md)

## Change Preferences

- User navigates to `/settings`
- A banner at the top states that the page is mostly a demonstration: only Theme is wired up for real
- **Theme** (real): saving applies it immediately and persists it (`next-themes`); the header toggle drives the same state
- **Profile and preference fields** (demo): each is labelled "Demo field", persists to `localStorage` only, and drives no behaviour
- Danger Zone actions are a demo; no real delete runs
- See: [Settings](features/settings.md)
