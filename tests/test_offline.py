"""Offline tests: no API key, no network. Run `python tests/test_offline.py`.
Server messages are built from the JSON shapes in the real-time translation docs."""
import json
import os
import sys
import tempfile
import time
from urllib.parse import parse_qs, urlsplit

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from assemblyai.streaming.v3 import LLMGatewayResponseEvent, TurnEvent  # noqa: E402
from assemblyai.streaming.v3._base import _build_uri  # noqa: E402

import batch_translate  # noqa: E402
import speak_english  # noqa: E402
from prompts import ES_TO_EN_PROMPT  # noqa: E402
from stream_translate import PairPrinter, make_params  # noqa: E402


def turn(order, text, final=True):
    return TurnEvent.model_validate({
        "type": "Turn", "turn_order": order, "transcript": text, "end_of_turn": final,
        "turn_is_formatted": final, "end_of_turn_confidence": 0.9, "words": []})


def gateway(order, text, content):
    return LLMGatewayResponseEvent.model_validate({
        "type": "LLMGatewayResponse", "turn_order": order, "transcript": text,
        "data": {"choices": [{"index": 0, "message": {"role": "assistant", "content": content},
                              "finish_reason": "stop"}]}})


def query(params):
    return parse_qs(urlsplit(_build_uri("streaming.assemblyai.com", params)).query)


def test_prompt():
    assert "{{turn}}" in ES_TO_EN_PROMPT and "{{history_3}}" in ES_TO_EN_PROMPT
    assert "€1,500.00" in ES_TO_EN_PROMPT


def test_params():
    q = query(make_params())
    assert q["speech_model"] == ["assemblyai-stt-3-7-realtime"]
    assert json.loads(q["language_codes"][0]) == ["es"]
    gw = json.loads(q["llm_gateway"][0])
    assert gw["model"] == "qwen3.5-4b-32k-fast" and gw["max_tokens"] == 400
    assert json.loads(query(make_params(spanglish=True))["language_codes"][0]) == ["es", "en"]


class FakeSpeaker:
    def __init__(self):
        self.said = []

    def say(self, text):
        self.said.append(text)


def test_pairs_out_of_order_and_fallback():
    spk = FakeSpeaker()
    p = PairPrinter(spk, fallback_after=0.2)
    p.on_turn(None, turn(0, "Buenos días", final=False))  # partial: ignored
    p.on_turn(None, turn(0, "Buenos días, ¿cómo está?"))
    p.on_turn(None, turn(1, "Son 1.500,00 € en total."))
    p.on_turn(None, turn(2, "Gracias."))
    p.on_llm_response(None, gateway(1, "Son 1.500,00 € en total.", "That's €1,500.00 in total."))
    p.on_llm_response(None, gateway(0, "Buenos días, ¿cómo está?", " Good morning, how are you? "))
    time.sleep(0.4)  # turn 2 never gets a translation
    p.on_llm_response(None, gateway(2, "Gracias.", "Thanks."))  # too late: ignored
    assert p.lines[0].startswith("[1] ES: Son 1.500,00 €") and "EN: That's €1,500.00" in p.lines[0]
    assert p.lines[1].endswith("EN: Good morning, how are you?")
    assert p.lines[2].endswith("EN: (no translation)") and len(p.lines) == 3
    assert spk.said == ["That's €1,500.00 in total.", "Good morning, how are you?"]


def test_batch_config():
    raw = json.loads(batch_translate.make_config().raw.json(exclude_none=True))
    assert raw["speech_models"] == ["universal-3-5-pro", "universal-2"]
    assert raw["speech_understanding"]["request"]["translation"]["target_languages"] == ["en"]


class FakeSession:
    instances = []

    def __init__(self, config, api_key=None):
        self.config, self.spoken, self.keepalives = config, [], 0
        FakeSession.instances.append(self)

    def __enter__(self):
        return self

    def __exit__(self, *exc):
        return False

    def speak(self, text):
        self.spoken.append(text)
        yield b"\x00\x00" * 240

    def keep_alive(self):
        self.keepalives += 1


def test_speaker_one_session_with_keepalive():
    real_session, real_every = speak_english.aai.TTSSession, speak_english.KEEPALIVE_EVERY_S
    speak_english.aai.TTSSession, speak_english.KEEPALIVE_EVERY_S = FakeSession, 0.1
    try:
        out = os.path.join(tempfile.mkdtemp(), "en.pcm")
        spk = speak_english.EnglishSpeaker("test-key", out_path=out, play=False)
        spk.say("Good morning.")
        time.sleep(0.35)
        spk.say("See you on May 3.")
        spk.close()
        s = FakeSession.instances[-1]
        assert len(FakeSession.instances) == 1
        assert s.config.voice_id == "aai-kyla" and s.config.language == "english"
        assert s.spoken == ["Good morning.", "See you on May 3."] and s.keepalives >= 1
        assert os.path.getsize(out) == 960
    finally:
        speak_english.aai.TTSSession, speak_english.KEEPALIVE_EVERY_S = real_session, real_every


if __name__ == "__main__":
    for name, fn in list(globals().items()):
        if name.startswith("test_"):
            fn()
            print("ok", name)
