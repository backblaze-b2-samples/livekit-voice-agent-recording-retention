"""After Egress finishes: checksum, transcription and evaluation of a recording.

Runs as a background task from the webhook receiver (so the webhook returns
quickly) and from the "Reprocess" action. Reads the recording Egress wrote to
B2; never re-uploads it.
"""

import logging
import tempfile
from pathlib import Path

from app.config import settings
from app.repo import session_store, transcriber
from app.service import layout, manifests
from app.service.evaluation import evaluate
from app.service.scripts import ScriptNotFound, get_script
from app.types import Evaluation, Transcript
from app.types.sessions import EvaluationInfo, TranscriptionInfo, TranscriptSegment

logger = logging.getLogger(__name__)


def _mark_failed(session_id: str, reason: str) -> None:
    with manifests.session_lock(session_id):
        manifest = manifests.load(session_id)
        if manifest is None:
            return
        manifest.status = "failed"
        manifest.error = reason
        manifests.save(manifest)


def _checksum(session_id: str) -> None:
    """Size from head_object (cross-checked against the webhook), SHA-256 by streaming."""
    manifest = manifests.load(session_id)
    if manifest is None:
        raise LookupError(session_id)
    head = session_store.head(manifest.recording.key)
    if head is None:
        raise RuntimeError(f"recording missing at {manifest.recording.key}")
    sha256, streamed = session_store.stream_sha256(manifest.recording.key)
    reported = manifest.recording.size_bytes
    if reported is not None and reported != head["size"]:
        logger.warning(
            "Size mismatch for %s: webhook=%s head_object=%s", session_id, reported, head["size"]
        )
    with manifests.session_lock(session_id):
        manifest = manifests.load(session_id) or manifest
        manifest.recording.size_bytes = head["size"]
        manifest.recording.etag = head["etag"]
        manifest.recording.sha256 = sha256
        if streamed != head["size"]:
            raise RuntimeError(f"streamed {streamed} bytes but head_object reports {head['size']}")
        manifests.save(manifest)


def _transcribe_and_evaluate(session_id: str) -> None:
    manifest = manifests.load(session_id)
    if manifest is None:
        raise LookupError(session_id)
    with tempfile.TemporaryDirectory() as tmp:
        local = Path(tmp) / layout.RECORDING
        session_store.download_to(manifest.recording.key, local)
        result = transcriber.transcribe(local)

    transcript = Transcript(
        session_id=session_id,
        model=result.model,
        device=result.device,
        language=result.language,
        text=result.text,
        segments=[TranscriptSegment(start=s.start, end=s.end, text=s.text.strip()) for s in result.segments],
    )
    session_store.put_json(layout.transcript_key(session_id), transcript.model_dump(mode="json"))

    try:
        script = get_script(manifest.script_id)
        reference, phrases = script.reference_text, script.expected_phrases
    except ScriptNotFound:
        reference, phrases = "", []
    scored = evaluate(reference, transcript.text, phrases, settings.eval_max_wer)
    evaluation = Evaluation(
        session_id=session_id,
        script_id=manifest.script_id,
        reference_text=reference,
        hypothesis_text=transcript.text,
        expected_phrases=phrases,
        **scored,
    )
    session_store.put_json(layout.evaluation_key(session_id), evaluation.model_dump(mode="json"))

    with manifests.session_lock(session_id):
        manifest = manifests.load(session_id) or manifest
        manifest.transcription = TranscriptionInfo(
            key=layout.transcript_key(session_id),
            model=result.model,
            device=result.device,
            language=result.language,
            word_count=len(transcript.text.split()),
        )
        manifest.evaluation = EvaluationInfo(
            key=layout.evaluation_key(session_id),
            wer=evaluation.wer,
            expected_phrases_found=len(evaluation.phrases_found),
            expected_phrases_total=len(phrases),
            passed=evaluation.passed,
        )
        manifest.status = "processed"
        manifest.error = None
        manifests.save(manifest)


def process_session(session_id: str) -> None:
    """Checksum, transcribe and evaluate. Never raises: failures land in the manifest."""
    try:
        _checksum(session_id)
        _transcribe_and_evaluate(session_id)
        logger.info("Session processed: %s", session_id)
    except Exception as e:
        logger.exception("Post-processing failed for %s", session_id)
        _mark_failed(session_id, f"post-processing failed: {e}")
