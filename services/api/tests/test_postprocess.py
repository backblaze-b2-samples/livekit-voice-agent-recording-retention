"""Post-processing: checksum, transcription (stubbed model) and evaluation."""

import hashlib
from datetime import UTC, datetime

from app.repo import transcriber
from app.service import layout, manifests, postprocess
from app.types import SessionCreate

SID = "s-20261119-0a0b0c"
AUDIO = b"OggS-fake-audio-bytes"
REFERENCE = (
    "Hello, thank you for calling the support line. I can see that your order has not "
    "arrived yet. The tracking number shows the package is still at the warehouse. I will "
    "hand you over to a human agent who can send a replacement. Thank you for your "
    "patience, and have a good day."
)


def _recorded(store):
    manifest = manifests.new_manifest(
        SID, SessionCreate(script_id="support-handoff"), datetime(2026, 11, 19, tzinfo=UTC)
    )
    manifest.status = "recorded"
    manifest.recording.size_bytes = len(AUDIO)
    manifests.save(manifest)
    store.put_bytes(layout.recording_key(SID), AUDIO, "audio/ogg")


def _fake_transcribe(text):
    def run(path):
        assert path.read_bytes() == AUDIO
        return transcriber.TranscriptionResult(
            model="faster-whisper tiny.en",
            device="cpu",
            language="en",
            segments=[transcriber.Segment(0.0, 20.0, text)],
        )

    return run


def test_process_writes_derivatives_and_marks_processed(store, monkeypatch):
    _recorded(store)
    monkeypatch.setattr(transcriber, "transcribe", _fake_transcribe(REFERENCE))

    postprocess.process_session(SID)

    manifest = store.json(layout.manifest_key(SID))
    assert manifest["status"] == "processed"
    assert manifest["recording"]["sha256"] == hashlib.sha256(AUDIO).hexdigest()
    assert manifest["transcription"]["model"] == "faster-whisper tiny.en"
    assert manifest["evaluation"]["wer"] == 0.0 and manifest["evaluation"]["passed"] is True
    assert store.json(layout.transcript_key(SID))["text"] == REFERENCE
    assert store.json(layout.evaluation_key(SID))["phrases_missing"] == []


def test_poor_transcript_fails_evaluation_not_the_session(store, monkeypatch):
    _recorded(store)
    monkeypatch.setattr(transcriber, "transcribe", _fake_transcribe("static noise"))
    postprocess.process_session(SID)
    manifest = store.json(layout.manifest_key(SID))
    assert manifest["status"] == "processed"
    assert manifest["evaluation"]["passed"] is False


def test_missing_model_stack_marks_failed(store, monkeypatch):
    _recorded(store)

    def no_model(path):
        raise RuntimeError("faster-whisper is not installed")

    monkeypatch.setattr(transcriber, "transcribe", no_model)
    postprocess.process_session(SID)
    manifest = store.json(layout.manifest_key(SID))
    assert manifest["status"] == "failed"
    assert "not installed" in manifest["error"]


def test_device_auto_falls_back_to_cpu_without_ctranslate2(monkeypatch):
    import builtins

    real_import = builtins.__import__

    def fake_import(name, *args, **kwargs):
        if name == "ctranslate2":
            raise ImportError(name)
        return real_import(name, *args, **kwargs)

    monkeypatch.setattr(builtins, "__import__", fake_import)
    assert transcriber.resolve_device("auto") == "cpu"
    assert transcriber.resolve_device("cuda") == "cuda"
