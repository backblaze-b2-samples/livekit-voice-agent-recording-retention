"""Test doubles for the repo boundary. No network, no model."""

import hashlib
import json
from datetime import UTC, datetime
from pathlib import Path


class FakeStore:
    """Versioned in-memory bucket with the session_store function surface."""

    def __init__(self) -> None:
        self.versions: dict[str, list[bytes]] = {}

    def install(self, monkeypatch, module) -> None:
        for name in (
            "put_json",
            "put_bytes",
            "get_json",
            "head",
            "stream_sha256",
            "download_to",
            "list_objects",
            "delete_all_versions",
        ):
            monkeypatch.setattr(module, name, getattr(self, name))

    # --- helpers for tests ---
    def keys(self) -> list[str]:
        return sorted(self.versions)

    def json(self, key: str) -> dict:
        return json.loads(self.versions[key][-1])

    # --- session_store surface ---
    def put_bytes(self, key: str, data: bytes, content_type: str = "") -> None:
        self.versions.setdefault(key, []).append(bytes(data))

    def put_json(self, key: str, data: dict) -> None:
        self.put_bytes(key, json.dumps(data, default=str).encode())

    def get_json(self, key: str):
        if key not in self.versions:
            return None
        return json.loads(self.versions[key][-1])

    def head(self, key: str):
        if key not in self.versions:
            return None
        body = self.versions[key][-1]
        return {"size": len(body), "etag": hashlib.md5(body).hexdigest(), "content_type": ""}

    def stream_sha256(self, key: str):
        body = self.versions[key][-1]
        return hashlib.sha256(body).hexdigest(), len(body)

    def download_to(self, key: str, path: Path) -> None:
        path.write_bytes(self.versions[key][-1])

    def list_objects(self, prefix: str):
        return [
            {"Key": k, "Size": len(v[-1]), "LastModified": datetime.now(UTC)}
            for k, v in sorted(self.versions.items())
            if k.startswith(prefix)
        ]

    def delete_all_versions(self, prefix: str, keep: tuple[str, ...] = ()):
        removed = freed = 0
        for key in [k for k in self.versions if k.startswith(prefix)]:
            if keep and key.endswith(keep):
                continue
            removed += len(self.versions[key])
            freed += sum(len(v) for v in self.versions[key])
            del self.versions[key]
        return removed, freed


class FakeLiveKit:
    """Records calls to the LiveKit server functions in repo/livekit_api.py."""

    def __init__(self) -> None:
        self.calls: list[tuple] = []
        self.fail_on: str | None = None

    def install(self, monkeypatch, module) -> None:
        self.error = module.LiveKitError
        for name in ("create_room", "dispatch_agent", "start_egress", "delete_room"):
            monkeypatch.setattr(module, name, getattr(self, name))

    def _record(self, name: str, *args):
        self.calls.append((name, *args))
        if self.fail_on == name:
            raise self.error(f"{name} refused")

    def create_room(self, name, metadata):
        self._record("create_room", name, metadata)

    def dispatch_agent(self, room_name, metadata):
        self._record("dispatch_agent", room_name, metadata)
        return "AD_test"

    def start_egress(self, room_name, filepath):
        self._record("start_egress", room_name, filepath)
        return "EG_test", "EGRESS_STARTING"

    def delete_room(self, name):
        self._record("delete_room", name)

    def names(self) -> list[str]:
        return [c[0] for c in self.calls]
