from __future__ import annotations

import pytest

from schemas.session import SessionStatus
from session.state_machine import InvalidStateTransitionError, SessionStateMachine


def test_state_machine_happy_path() -> None:
    sm = SessionStateMachine()
    assert sm.state == SessionStatus.CREATED
    sm.transition(SessionStatus.READY)
    sm.transition(SessionStatus.ACTIVE)
    sm.transition(SessionStatus.HANGING_UP)
    sm.transition(SessionStatus.ENDED)
    assert sm.state == SessionStatus.ENDED


def test_state_machine_rejects_invalid_transition() -> None:
    sm = SessionStateMachine()
    with pytest.raises(InvalidStateTransitionError):
        sm.transition(SessionStatus.ACTIVE)
