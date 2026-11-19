# Minimal scripted test agent (LiveKit Agents worker). CPU only.
FROM python:3.12-slim-bookworm

# espeak-ng (GPL-3.0) is installed from the Debian package and run unmodified as
# a separate program: the agent shells out to it to synthesize each line.
RUN apt-get update \
    && apt-get install -y --no-install-recommends espeak-ng \
    && rm -rf /var/lib/apt/lists/*

RUN useradd --create-home --uid 10001 agent
WORKDIR /app
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt
COPY agent.py .
COPY scripts ./scripts

USER agent
ENV PYTHONUNBUFFERED=1
CMD ["python", "agent.py", "start"]
