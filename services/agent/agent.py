"""Minimal scripted test agent for the session archive (LiveKit Agents 1.8).

The API dispatches this worker explicitly (agent name
`session-archive-test-agent`) with job metadata naming the session, the script
and the mode. The agent:

1. joins the room and publishes one microphone track,
2. waits until the room's Egress reports EGRESS_ACTIVE, so the recording
   captures the first line,
3. synthesizes each script line with the `espeak-ng` command-line program (run
   unmodified as a separate process; no model weights, no voice licenses) and
   pushes the PCM through `rtc.AudioSource`,
4. in `scripted` mode deletes the room, which ends the Egress and triggers the
   `egress_ended` webhook; in `interactive` mode it waits for the human to leave
   (or a timeout) and then deletes the room.

CPU only. Nothing here touches B2: Egress writes the recording, the API writes
everything else.

Run: `python agent.py start` (the Compose `agent` service does this).
"""

import asyncio
import io
import json
import logging
import os
import wave
from pathlib import Path

from livekit import api, rtc
from livekit.agents import AutoSubscribe, JobContext, WorkerOptions, cli

logger = logging.getLogger("session-archive-agent")

AGENT_NAME = os.environ.get("AGENT_NAME", "session-archive-test-agent")
SCRIPTS_DIR = Path(os.environ.get("SESSION_SCRIPTS_DIR", Path(__file__).parent / "scripts"))
SAMPLE_RATE = 22050  # espeak-ng's native output rate
FRAME_MS = 20
EGRESS_WAIT_S = 30.0
INTERACTIVE_JOIN_WAIT_S = 120.0
INTERACTIVE_MAX_S = 600.0


def load_script(script_id: str) -> dict:
    path = SCRIPTS_DIR / f"{script_id}.json"
    return json.loads(path.read_text(encoding="utf-8"))


async def synthesize(text: str) -> bytes:
    """16-bit mono PCM at SAMPLE_RATE for one line, via the espeak-ng CLI."""
    proc = await asyncio.create_subprocess_exec(
        "espeak-ng",
        "-v",
        "en-us",
        "-s",
        "150",
        "--stdout",
        text,
        stdout=asyncio.subprocess.PIPE,
        stderr=asyncio.subprocess.PIPE,
    )
    stdout, stderr = await proc.communicate()
    if proc.returncode != 0:
        raise RuntimeError(f"espeak-ng failed: {stderr.decode(errors='replace')}")
    with wave.open(io.BytesIO(stdout)) as wav:
        if wav.getframerate() != SAMPLE_RATE or wav.getnchannels() != 1:
            raise RuntimeError("unexpected espeak-ng output format")
        return wav.readframes(wav.getnframes())


async def push_pcm(source: rtc.AudioSource, pcm: bytes) -> None:
    samples_per_frame = SAMPLE_RATE * FRAME_MS // 1000
    bytes_per_frame = samples_per_frame * 2
    for offset in range(0, len(pcm), bytes_per_frame):
        chunk = pcm[offset : offset + bytes_per_frame]
        if len(chunk) < bytes_per_frame:
            chunk = chunk + b"\x00" * (bytes_per_frame - len(chunk))
        frame = rtc.AudioFrame(chunk, SAMPLE_RATE, 1, samples_per_frame)
        await source.capture_frame(frame)


async def push_silence(source: rtc.AudioSource, seconds: float) -> None:
    await push_pcm(source, b"\x00\x00" * int(SAMPLE_RATE * seconds))


async def wait_for_egress(ctx: JobContext) -> bool:
    """Poll until this room's Egress is active, so no line is spoken unrecorded."""
    deadline = asyncio.get_running_loop().time() + EGRESS_WAIT_S
    while asyncio.get_running_loop().time() < deadline:
        response = await ctx.api.egress.list_egress(
            api.ListEgressRequest(room_name=ctx.room.name, active=True)
        )
        if any(item.status == api.EgressStatus.EGRESS_ACTIVE for item in response.items):
            return True
        await asyncio.sleep(0.5)
    logger.warning("Egress not active after %.0fs; speaking anyway", EGRESS_WAIT_S)
    return False


async def speak_script(source: rtc.AudioSource, script: dict) -> None:
    pause = float(script.get("pause_s", 0.6))
    for line in script["lines"]:
        await push_pcm(source, await synthesize(line))
        await push_silence(source, pause)
    await source.wait_for_playout()


async def wait_for_human_to_leave(ctx: JobContext) -> None:
    try:
        human = await asyncio.wait_for(
            ctx.wait_for_participant(kind=rtc.ParticipantKind.PARTICIPANT_KIND_STANDARD),
            timeout=INTERACTIVE_JOIN_WAIT_S,
        )
    except TimeoutError:
        logger.info("Nobody joined %s; closing the room", ctx.room.name)
        return
    left = asyncio.Event()

    def on_disconnect(participant: rtc.RemoteParticipant) -> None:
        if participant.identity == human.identity:
            left.set()

    ctx.room.on("participant_disconnected", on_disconnect)
    try:
        await asyncio.wait_for(left.wait(), timeout=INTERACTIVE_MAX_S)
    except TimeoutError:
        logger.info("Interactive session %s hit its time limit", ctx.room.name)


async def entrypoint(ctx: JobContext) -> None:
    meta = json.loads(ctx.job.metadata or "{}")
    script = load_script(meta.get("script_id", "support-handoff"))
    mode = meta.get("mode", "scripted")
    logger.info("Joining %s script=%s mode=%s", ctx.room.name, script["id"], mode)

    await ctx.connect(auto_subscribe=AutoSubscribe.AUDIO_ONLY)
    source = rtc.AudioSource(SAMPLE_RATE, 1)
    track = rtc.LocalAudioTrack.create_audio_track("agent-voice", source)
    options = rtc.TrackPublishOptions(source=rtc.TrackSource.SOURCE_MICROPHONE)
    await ctx.room.local_participant.publish_track(track, options)

    await wait_for_egress(ctx)
    await push_silence(source, 1.0)  # lead-in so the first word is not clipped

    if mode == "interactive":
        await push_pcm(source, await synthesize("Hello. I will read a short script, then you can talk."))
        await push_silence(source, 1.0)
        await speak_script(source, script)
        await wait_for_human_to_leave(ctx)
    else:
        await speak_script(source, script)
        await push_silence(source, 1.0)
        await source.wait_for_playout()

    logger.info("Closing %s", ctx.room.name)
    await ctx.delete_room()


if __name__ == "__main__":
    cli.run_app(WorkerOptions(entrypoint_fnc=entrypoint, agent_name=AGENT_NAME))
