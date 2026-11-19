"""Local speech-to-text with faster-whisper (CTranslate2), no hosted provider.

`faster_whisper` and `ctranslate2` are imported lazily, inside the functions
that need them: they ship in `requirements-ml.txt` (installed in the api Docker
image), not in the host venv `pnpm verify` uses, so importing this module never
requires the model stack.
"""

import functools
import logging
from dataclasses import dataclass
from pathlib import Path
from threading import Lock

from app.config import settings

logger = logging.getLogger(__name__)

# One model, one transcription at a time: CTranslate2 already uses every core,
# so parallel jobs only add memory pressure.
_transcribe_lock = Lock()


@dataclass(frozen=True)
class Segment:
    start: float
    end: float
    text: str


@dataclass(frozen=True)
class TranscriptionResult:
    model: str
    device: str
    language: str | None
    segments: list[Segment]

    @property
    def text(self) -> str:
        return " ".join(s.text.strip() for s in self.segments if s.text.strip())


def resolve_device(requested: str) -> str:
    """auto -> cuda when CTranslate2 sees a GPU, else cpu.

    CTranslate2 has no Apple MPS backend, so Apple Silicon resolves to cpu.
    An explicit value is passed through unchanged.
    """
    if requested != "auto":
        return requested
    try:
        import ctranslate2

        if ctranslate2.get_cuda_device_count() > 0:
            return "cuda"
    except Exception:  # missing CUDA runtime libraries count as "no GPU"
        logger.info("CUDA not available to CTranslate2; using CPU")
    return "cpu"


@functools.lru_cache(maxsize=2)
def _load_model(model_name: str, device: str):
    from faster_whisper import WhisperModel

    compute_type = "float16" if device == "cuda" else "int8"
    logger.info("Loading faster-whisper model=%s device=%s", model_name, device)
    return WhisperModel(model_name, device=device, compute_type=compute_type)


def transcribe(path: Path) -> TranscriptionResult:
    """Transcribe one audio file. Raises RuntimeError when the model stack is missing."""
    device = resolve_device(settings.whisper_device)
    model_name = settings.whisper_model
    try:
        model = _load_model(model_name, device)
    except ImportError as e:
        raise RuntimeError(
            "faster-whisper is not installed in this environment; it ships in "
            "services/api/requirements-ml.txt (installed in the api Docker image)."
        ) from e
    with _transcribe_lock:
        segments_iter, info = model.transcribe(str(path), beam_size=1, vad_filter=False)
        segments = [Segment(float(s.start), float(s.end), s.text) for s in segments_iter]
    return TranscriptionResult(
        model=f"faster-whisper {model_name}",
        device=device,
        language=getattr(info, "language", None),
        segments=segments,
    )
