"""Audio sources: 16 kHz, 16-bit mono PCM chunks at real-time pace.

Two inputs are supported:
  * a WAV file that is already 16 kHz mono 16-bit (no extra tools needed)
  * anything ffmpeg can read: a recorded file (mp4, m4a, mp3), a radio or HLS URL,
    or a live capture device
"""
from __future__ import annotations

import shlex
import subprocess
import time
import wave
from typing import Iterator, List

SAMPLE_RATE = 16_000
CHUNK_MS = 50
CHUNK_BYTES = SAMPLE_RATE * 2 * CHUNK_MS // 1000  # 16-bit mono


def wav_chunks(path: str, realtime: bool = True) -> Iterator[bytes]:
    """Yield 50 ms chunks from a 16 kHz mono 16-bit WAV file."""
    with wave.open(path, "rb") as wf:
        if (wf.getframerate(), wf.getnchannels(), wf.getsampwidth()) != (SAMPLE_RATE, 1, 2):
            raise ValueError(
                f"{path} must be 16 kHz mono 16-bit PCM; convert it with ffmpeg "
                "or pass it through ffmpeg_chunks() instead"
            )
        frames = CHUNK_BYTES // 2
        start = time.monotonic()
        sent = 0
        while True:
            data = wf.readframes(frames)
            if not data:
                return
            yield data
            sent += 1
            if realtime:
                # Pace to the wall clock so the server sees live audio.
                delay = start + sent * CHUNK_MS / 1000 - time.monotonic()
                if delay > 0:
                    time.sleep(delay)


def ffmpeg_command(input_args: List[str], realtime: bool) -> List[str]:
    cmd = ["ffmpeg", "-hide_banner", "-loglevel", "error"]
    if realtime:
        cmd.append("-re")  # read input at its native frame rate
    return cmd + input_args + [
        "-ac", "1", "-ar", str(SAMPLE_RATE), "-f", "s16le", "-acodec", "pcm_s16le", "pipe:1",
    ]


def ffmpeg_chunks(input_args: List[str], realtime: bool = True) -> Iterator[bytes]:
    """Decode any ffmpeg input to PCM and yield 50 ms chunks.

    Recorded file:  ["-i", "standup.mp4"]               (realtime=True)
    macOS device:   ["-f", "avfoundation", "-i", ":1"]  (realtime=False)
    Linux Pulse:    ["-f", "pulse", "-i", "default"]    (realtime=False)
    """
    proc = subprocess.Popen(ffmpeg_command(input_args, realtime), stdout=subprocess.PIPE)
    assert proc.stdout is not None
    try:
        while True:
            data = proc.stdout.read(CHUNK_BYTES)
            if not data:
                return
            yield data
    finally:
        proc.kill()
        proc.wait()


def open_source(spec: str) -> Iterator[bytes]:
    """'meeting.wav' -> WAV reader; 'ffmpeg:-f avfoundation -i :1' -> live device;
    anything else -> ffmpeg file or URL replayed at real-time pace."""
    if spec.startswith("ffmpeg:"):
        return ffmpeg_chunks(shlex.split(spec[len("ffmpeg:"):]), realtime=False)
    if spec.lower().endswith(".wav"):
        return wav_chunks(spec)
    return ffmpeg_chunks(["-i", spec], realtime=True)
