"""Small HTTP helpers shared by `make demo` and the live suite (run inside the api container)."""

import os
import time

import httpx

API = os.environ.get("ARCHIVE_API_URL", "http://127.0.0.1:8000")
TERMINAL = {"processed", "failed", "expired"}


def client() -> httpx.Client:
    return httpx.Client(base_url=API, timeout=30)


def create_scripted_session(
    http: httpx.Client, session_class: str = "standard", script_id: str = "support-handoff"
) -> dict:
    response = http.post(
        "/api/sessions",
        json={"script_id": script_id, "session_class": session_class, "mode": "scripted"},
    )
    response.raise_for_status()
    return response.json()


def wait_for_terminal(http: httpx.Client, session_id: str, timeout_s: float = 300) -> dict:
    """Poll the session until it is processed or failed. Returns the detail body."""
    deadline = time.monotonic() + timeout_s
    detail: dict = {}
    while time.monotonic() < deadline:
        response = http.get(f"/api/sessions/{session_id}")
        response.raise_for_status()
        detail = response.json()
        if detail["manifest"]["status"] in TERMINAL:
            return detail
        time.sleep(3)
    status = detail.get("manifest", {}).get("status")
    raise TimeoutError(f"{session_id} still {status} after {timeout_s}s")
