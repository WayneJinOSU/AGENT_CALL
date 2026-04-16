"""北向协议序列化器。

该模块把 WebSocket 文本/二进制帧转换为 Pipecat 可消费的 Frame。
"""

from __future__ import annotations

import audioop
import hashlib
import json
from time import perf_counter

from loguru import logger
from pipecat.frames.frames import AudioRawFrame, Frame, InputAudioRawFrame, OutputAudioRawFrame, StartFrame
from pipecat.serializers.base_serializer import FrameSerializer

from gateway.protocol import ProtocolError, parse_text_message
from runtime.transport import SessionControlFrame


class SessionProtocolFrameSerializer(FrameSerializer):
    """
    Northbound WS protocol serializer:
    - text frame <-> SessionControlFrame
    - binary frame <-> raw PCM Input/OutputAudio frames
    """

    _DISALLOWED_BINARY_SIGNATURES = {
        b"\x89PNG\r\n\x1a\n": "png",
        b"\xff\xd8\xff": "jpeg",
        b"GIF87a": "gif",
        b"GIF89a": "gif",
        b"RIFF": "riff",
        b"OggS": "ogg",
        b"ID3": "mp3",
        b"%PDF": "pdf",
        b"PK\x03\x04": "zip",
    }

    def __init__(
        self,
        *,
        sample_rate: int = 8000,
        channels: int = 1,
        input_sample_rate: int = 8000,
        output_sample_rate: int = 8000,
    ) -> None:
        super().__init__()
        self.sample_rate = sample_rate
        self.channels = channels
        self.input_sample_rate = input_sample_rate
        self.output_sample_rate = output_sample_rate
        self.input_audio_bytes = 0
        self.output_audio_bytes = 0
        self._filter_drop_count = 0

    async def setup(self, frame: StartFrame) -> None:
        # Align serializer runtime sample rates with transport StartFrame.
        audio_in_sample_rate = getattr(frame, "audio_in_sample_rate", None)
        if audio_in_sample_rate:
            self.sample_rate = audio_in_sample_rate
        self.input_sample_rate = self.sample_rate
        self.output_sample_rate = getattr(frame, "audio_out_sample_rate", self.output_sample_rate)

    def _is_valid_pcm16_frame(self, payload: bytes) -> bool:
        """校验二进制帧是否满足 PCM16 对齐。"""
        bytes_per_sample = 2 * max(1, self.channels)
        return len(payload) > 0 and len(payload) % bytes_per_sample == 0

    def _detect_binary_signature(self, payload: bytes) -> str | None:
        """识别常见文件签名，避免把非音频文件误当 PCM。"""
        head = payload[:12]
        for signature, media_type in self._DISALLOWED_BINARY_SIGNATURES.items():
            if head.startswith(signature):
                return media_type
        return None

    def _binary_preview(self, payload: bytes, limit: int = 24) -> str:
        """用于日志排障的短摘要（hash + hex preview）。"""
        preview = payload[:limit].hex()
        digest = hashlib.sha1(payload).hexdigest()[:12]
        return f"sha1={digest} preview_hex={preview}"

    async def deserialize(self, data: str | bytes) -> Frame | None:
        if isinstance(data, (bytes, bytearray)):
            # Binary path: strict PCM gate to keep media contract simple and safe.
            started = perf_counter()
            audio = bytes(data)
            media_type = self._detect_binary_signature(audio)
            if media_type:
                self._filter_drop_count += 1
                elapsed_ms = (perf_counter() - started) * 1000
                logger.warning(
                    "SessionProtocolFrameSerializer dropped non-PCM payload "
                    "signature={} size={} filter_ms={:.3f} {}",
                    media_type,
                    len(audio),
                    elapsed_ms,
                    self._binary_preview(audio),
                )
                return None
            if not self._is_valid_pcm16_frame(audio):
                self._filter_drop_count += 1
                elapsed_ms = (perf_counter() - started) * 1000
                logger.warning(
                    "SessionProtocolFrameSerializer dropped invalid PCM payload "
                    "size={} channels={} filter_ms={:.3f} {}",
                    len(audio),
                    self.channels,
                    elapsed_ms,
                    self._binary_preview(audio),
                )
                return None
            if self.input_sample_rate != self.sample_rate:
                # Resample inbound PCM if upstream and runtime sample rates diverge.
                audio = audioop.ratecv(
                    audio,
                    2,
                    self.channels,
                    self.input_sample_rate,
                    self.sample_rate,
                    None,
                )[0]
            self.input_audio_bytes += len(audio)
            return InputAudioRawFrame(audio=audio, sample_rate=self.sample_rate, num_channels=self.channels)

        try:
            # Text path: only control protocol messages are accepted.
            message = parse_text_message(data)
        except ProtocolError as exc:
            logger.warning("SessionProtocolFrameSerializer ignored invalid text frame: {}", exc)
            return None

        return SessionControlFrame(
            message_type=message.type,
            request_id=message.request_id,
            payload=message.payload.model_dump(mode="json"),
        )

    async def serialize(self, frame: Frame) -> str | bytes | None:
        if self.should_ignore_frame(frame):
            return None
        if isinstance(frame, (AudioRawFrame, OutputAudioRawFrame)):
            # Runtime audio is always sent northbound as raw PCM binary chunks.
            audio = frame.audio
            sample_rate = getattr(frame, "sample_rate", self.output_sample_rate)
            channels = getattr(frame, "num_channels", self.channels)
            if sample_rate != self.output_sample_rate:
                audio = audioop.ratecv(
                    audio,
                    2,
                    channels,
                    sample_rate,
                    self.output_sample_rate,
                    None,
                )[0]
            self.output_audio_bytes += len(audio)
            return audio
        if isinstance(frame, SessionControlFrame):
            # Kept for completeness; current northbound control is mainly one-way (server -> ready/failed/finalized).
            return json.dumps(
                {
                    "type": frame.message_type,
                    "request_id": frame.request_id,
                    "payload": frame.payload,
                },
                ensure_ascii=False,
            )
        return None
