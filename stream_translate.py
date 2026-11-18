"""Real-time Spanish -> English speech translation.

Streams Spanish audio (a file, a radio or HLS URL, or a capture device) to
AssemblyAI STT 3.7 Realtime and prints each turn in Spanish next to its English
translation, which arrives on the same WebSocket via llm_gateway.

    export ASSEMBLYAI_API_KEY=...
    python stream_translate.py entrevista.wav
    python stream_translate.py https://example.com/radio/stream.mp3 --spanglish --speak
"""
from __future__ import annotations

import argparse
import os
import threading
from typing import Dict, List, Optional

from assemblyai.streaming.v3 import (
    LLMGatewayResponseEvent,
    RealTimeError,
    RealTimeEvents,
    RealTimeParameters,
    RealTimeTranscriber,
    RealTimeTranscriberOptions,
    TerminationEvent,
    TurnEvent,
)
from assemblyai.streaming.v3.models import LLMGatewayConfig, LLMGatewayMessage

from audio_source import SAMPLE_RATE, open_source
from prompts import ES_TO_EN_PROMPT

SPEECH_MODEL = "assemblyai-stt-3-7-realtime"  # AssemblyAI STT 3.7 Realtime
TRANSLATION_MODEL = "qwen3.5-4b-32k-fast"


def make_params(spanglish: bool = False) -> RealTimeParameters:
    return RealTimeParameters(
        sample_rate=SAMPLE_RATE,
        speech_model=SPEECH_MODEL,
        # Bias recognition toward Spanish, or Spanish + English for Spanglish.
        language_codes=["es", "en"] if spanglish else ["es"],
        llm_gateway=LLMGatewayConfig(
            model=TRANSLATION_MODEL,
            messages=[LLMGatewayMessage(role="user", content=ES_TO_EN_PROMPT)],
            max_tokens=400,
        ),
    )


class PairPrinter:
    """Joins each English translation to its Spanish turn by turn_order."""

    def __init__(self, speaker=None, fallback_after: float = 3.0):
        self.spanish: Dict[int, str] = {}
        self.done: set = set()
        self.speaker = speaker
        self.fallback_after = fallback_after
        self.lines: List[str] = []
        self._lock = threading.Lock()

    def _emit(self, line: str) -> None:
        self.lines.append(line)
        print(line, flush=True)

    def on_turn(self, client, event: TurnEvent) -> None:
        if not event.end_of_turn or not event.transcript:
            return  # partials stay in Spanish and aren't translated
        with self._lock:
            self.spanish[event.turn_order] = event.transcript
        timer = threading.Timer(self.fallback_after, self._no_translation, args=(event.turn_order,))
        timer.daemon = True
        timer.start()

    def on_llm_response(self, client, event: LLMGatewayResponseEvent) -> None:
        try:
            english = event.data["choices"][0]["message"]["content"].strip()
        except (KeyError, IndexError, TypeError, AttributeError):
            english = ""
        with self._lock:
            if event.turn_order in self.done or not english:
                return
            self.done.add(event.turn_order)
            spanish = self.spanish.get(event.turn_order, event.transcript)
        self._emit(f"[{event.turn_order}] ES: {spanish}\n    EN: {english}")
        if self.speaker is not None:
            self.speaker.say(english)

    def _no_translation(self, turn_order: int) -> None:
        # The gateway sends nothing when a translation fails or times out.
        with self._lock:
            if turn_order in self.done:
                return
            self.done.add(turn_order)
            spanish = self.spanish[turn_order]
        self._emit(f"[{turn_order}] ES: {spanish}\n    EN: (no translation)")


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__,
                                     formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("source", help="16 kHz mono WAV, any ffmpeg file/URL, or 'ffmpeg:<input args>'")
    parser.add_argument("--spanglish", action="store_true",
                        help="steer toward Spanish and English for code-switching speakers")
    parser.add_argument("--speak", action="store_true",
                        help="voice the English with AssemblyAI text to speech (aai-kyla)")
    args = parser.parse_args()

    api_key = os.environ["ASSEMBLYAI_API_KEY"]
    speaker = None
    if args.speak:
        from speak_english import EnglishSpeaker
        speaker = EnglishSpeaker(api_key)

    printer = PairPrinter(speaker)
    client = RealTimeTranscriber(
        RealTimeTranscriberOptions(api_host="streaming.assemblyai.com"), api_key=api_key)
    client.on(RealTimeEvents.Turn, printer.on_turn)
    client.on(RealTimeEvents.LLMGatewayResponse, printer.on_llm_response)
    client.on(RealTimeEvents.Error, lambda c, err: print(f"Streaming error: {err}"))
    client.on(RealTimeEvents.Termination, lambda c, e: print(
        f"Done: {e.audio_duration_seconds}s of audio, {e.session_duration_seconds}s session"))

    client.connect(make_params(args.spanglish))
    try:
        client.stream(open_source(args.source))
    except KeyboardInterrupt:
        pass
    finally:
        client.disconnect(terminate=True)
        if speaker is not None:
            speaker.close()


if __name__ == "__main__":
    main()
