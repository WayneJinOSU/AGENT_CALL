"""Detect voicemail prompts and inject a forced voicemail instruction."""

from __future__ import annotations

import re
from collections.abc import Awaitable, Callable

from loguru import logger
from pipecat.frames.frames import (
    BotStartedSpeakingFrame,
    BotStoppedSpeakingFrame,
    Frame,
    InterimTranscriptionFrame,
    LLMMessagesAppendFrame,
    TextFrame,
    TranscriptionFrame,
)
from pipecat.processors.frame_processor import FrameDirection, FrameProcessor

VoicemailInterruptHandler = Callable[[dict[str, str]], Awaitable[None]]


class VoicemailDetector(FrameProcessor):
    """Match voicemail keywords from STT text and force a voicemail response prompt."""

    _COMPACT_VOICEMAIL_REGEX = re.compile(
        r"(?:语音信箱|开始留言|请留言|无法接通|无法应答|暂时无人接听|号码不存在|不在服务区|转入留言|转到留言|听到?[滴嘀哔]?声)",
        re.I,
    )

    def __init__(
        self,
        max_buffer_chars: int = 600,
        language: str = "",
        interrupt_handler: VoicemailInterruptHandler | None = None,
    ) -> None:
        super().__init__()
        self._detected = False
        self._buffer = ""
        self._max_buffer_chars = max_buffer_chars
        self._assistant_speaking = False
        self._interrupt_handler = interrupt_handler
        self._voicemail_regex = re.compile(
            r"(?i)("
            r"\b(?:b?uz[oó]n|(?:ser)?vicio\s+de\s+buz[oó]n|correo\s+de\s+voz|contestador)\b|"
            r"\b(?:grab[ae]|deje|grabar|dejar)\s+(?:su|tu|un|el)\s+(?:mensaje|recado)\b|"
            r"\b(?:su|tu)\s+mensaje\b|"
            r"\b(?:[aá]rea\s+)?fuera\s+de\s+(?:servicio|cobertura|l[ií]nea|[aá]rea)\b|"
            r"\bno\s+est[aá]\s+disponible\b|"
            r"\bdespu[eé]s\s+(?:del\s+tono|de\s+la\s+se[ñn]al)\b|"
            r"\b(?:pulsa\s+la\s+)?tecla\s+(?:de\s+)?(?:almohadilla|numeral|gato)\b|"
            r"\bn[uú]mero\b.*?(?:marcado|marc[oó]|no\s+existe)\b|"
            r"\bcliente\s+n[uú]mero\b|"
            r"\bcobro\s+revertido\b|"
            r"\bvoice\s*mail\b|"
            r"\b(?:leave|record)\s+(?:a\s+|your\s+)?message\b|"
            r"\b(?:after|at)\s+the\s+tone\b|"
            r"\b(?:please\s+)?leave\s+(?:your\s+)?message\b|"
            r"\b(?:sorry,?\s+)?(?:the\s+)?person\s+you\s+(?:are\s+)?trying\s+to\s+reach\b|"
            r"\bunavailable\b|"
            r"听到?\s*[滴嘀哔]?\s*声|"
            r"开始\s*留言|"
            r"请\s*留言|"
            r"无法\s*接通|"
            r"无法\s*应答|"
            r"暂时\s*无人\s*接听|"
            r"号码\s*不存在|"
            r"语音\s*信箱|"
            r"不在\s*服务区|"
            r"转入\s*留言|"
            r"转到\s*留言"
            r")"
        )
        self._prompt = self._build_prompt(language)

    async def process_frame(self, frame: Frame, direction: FrameDirection) -> None:
        await super().process_frame(frame, direction)

        if isinstance(frame, BotStartedSpeakingFrame):
            self._assistant_speaking = True
        elif isinstance(frame, BotStoppedSpeakingFrame):
            self._assistant_speaking = False
        elif isinstance(frame, (TextFrame, TranscriptionFrame, InterimTranscriptionFrame)) and not self._detected:
            text = frame.text.strip()
            if text:
                self._buffer += text
                if len(self._buffer) > self._max_buffer_chars:
                    self._buffer = self._buffer[-self._max_buffer_chars :]
                check_text = self._buffer.strip()
                compact_text = re.sub(r"\s+", "", check_text)
                if self._voicemail_regex.search(check_text) or self._COMPACT_VOICEMAIL_REGEX.search(compact_text):
                    transcript_type = self._get_transcript_type(frame)
                    logger.info(
                        "[VoicemailDetector] Detected voicemail keywords transcript_type={} text={!r}.",
                        transcript_type,
                        frame.text,
                    )
                    self._detected = True
                    self._buffer = ""
                    if self._assistant_speaking and self._interrupt_handler is not None:
                        await self._interrupt_handler(
                            {
                                "reason": "voicemail_detected",
                                "text": frame.text,
                                "transcript_type": transcript_type,
                            }
                        )
                    await self.push_frame(
                        LLMMessagesAppendFrame(
                            messages=[{"role": "user", "content": self._prompt}],
                            run_llm=True,
                        ),
                        direction,
                    )
                    return

        await self.push_frame(frame, direction)

    @staticmethod
    def _get_transcript_type(frame: Frame) -> str:
        if isinstance(frame, InterimTranscriptionFrame):
            return "interim"
        if isinstance(frame, TranscriptionFrame):
            return "final"
        return "text"

    @staticmethod
    def _build_prompt(language: str) -> str:
        lang_code = language.split("-")[0].lower() if language else "es"
        if lang_code == "zh":
            return (
                "【系统最高优先级指令】\n"
                "场景：检测到对方是语音信箱或自动答录机。\n"
                "行动要求：\n"
                "1. 忽略之前所有的对话上下文（包括对方可能发出的“喂”等声音）。\n"
                "2. 立即开始留言。\n"
                "3. 触发流程：Buzón de voz detectado。\n"
                "4. 语言简练。\n"
                "5. 在留言内容最后，必须输出“再见”用于挂断。"
            )
        if lang_code == "en":
            return (
                "[System Priority Instruction]\n"
                "Situation: You reached a voicemail or answering machine.\n"
                "Action Required:\n"
                "1. Ignore previous user context.\n"
                "2. Leave a voicemail immediately.\n"
                "3. Triggered process: Buzón de voz detectado.\n"
                "4. Be concise.\n"
                "5. At the end of the voicemail, you must output 'goodbye' for hangup."
            )
        return (
            "【Instrucción Prioritaria del Sistema】\n"
            "Situación: Has contactado con un contestador automático o buzón de voz.\n"
            "Acción requerida:\n"
            "1. Ignora cualquier input anterior del usuario.\n"
            "2. Deja un mensaje de voz inmediatamente.\n"
            "3. Activar el proceso: Buzón de voz detectado.\n"
            "4. Sé breve.\n"
            "5. Al finalizar el mensaje, escribe exactamente 'chao' para colgar."
        )
