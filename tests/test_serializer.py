from __future__ import annotations

import pytest
from pipecat.frames.frames import InputAudioRawFrame, OutputAudioRawFrame

from gateway.serializer import SessionProtocolFrameSerializer
from runtime.transport import SessionControlFrame


@pytest.mark.asyncio
async def test_serializer_accepts_pcm_binary() -> None:
    serializer = SessionProtocolFrameSerializer(sample_rate=8000, channels=1)
    pcm = b"\x00\x00\x01\x00\x02\x00\x03\x00"
    frame = await serializer.deserialize(pcm)
    assert isinstance(frame, InputAudioRawFrame)
    assert frame.sample_rate == 8000
    assert frame.num_channels == 1


@pytest.mark.asyncio
async def test_serializer_drops_non_pcm_binary() -> None:
    serializer = SessionProtocolFrameSerializer(sample_rate=8000, channels=1)
    frame = await serializer.deserialize(b"\x89PNG\r\n\x1a\nabc")
    assert frame is None


@pytest.mark.asyncio
async def test_serializer_parses_stop_control_message() -> None:
    serializer = SessionProtocolFrameSerializer(sample_rate=8000, channels=1)
    frame = await serializer.deserialize(
        '{"type":"session.stop","request_id":"req_2","payload":{"session_id":"sess_1","reason":"upstream_stopped"}}'
    )
    assert isinstance(frame, SessionControlFrame)
    assert frame.message_type == "session.stop"


@pytest.mark.asyncio
async def test_serializer_serializes_audio_output() -> None:
    serializer = SessionProtocolFrameSerializer(sample_rate=8000, channels=1)
    frame = OutputAudioRawFrame(audio=b"\x00\x00\x01\x00", sample_rate=8000, num_channels=1)
    payload = await serializer.serialize(frame)
    assert isinstance(payload, bytes)
    assert payload == b"\x00\x00\x01\x00"
