"""Detect voicemail prompts and replace user utterance with voicemail instruction."""

from __future__ import annotations

import re

from loguru import logger
from pipecat.frames.frames import Frame, TextFrame, TranscriptionFrame
from pipecat.processors.frame_processor import FrameDirection, FrameProcessor


class VoicemailDetector(FrameProcessor):
    """Match voicemail keywords from STT text and force a voicemail response prompt."""

    _COMPACT_VOICEMAIL_REGEX = re.compile(
        r"(?:语音信箱|开始留言|无法接通|号码不存在|不在服务区|听到?滴?声)",
        re.I,
    )

    def __init__(self, max_buffer_chars: int = 600, language: str = "") -> None:
        super().__init__()
        self._detected = False
        self._buffer = ""
        self._max_buffer_chars = max_buffer_chars
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
            r"\bunavailable\b|"
            r"听到?\s*滴?\s*声|"
            r"开始\s*留言|"
            r"无法\s*接通|"
            r"号码\s*不存在|"
            r"语音\s*信箱|"
            r"不在\s*服务区"
            r")"
        )
        self._prompt = self._build_prompt(language)

    async def process_frame(self, frame: Frame, direction: FrameDirection) -> None:
        await super().process_frame(frame, direction)

        if isinstance(frame, (TextFrame, TranscriptionFrame)) and not self._detected:
            text = frame.text.strip()
            if text:
                self._buffer += text
                if len(self._buffer) > self._max_buffer_chars:
                    self._buffer = self._buffer[-self._max_buffer_chars :]
                check_text = self._buffer.strip()
                compact_text = re.sub(r"\s+", "", check_text)
                if self._voicemail_regex.search(check_text) or self._COMPACT_VOICEMAIL_REGEX.search(compact_text):
                    logger.info("[VoicemailDetector] Detected voicemail keywords.")
                    self._detected = True
                    frame.text = self._prompt
                    self._buffer = ""

        await self.push_frame(frame, direction)

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
