"""Translate a recorded Spanish file to English in one request.

Uses pre-recorded transcription with the Speech Understanding translation
feature (target language "en"). Works on a local path or a public URL.

    export ASSEMBLYAI_API_KEY=...
    python batch_translate.py entrevista.mp3
"""
from __future__ import annotations

import os
import sys

import assemblyai as aai


def make_config() -> aai.TranscriptionConfig:
    return aai.TranscriptionConfig(
        speech_models=["universal-3-5-pro", "universal-2"],
        language_detection=True,
        speaker_labels=True,
        speech_understanding=aai.SpeechUnderstandingRequest(
            request=aai.SpeechUnderstandingFeatureRequests(
                translation=aai.TranslationRequest(target_languages=["en"], formal=False)
            )
        ),
    )


def main() -> None:
    aai.settings.api_key = os.environ["ASSEMBLYAI_API_KEY"]
    audio = sys.argv[1] if len(sys.argv) > 1 else "entrevista.mp3"

    transcript = aai.Transcriber().transcribe(audio, make_config())
    if transcript.status == aai.TranscriptStatus.error:
        raise SystemExit(f"Transcription failed: {transcript.error}")

    print("--- Spanish ---")
    print(transcript.text)
    print("\n--- English ---")
    print(transcript.json_response["translated_texts"]["en"])


if __name__ == "__main__":
    main()
