"""会话状态机。"""

from __future__ import annotations

from collections.abc import Mapping

from schemas.session import SessionStatus


class InvalidStateTransitionError(ValueError):
    """非法状态迁移。"""
    pass


_ALLOWED_TRANSITIONS: Mapping[SessionStatus, set[SessionStatus]] = {
    SessionStatus.CREATED: {SessionStatus.READY, SessionStatus.FAILED},
    SessionStatus.READY: {SessionStatus.ACTIVE, SessionStatus.FAILED},
    SessionStatus.ACTIVE: {SessionStatus.HANGING_UP, SessionStatus.FAILED},
    SessionStatus.HANGING_UP: {SessionStatus.ENDED, SessionStatus.FAILED},
    SessionStatus.ENDED: set(),
    SessionStatus.FAILED: set(),
}


class SessionStateMachine:
    """受限状态迁移控制器。"""

    def __init__(self) -> None:
        self._state = SessionStatus.CREATED

    @property
    def state(self) -> SessionStatus:
        """当前状态。"""
        return self._state

    def transition(self, new_state: SessionStatus) -> SessionStatus:
        """执行状态迁移并返回新状态。"""
        allowed = _ALLOWED_TRANSITIONS[self._state]
        if new_state not in allowed:
            raise InvalidStateTransitionError(f"Cannot transition from {self._state} to {new_state}")
        self._state = new_state
        return self._state
