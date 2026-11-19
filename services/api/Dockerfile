# The `api` Compose service: REST API for the web UI, LiveKit webhook receiver,
# post-processing (checksum, faster-whisper transcription, evaluation) and the
# retention job. CPU by default; CUDA is used automatically when visible.
FROM python:3.12-slim-bookworm

ENV PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1 \
    HF_HOME=/models

RUN useradd --create-home --uid 10001 api
WORKDIR /app

COPY requirements.lock requirements-ml.txt ./
RUN pip install -r requirements.lock -r requirements-ml.txt

# Bake the default Whisper model into the image so the first session does not
# wait on a download. Override WHISPER_MODEL at runtime to fetch another one.
ARG WHISPER_MODEL=tiny.en
RUN mkdir -p /models \
    && python -c "from faster_whisper import WhisperModel; WhisperModel('${WHISPER_MODEL}', device='cpu', compute_type='int8')" \
    && chown -R api /models

COPY main.py pyproject.toml ./
COPY app ./app
COPY live_tests ./live_tests

USER api
EXPOSE 8000
CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8000"]
