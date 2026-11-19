<!-- last_verified: 2026-11-19 -->
# Feature: Transcription and Evaluation

## Purpose
Turn each recording into a transcript and a deterministic score against its script, locally and without a hosted model or speech provider.

## Used By
- Job: background task after a complete `egress_ended` webhook
- API: `POST /api/sessions/{session_id}/reprocess` (202)
- UI: session page tabs "Transcript" and "Evaluation"; "Reprocess" button

## Core Functions
- `services/api/app/service/postprocess.py`: `process_session` (checksum, transcription, evaluation)
- `services/api/app/repo/transcriber.py`: `transcribe`, `resolve_device` (faster-whisper, lazy import)
- `services/api/app/service/evaluation.py`: `normalize`, `word_error_rate`, `phrase_coverage`, `evaluate`
- `services/api/app/repo/session_store.py`: `head`, `stream_sha256`, `download_to`, `put_json`

## Canonical Files
- Pattern exemplar: `services/api/app/repo/transcriber.py` (lazy model import, device auto-detect)

## Inputs
- The recording in B2 at the manifest's `recording.key`
- The script's lines and `expected_phrases`
- `WHISPER_MODEL` (default `tiny.en`), `WHISPER_DEVICE` (`auto`), `EVAL_MAX_WER` (default 0.5)

## Outputs
- `transcript.json`: model, device, language, full text, timestamped segments
- `evaluation.json`: reference and hypothesis text, WER, max WER, phrases found and missing, `passed`
- Manifest: `recording.size_bytes`, `etag`, `sha256`, `transcription`, `evaluation`, status `processed`

## Flow
- `head_object` the recording; warn if its size differs from the webhook's
- Stream the object from B2 in 1 MiB chunks to compute SHA-256 (and check the streamed byte count)
- Download to a temporary file, transcribe with faster-whisper (`beam_size=1`, one transcription at a time per process)
- Score: word-level Levenshtein distance / reference words after lowercasing, stripping punctuation and mapping number words to digits ("ten" -> "10", "twenty five" -> "25") on both sides; every expected phrase must appear as whole words; pass when `wer <= EVAL_MAX_WER` and no phrase is missing
- Write both JSON documents, then the manifest

## Edge Cases
- Device: `auto` uses CUDA when CTranslate2 sees a GPU, else CPU. CTranslate2 has no Apple MPS backend, so Apple Silicon runs on CPU.
- PyAV 19 removed the `metadata_errors` keyword that faster-whisper 1.2.1 passes to `av.open`, which failed every transcription; `requirements-ml.txt` keeps `av` on 18.x (`tests/test_dependency_lock.py` guards the pairing)
- Model stack not installed (host venv) -> the session is marked `failed` with that reason; the api Docker image installs `requirements-ml.txt` and bakes `tiny.en` in
- A poor transcript fails the evaluation, not the session (status stays `processed`)
- Script file removed later -> evaluation runs against an empty reference
- Whisper writes small numbers as digits ("10 minutes early") while scripts spell them out; number normalization keeps such a phrase from being reported missing
- Expected phrases avoid words `tiny.en` reliably mishears in the bundled TTS audio (it hears "dental clinic" as "mental clinic"), so `appointment-reminder` expects "automated reminder" instead; the mishearing still counts in WER

## Verification
- Test files: `services/api/tests/test_postprocess.py`, `services/api/tests/test_evaluation.py`
- Required cases: processed with derivatives and checksum; poor transcript fails evaluation only; missing model marks failed; device fallback to CPU; WER arithmetic; number words and digits compare equal
- Focused verify command: `cd services/api && .venv/bin/python -m pytest tests/test_postprocess.py tests/test_evaluation.py`
- Default pre-PR verify command: `pnpm verify`
- Full local verify command: `make test` (real model in the api container)
- Pass criteria: offline green; live suite has a non-empty transcript and a passing evaluation

## Related Docs
- [Webhook Manifests](webhook-manifests.md)
- [ARCHITECTURE.md](../../ARCHITECTURE.md)
