"""B2 reads and writes for the session archive (manifests, derivatives, reports).

Every call goes through the single cached boto3 client in `b2_client`, so the
`user_agent_extra` attribution rides on all of them. Recordings themselves are
written by LiveKit Egress, never by this module.
"""

import hashlib
import json
from pathlib import Path
from typing import Any

from botocore.exceptions import BotoCoreError, ClientError

from app.config import settings
from app.repo.b2_client import get_s3_client
from app.repo.list_cache import invalidate as _invalidate_list_cache

_CHUNK = 1024 * 1024
_NOT_FOUND = {"404", "NoSuchKey", "NotFound"}


def _bucket() -> str:
    return settings.b2_bucket_name


def _is_missing(error: ClientError) -> bool:
    return error.response.get("Error", {}).get("Code", "") in _NOT_FOUND


def put_json(key: str, data: dict[str, Any]) -> None:
    """Write one JSON document. Raises RuntimeError on failure."""
    body = json.dumps(data, indent=2, sort_keys=True, default=str).encode("utf-8")
    try:
        get_s3_client().put_object(
            Bucket=_bucket(), Key=key, Body=body, ContentType="application/json"
        )
    except (ClientError, BotoCoreError) as e:
        raise RuntimeError(f"B2 put_object failed for '{key}': {e}") from e
    _invalidate_list_cache()


def put_bytes(key: str, data: bytes, content_type: str) -> None:
    """Write raw bytes (webhook evidence, live-test fixtures)."""
    try:
        get_s3_client().put_object(Bucket=_bucket(), Key=key, Body=data, ContentType=content_type)
    except (ClientError, BotoCoreError) as e:
        raise RuntimeError(f"B2 put_object failed for '{key}': {e}") from e
    _invalidate_list_cache()


def get_json(key: str) -> dict[str, Any] | None:
    """Read one JSON document, or None when the key does not exist."""
    try:
        response = get_s3_client().get_object(Bucket=_bucket(), Key=key)
        return json.loads(response["Body"].read())
    except ClientError as e:
        if _is_missing(e):
            return None
        raise RuntimeError(f"B2 get_object failed for '{key}': {e}") from e
    except BotoCoreError as e:
        raise RuntimeError(f"B2 get_object failed for '{key}': {e}") from e


def head(key: str) -> dict[str, Any] | None:
    """Size, ETag and content type of one object, or None when missing."""
    try:
        response = get_s3_client().head_object(Bucket=_bucket(), Key=key)
    except ClientError as e:
        if _is_missing(e):
            return None
        raise RuntimeError(f"B2 head_object failed for '{key}': {e}") from e
    return {
        "size": int(response["ContentLength"]),
        "etag": str(response.get("ETag", "")).strip('"'),
        "content_type": response.get("ContentType", ""),
    }


def stream_sha256(key: str) -> tuple[str, int]:
    """SHA-256 of an object, computed by streaming it from B2 in 1 MiB chunks."""
    digest = hashlib.sha256()
    size = 0
    try:
        body = get_s3_client().get_object(Bucket=_bucket(), Key=key)["Body"]
        for chunk in body.iter_chunks(_CHUNK):
            digest.update(chunk)
            size += len(chunk)
    except (ClientError, BotoCoreError) as e:
        raise RuntimeError(f"B2 streamed read failed for '{key}': {e}") from e
    return digest.hexdigest(), size


def download_to(key: str, path: Path) -> None:
    """Stream an object to a local file (transcription input)."""
    try:
        body = get_s3_client().get_object(Bucket=_bucket(), Key=key)["Body"]
        with path.open("wb") as handle:
            for chunk in body.iter_chunks(_CHUNK):
                handle.write(chunk)
    except (ClientError, BotoCoreError) as e:
        raise RuntimeError(f"B2 download failed for '{key}': {e}") from e


def list_objects(prefix: str) -> list[dict[str, Any]]:
    """Every object under `prefix` (paginated, uncached, scoped)."""
    client = get_s3_client()
    kwargs: dict[str, Any] = {"Bucket": _bucket(), "Prefix": prefix, "MaxKeys": 1000}
    contents: list[dict[str, Any]] = []
    try:
        while True:
            response = client.list_objects_v2(**kwargs)
            contents.extend(response.get("Contents", []))
            if not response.get("IsTruncated"):
                return contents
            kwargs["ContinuationToken"] = response["NextContinuationToken"]
    except (ClientError, BotoCoreError) as e:
        raise RuntimeError(f"B2 list failed for prefix '{prefix}': {e}") from e


def delete_all_versions(prefix: str, keep: tuple[str, ...] = ()) -> tuple[int, int]:
    """Delete every version and delete marker under `prefix`.

    Keys ending with any suffix in `keep` are left alone. Plain `delete_object`
    on a versioned bucket only hides an object behind a delete marker; removing
    each version is what actually frees the bytes. Returns (versions, bytes).
    """
    client = get_s3_client()
    kwargs: dict[str, Any] = {"Bucket": _bucket(), "Prefix": prefix}
    removed = 0
    freed = 0
    try:
        while True:
            response = client.list_object_versions(**kwargs)
            entries = response.get("Versions", []) + response.get("DeleteMarkers", [])
            for entry in entries:
                key = entry["Key"]
                if keep and key.endswith(keep):
                    continue
                client.delete_object(Bucket=_bucket(), Key=key, VersionId=entry["VersionId"])
                removed += 1
                freed += int(entry.get("Size", 0) or 0)
            if not response.get("IsTruncated"):
                break
            kwargs["KeyMarker"] = response.get("NextKeyMarker")
            kwargs["VersionIdMarker"] = response.get("NextVersionIdMarker")
    except (ClientError, BotoCoreError) as e:
        raise RuntimeError(f"B2 version delete failed for prefix '{prefix}': {e}") from e
    _invalidate_list_cache()
    return removed, freed
