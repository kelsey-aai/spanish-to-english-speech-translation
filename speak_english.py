"""Speak English translations with AssemblyAI text to speech (voice aai-kyla).

One long-lived TTS session is opened for the whole run. A worker thread speaks
each translation in order and sends KeepAlive while the stream is quiet, so the
session doesn't hit its two-minute idle timeout between sentences.
"""
from __future__ import annotations

import queue
import shutil
import subprocess
import threading
from typing import Optional

import assemblyai as aai

TTS_SAMPLE_RATE = 24_000  # the session's default: 24 kHz 16-bit mono PCM
KEEPALIVE_EVERY_S = 60


class EnglishSpeaker:
    def __init__(self, api_key: str, out_path: str = "english.pcm", play: bool = True):
        self._config = aai.TTSConfig(voice_id="aai-kyla", language="english")
        self._api_key = api_key
        self._queue: "queue.Queue[Optional[str]]" = queue.Queue()
        self._out = open(out_path, "wb")
        self._player = None
        if play and shutil.which("ffplay"):
            self._player = subprocess.Popen(
                ["ffplay", "-nodisp", "-autoexit", "-loglevel", "error",
                 "-f", "s16le", "-ar", str(TTS_SAMPLE_RATE), "-ac", "1", "-"],
                stdin=subprocess.PIPE)
        self._thread = threading.Thread(target=self._run, daemon=True)
        self._thread.start()

    def say(self, text: str) -> None:
        if text.strip():
            self._queue.put(text)

    def close(self) -> None:
        self._queue.put(None)
        self._thread.join(timeout=30)
        self._out.close()
        if self._player and self._player.stdin:
            self._player.stdin.close()
            self._player.wait(timeout=30)

    def _run(self) -> None:
        with aai.TTSSession(self._config, api_key=self._api_key) as session:
            while True:
                try:
                    text = self._queue.get(timeout=KEEPALIVE_EVERY_S)
                except queue.Empty:
                    session.keep_alive()
                    continue
                if text is None:
                    return
                for chunk in session.speak(text):
                    self._out.write(chunk)
                    if self._player and self._player.stdin:
                        self._player.stdin.write(chunk)


if __name__ == "__main__":
    import os

    speaker = EnglishSpeaker(os.environ["ASSEMBLYAI_API_KEY"])
    speaker.say("We'll meet on May 3 at 7:30 PM. The deposit is 1,500 euros.")
    speaker.close()
    print("Wrote english.pcm (24 kHz, 16-bit mono PCM)")
