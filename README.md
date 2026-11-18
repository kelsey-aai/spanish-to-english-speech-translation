# Real-time Spanish to English speech translation

Stream Spanish audio to AssemblyAI and get English back per turn on the same WebSocket. Optionally hear the English through AssemblyAI text to speech, or translate a recorded Spanish file in one request.

Companion repo for the AssemblyAI blog post "Real-time Spanish to English speech translation with an API (Python)".

## Files

| File | What it does |
|---|---|
| `stream_translate.py` | Streams a Spanish file, URL or device to **AssemblyAI STT 3.7 Realtime** (`assemblyai-stt-3-7-realtime`) with `llm_gateway` translation, and prints Spanish/English pairs by `turn_order` |
| `prompts.py` | The Spanish to English prompt: regional vocabulary, Spanglish, US number/date/currency formats, `{{history_3}}` context |
| `speak_english.py` | Speaks each English line with text to speech (`aai-kyla`, `language="english"`) over one long-lived session with KeepAlive |
| `batch_translate.py` | Recorded files: pre-recorded transcription + Speech Understanding translation to English |
| `audio_source.py` | 16 kHz PCM from a WAV file, any ffmpeg input (file, radio or HLS URL), or a capture device, paced to real time |
| `tests/test_offline.py` | Offline tests (no API key needed) |

## Run it

```bash
python3 -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
export ASSEMBLYAI_API_KEY=your_api_key_here

# A 16 kHz mono WAV needs nothing else
python stream_translate.py entrevista.wav

# MP3/MP4 files and stream URLs need ffmpeg on your PATH
python stream_translate.py https://example.com/radio/stream.mp3

# Speakers who mix Spanish and English, with spoken English output (plays via ffplay if installed)
python stream_translate.py entrevista.wav --spanglish --speak

# A recorded file, translated in one request
python batch_translate.py entrevista.mp3
```

Output looks like this (lines print as translations arrive, so consecutive short turns can come out of order):

```text
[0] ES: Buenos días, ¿cómo está?
    EN: Good morning, how are you?
[1] ES: Son 1.500,00 € en total.
    EN: That's €1,500.00 in total.
```

## Tests

```bash
python tests/test_offline.py
```

They check the connection parameters the SDK sends, turn/translation pairing (including out-of-order arrivals and a missing translation), the batch request body, and that the speaker uses one TTS session with KeepAlive. They don't call the API.

## Notes

- Use audio you have the rights to. The repo doesn't ship a sample file.
- Streaming is billed on session duration; the gateway bills the model's tokens; text to speech bills input characters. See [pricing](https://www.assemblyai.com/pricing).
- Docs: [Real-time translation](https://www.assemblyai.com/docs/streaming/real-time-translation), [Multilingual transcription](https://www.assemblyai.com/docs/streaming/multilingual-transcription), [Text to speech quickstart](https://www.assemblyai.com/docs/tts/getting-started/quickstart), [Translation (pre-recorded)](https://www.assemblyai.com/docs/speech-understanding/translation).
