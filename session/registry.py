"""进程内 session 注册表。"""

from __future__ import annotations

import asyncio


class SessionRegistry:
    """线程安全（async lock）的会话索引。"""

    def __init__(self) -> None:
        self._sessions: dict[str, object] = {}
        self._lock = asyncio.Lock()

    async def register(self, session_id: str, runner: object) -> None:
        """按 session_id 注册运行对象。"""
        async with self._lock:
            self._sessions[session_id] = runner

    async def add(self, runner: object) -> None:
        """从对象属性 runner.session_id 自动注册。"""
        session_id = getattr(runner, "session_id", None)
        if not isinstance(session_id, str):
            raise ValueError("runner.session_id must be a str")
        await self.register(session_id, runner)

    async def unregister(self, session_id: str) -> None:
        """按 session_id 删除注册。"""
        async with self._lock:
            self._sessions.pop(session_id, None)

    async def remove(self, session_id: str) -> None:
        """unregister 别名，提升调用语义可读性。"""
        await self.unregister(session_id)

    async def get(self, session_id: str) -> object | None:
        """查询当前 session 运行对象。"""
        async with self._lock:
            return self._sessions.get(session_id)
