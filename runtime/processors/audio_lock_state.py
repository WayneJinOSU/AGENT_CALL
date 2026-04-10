"""Audio synthesis lock window helper."""

from __future__ import annotations

import time


class AudioLockState:
    """Monotonic time based audio lock state."""

    def __init__(self) -> None:
        # Monotonic clock avoids issues when wall time jumps.
        self.busy_until = 0.0

    def is_locked(self) -> bool:
        return time.monotonic() < self.busy_until + 0.1

    def extend_lock(self, duration_seconds: float) -> None:
        now = time.monotonic()
        if now > self.busy_until:
            self.busy_until = now + duration_seconds
        else:
            self.busy_until += duration_seconds
