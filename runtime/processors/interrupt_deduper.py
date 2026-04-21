"""Helpers for suppressing repeated user interruption text."""

from __future__ import annotations

import re
import time
import unicodedata
from collections import deque
from dataclasses import dataclass
from difflib import SequenceMatcher
from typing import Literal

DecisionAction = Literal["allow", "defer", "suppress"]


@dataclass(frozen=True)
class InterruptTextFeatures:
    """Normalized representation used for token counting and matching."""

    normalized_text: str
    tokens: tuple[str, ...]


@dataclass(frozen=True)
class InterruptHistoryEntry:
    """Recent finalized or provisional utterance kept for matching."""

    raw_text: str
    normalized_text: str
    tokens: tuple[str, ...]
    reason: str
    timestamp_monotonic: float
    provisional: bool = False


@dataclass(frozen=True)
class InterruptSuppressionDecision:
    """Decision details for repeated-interruption suppression."""

    action: DecisionAction
    similarity: float
    elapsed_ms: int | None
    normalized_text: str
    candidate_text: str | None
    candidate_reason: str | None
    prefix_match: bool = False


class InterruptDeduper:
    """Suppress repeated interruption inputs within a recent utterance window."""

    _TOKEN_PATTERN = re.compile(r"[a-z0-9áéíóúüñ]+|[\u3400-\u4dbf\u4e00-\u9fff]")
    _LEADING_NOISE_PATTERN = re.compile(r"^[\s\.,!?;:，。！？；：、“”\"'‘’（）()\-_]+")
    _CHINESE_FILLERS = (
        "那个",
        "这个",
        "就是",
        "然后",
        "那么",
        "啊",
        "嗯",
        "哦",
        "喂",
        "欸",
        "诶",
        "哎",
    )
    _ENGLISH_FILLERS = {
        "sorry",
        "alright",
        "allright",
        "okay",
        "ok",
        "well",
        "uh",
        "um",
        "ah",
        "er",
        "hmm",
    }
    _SPANISH_FILLERS = {
        "bueno",
        "vale",
        "pues",
        "entonces",
        "eh",
        "ah",
        "oye",
        "hola",
        "este",
    }
    _MIN_PREFIX_TOKENS = 2

    def __init__(
        self,
        *,
        similarity_threshold: float = 0.8,
        suppression_window_ms: int = 3000,
        history_window_ms: int | None = None,
        history_size: int = 6,
    ) -> None:
        self._similarity_threshold = similarity_threshold
        self._suppression_window_ms = suppression_window_ms
        self._history_window_ms = history_window_ms or max(suppression_window_ms, 8000)
        self._history_size = history_size
        self._history: deque[InterruptHistoryEntry] = deque(maxlen=history_size)
        self._pending_entry: InterruptHistoryEntry | None = None

    def evaluate(
        self,
        *,
        text: str,
        reason: str,
        phase: Literal["interim", "final"],
        now_monotonic: float | None = None,
        defer_on_interim: bool = True,
    ) -> InterruptSuppressionDecision:
        features = self.extract_features(text)
        now = time.monotonic() if now_monotonic is None else now_monotonic
        self._trim_history(now)
        if not features.tokens:
            return InterruptSuppressionDecision(
                action="allow",
                similarity=0.0,
                elapsed_ms=None,
                normalized_text=features.normalized_text,
                candidate_text=None,
                candidate_reason=None,
            )

        best_candidate: InterruptHistoryEntry | None = None
        best_similarity = 0.0
        best_elapsed_ms: int | None = None
        best_prefix_match = False

        for candidate in self._iter_candidates():
            elapsed_ms = int((now - candidate.timestamp_monotonic) * 1000)
            if elapsed_ms > self._history_window_ms:
                continue
            similarity = self._similarity(features.tokens, candidate.tokens)
            prefix_match = self._is_prefix_duplicate(features.tokens, candidate.tokens)
            if not prefix_match and similarity < self._similarity_threshold:
                continue
            score = (1.0 if prefix_match else 0.0, similarity, -elapsed_ms)
            best_score = (
                1.0 if best_prefix_match else 0.0,
                best_similarity,
                -(best_elapsed_ms or 0),
            )
            if best_candidate is None or score > best_score:
                best_candidate = candidate
                best_similarity = similarity
                best_elapsed_ms = elapsed_ms
                best_prefix_match = prefix_match

        if best_candidate is None:
            return InterruptSuppressionDecision(
                action="allow",
                similarity=0.0,
                elapsed_ms=None,
                normalized_text=features.normalized_text,
                candidate_text=None,
                candidate_reason=None,
            )

        if best_elapsed_ms is None or best_elapsed_ms > self._suppression_window_ms:
            action: DecisionAction = "allow"
        elif phase == "interim" and defer_on_interim:
            action = "defer"
        else:
            action = "suppress"

        return InterruptSuppressionDecision(
            action=action,
            similarity=best_similarity,
            elapsed_ms=best_elapsed_ms,
            normalized_text=features.normalized_text,
            candidate_text=best_candidate.raw_text,
            candidate_reason=best_candidate.reason,
            prefix_match=best_prefix_match,
        )

    def begin_accepted(
        self,
        *,
        text: str,
        reason: str,
        now_monotonic: float | None = None,
    ) -> None:
        features = self.extract_features(text)
        if not features.tokens:
            return
        now = time.monotonic() if now_monotonic is None else now_monotonic
        self._pending_entry = InterruptHistoryEntry(
            raw_text=text,
            normalized_text=features.normalized_text,
            tokens=features.tokens,
            reason=reason,
            timestamp_monotonic=now,
            provisional=True,
        )

    def finalize_utterance(
        self,
        *,
        text: str,
        default_reason: str = "user_turn",
        now_monotonic: float | None = None,
    ) -> None:
        features = self.extract_features(text)
        now = time.monotonic() if now_monotonic is None else now_monotonic
        if not features.tokens:
            self._pending_entry = None
            self._trim_history(now)
            return

        entry = InterruptHistoryEntry(
            raw_text=text,
            normalized_text=features.normalized_text,
            tokens=features.tokens,
            reason=self._pending_entry.reason if self._pending_entry else default_reason,
            timestamp_monotonic=now,
            provisional=False,
        )
        self._history.append(entry)
        self._pending_entry = None
        self._trim_history(now)

    @property
    def last_reason(self) -> str | None:
        return self._pending_entry.reason if self._pending_entry else (self._history[-1].reason if self._history else None)

    @classmethod
    def count_tokens(cls, text: str) -> int:
        return len(cls.extract_features(text).tokens)

    @classmethod
    def normalize_text(cls, text: str) -> str:
        return cls.extract_features(text).normalized_text

    @classmethod
    def extract_features(cls, text: str) -> InterruptTextFeatures:
        lowered = unicodedata.normalize("NFKC", text).lower()
        lowered = cls._strip_leading_chinese_fillers(lowered)
        tokens = tuple(cls._TOKEN_PATTERN.findall(lowered))
        tokens = cls._strip_leading_fillers(tokens)
        normalized_text = "".join(tokens)
        return InterruptTextFeatures(
            normalized_text=normalized_text,
            tokens=tokens,
        )

    @classmethod
    def _strip_leading_fillers(cls, tokens: tuple[str, ...]) -> tuple[str, ...]:
        index = 0
        filler_tokens = cls._ENGLISH_FILLERS | cls._SPANISH_FILLERS
        while index < len(tokens) and tokens[index] in filler_tokens:
            index += 1
        return tokens[index:]

    @classmethod
    def _strip_leading_chinese_fillers(cls, text: str) -> str:
        stripped = cls._strip_leading_noise(text)
        while True:
            matched = next((filler for filler in cls._CHINESE_FILLERS if stripped.startswith(filler)), None)
            if matched is None:
                return stripped
            stripped = cls._strip_leading_noise(stripped[len(matched) :])

    @classmethod
    def _similarity(cls, left: tuple[str, ...], right: tuple[str, ...]) -> float:
        if not left or not right:
            return 0.0
        if left == right:
            return 1.0
        if min(len(left), len(right)) <= 1:
            return 0.0
        return SequenceMatcher(a=left, b=right).ratio()

    @classmethod
    def _is_prefix_duplicate(cls, left: tuple[str, ...], right: tuple[str, ...]) -> bool:
        shorter, longer = (left, right) if len(left) <= len(right) else (right, left)
        if len(shorter) < cls._MIN_PREFIX_TOKENS:
            return False
        return longer[: len(shorter)] == shorter

    def _iter_candidates(self) -> tuple[InterruptHistoryEntry, ...]:
        candidates = list(self._history)
        if self._pending_entry is not None:
            candidates.append(self._pending_entry)
        return tuple(candidates)

    def _trim_history(self, now_monotonic: float) -> None:
        while self._history and int((now_monotonic - self._history[0].timestamp_monotonic) * 1000) > self._history_window_ms:
            self._history.popleft()

    @classmethod
    def _strip_leading_noise(cls, text: str) -> str:
        return cls._LEADING_NOISE_PATTERN.sub("", text)
