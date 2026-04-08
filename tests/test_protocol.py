from __future__ import annotations

import pytest

from gateway.protocol import ProtocolError, parse_text_message


def _start_message() -> str:
    return """
{
  "type": "session.start",
  "request_id": "req_1",
  "payload": {
    "conversation": {
      "language": "zh-CN",
      "system_prompt": "You are an assistant",
      "initial_messages": [{"role": "user", "content": "hello"}]
    },
    "media": {
      "encoding": "pcm_s16le",
      "sample_rate": 8000,
      "channels": 1
    },
    "providers": {
      "asr": {"provider": "reference", "model": "x"},
      "llm": {"provider": "reference", "model": "y"},
      "tts": {"provider": "reference", "voice": "z"}
    },
    "runtime": {
      "barge_in": true,
      "silence_timeout_ms": 6000,
      "max_session_duration_ms": 180000
    },
    "metadata": {
      "tenant_id": "t1"
    }
  }
}
"""


def test_parse_start_message() -> None:
    message = parse_text_message(_start_message())
    assert message.type == "session.start"
    assert message.payload.media.sample_rate == 8000
    assert message.payload.media.channels == 1


def test_parse_stop_message() -> None:
    message = parse_text_message(
        '{"type":"session.stop","request_id":"req_2","payload":{"session_id":"sess_1","reason":"upstream_stopped"}}'
    )
    assert message.type == "session.stop"
    assert message.payload.session_id == "sess_1"


def test_parse_invalid_message_raises() -> None:
    with pytest.raises(ProtocolError):
        parse_text_message('{"type":"unknown","request_id":"x"}')
