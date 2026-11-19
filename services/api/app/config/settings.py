import json
from pathlib import Path

from pydantic_settings import BaseSettings

# The B2 configuration contract, declared once as data. `scripts/doctor.mjs`
# parses this same file, so the preflight check cannot drift from the server it
# is checking (it used to keep its own copy behind a "keep in sync" comment).
# The file sits inside this package, so it ships with every deploy shape
# (Railway and Vercel both root at services/api) rather than needing a repo root.
_B2_VARS_PATH = Path(__file__).resolve().parent / "b2_required_vars.json"
_B2_VARS = json.loads(_B2_VARS_PATH.read_text(encoding="utf-8"))

# (settings attribute, env var name) pairs the server refuses to start without.
REQUIRED_B2_SETTINGS: tuple[tuple[str, str], ...] = tuple(
    (entry["setting"], entry["env"]) for entry in _B2_VARS["required"]
)
# The exact placeholder strings .env.example ships. A copied-but-unedited file
# passes the "non-empty" check above and then 403s on every B2 call.
PLACEHOLDER_VALUES: frozenset[str] = frozenset(
    entry["placeholder"] for entry in _B2_VARS["required"] if entry.get("placeholder")
)


class Settings(BaseSettings):
    # Standard B2 names (B2_APPLICATION_KEY_ID, B2_APPLICATION_KEY,
    # B2_BUCKET_NAME, B2_REGION, B2_PUBLIC_URL_BASE) bind case-insensitively to
    # these fields. Declared with empty defaults so importing the app never
    # raises; main.py fails fast at startup instead.
    b2_application_key_id: str = ""
    b2_application_key: str = ""
    b2_bucket_name: str = ""
    b2_region: str = ""
    b2_public_url_base: str = ""

    # Slug for anything that must be namespaced per app. Python cannot import
    # the frontend's app-config.ts, so this is the backend's declaration of the
    # same slug: keep it equal to the package name.
    app_slug: str = "livekit-voice-agent-recording-retention"

    api_port: int = 8000
    # Interactive API docs (/docs, /redoc, /openapi.json). On by default for
    # local dev and starter-kit exploration; set false to hide the full API
    # surface in production.
    enable_docs: bool = True
    # Explicit allowlist by default: covers Next on :3000 and the
    # fallback :3001 it picks if 3000 is busy. Production deploys should
    # override with the exact frontend origin.
    api_cors_origins: str = "http://localhost:3000,http://localhost:3001"
    # Optional dev-only escape hatch: a regex that matches additional
    # allowed origins. Empty by default — set this to e.g.
    # `^http://localhost:\d+$` to accept any localhost port without
    # listing each one. NEVER ship this to production.
    api_cors_origin_regex: str = ""

    # Ceiling for the /files detail recompute, which buffers the whole object.
    max_file_size: int = 100 * 1024 * 1024  # 100MB

    # Optional confinement for key-addressed reads/deletes. Empty by default so
    # the by-key routes accept any key shape (they deliberately support nested
    # folders and reserved-word segments). Point a fork at a bucket shared with
    # other data? Set to e.g. "uploads/" to restrict all key ops to app uploads.
    allowed_key_prefix: str = ""

    # Full-bucket listing cache (repo/list_cache.py). Both /files and
    # /files/stats need every object, and paginating a 16k-object bucket takes
    # ~8-20s, so one scan is shared. Entries older than the TTL are still
    # served *immediately* while a background thread refreshes them
    # (stale-while-revalidate), so only the very first scan can make a user
    # wait. Uploads and deletes invalidate the cache outright, so the app's own
    # writes are never served stale; only bucket changes made elsewhere (such as
    # an Egress upload) can lag by up to this TTL.
    list_cache_ttl_seconds: float = 300.0
    # Scan the bucket once at startup so the first page view doesn't pay for the
    # cold scan. Set false for offline dev or when startup must not touch B2.
    warm_list_cache_on_startup: bool = True

    # Rate limiting (per client IP, per 60s window). In-process per replica —
    # documented in docs/RELIABILITY.md; horizontal scaling needs a shared
    # store (e.g. Redis). Writes/downloads get the tighter cap.
    rate_limit_per_minute: int = 120
    # Covers creates, deletes, downloads and previews; kept generous enough
    # that a normal browsing session doesn't trip it.
    rate_limit_write_per_minute: int = 60

    # --- LiveKit (local Compose stack) ---
    # Dev keys shared by the server, Egress, the agent and this API. They never
    # leave the Compose network except as signed room tokens.
    livekit_api_key: str = ""
    livekit_api_secret: str = ""
    # Where this API reaches the LiveKit server (inside Compose).
    livekit_url: str = "ws://livekit:7880"
    # Where a browser on the host reaches it (returned with join tokens).
    livekit_public_url: str = "ws://localhost:7880"
    # Name the agent worker registers with; dispatch is explicit.
    agent_name: str = "session-archive-test-agent"
    # Seconds a room stays open with nobody in it.
    room_empty_timeout: int = 60

    # --- Archive layout ---
    # Prepended to every key this app writes. Empty by default; the live test
    # sets e2e/<run-id>/ so a run only touches its own prefix in a shared bucket.
    archive_prefix: str = ""
    # Bundled conversation scripts (JSON). Relative paths resolve from the repo
    # root; the api container mounts the agent's copy at an absolute path.
    session_scripts_dir: str = "services/agent/scripts"

    # --- Transcription and evaluation ---
    whisper_model: str = "tiny.en"
    # auto picks CUDA when CTranslate2 sees a GPU, else CPU (no Apple MPS
    # backend exists in CTranslate2, so Apple Silicon runs on CPU).
    whisper_device: str = "auto"
    # A session passes when its word error rate is at or below this value.
    eval_max_wer: float = 0.5

    # --- Retention (days per session class; hold is never removed) ---
    retention_days_debug: int = 1
    retention_days_standard: int = 30
    retention_days_training: int = 365

    # `extra: ignore` because the repo-root env file is shared: it also carries
    # frontend and script variables, and — after the rename to the standard B2
    # names — an older file still carrying the previous ones. pydantic-settings
    # forbids unknown keys by default, which turns any of those into a
    # ValidationError at import time. That would replace main.py's actionable
    # "missing required B2 configuration" startup message with a traceback, so
    # unknown keys are ignored here and the required set is validated there.
    model_config = {
        "env_file": ".env",
        "env_file_encoding": "utf-8",
        "extra": "ignore",
    }

    @property
    def endpoint_url(self) -> str:
        """B2's S3-compatible endpoint for this bucket's region.

        Derived from `B2_REGION`, never configured separately: one region and
        one endpoint string are two sources of truth that can disagree, and the
        endpoint is fully determined by the region. A non-standard endpoint (an
        S3 proxy, or another S3-compatible service) is a deliberate one-line
        edit here rather than an environment variable.
        """
        return f"https://s3.{self.b2_region}.backblazeb2.com"

    @property
    def retention_days(self) -> dict[str, int | None]:
        """Retain days per session class. `None` means keep indefinitely."""
        return {
            "debug": self.retention_days_debug,
            "standard": self.retention_days_standard,
            "training": self.retention_days_training,
            "hold": None,
        }

    @property
    def cors_origins(self) -> list[str]:
        # Drop empties so a trailing comma or API_CORS_ORIGINS="" doesn't yield
        # a stray "" origin.
        return [o.strip() for o in self.api_cors_origins.split(",") if o.strip()]


settings = Settings()
