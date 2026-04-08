from __future__ import annotations

import asyncio


class SessionRegistry:
    def __init__(self) -> None:
        self._sessions: dict[str, object] = {}
        self._lock = asyncio.Lock()

    async def register(self, session_id: str, runner: object) -> None:
        async with self._lock:
            self._sessions[session_id] = runner

    async def add(self, runner: object) -> None:
        session_id = getattr(runner, "session_id", None)
        if not isinstance(session_id, str):
            raise ValueError("runner.session_id must be a str")
        await self.register(session_id, runner)

    async def unregister(self, session_id: str) -> None:
        async with self._lock:
            self._sessions.pop(session_id, None)

    async def remove(self, session_id: str) -> None:
        await self.unregister(session_id)

    async def get(self, session_id: str) -> object | None:
        async with self._lock:
            return self._sessions.get(session_id)
