"""FastAPI 应用入口。

职责很单一：
1. 初始化生命周期（当前只做 DB engine 生命周期管理）
2. 挂载北向 WebSocket 路由
"""

from contextlib import asynccontextmanager

from fastapi import FastAPI

from db import close_db, init_db
from gateway.websocket import router as websocket_router


@asynccontextmanager
async def _lifespan(_: FastAPI):
    """应用启动/关闭钩子。"""
    await init_db()
    try:
        yield
    finally:
        await close_db()


def create_app() -> FastAPI:
    """创建并返回 FastAPI 应用实例。"""
    app = FastAPI(title="AGENT_CALL", version="0.1.0", lifespan=_lifespan)
    app.include_router(websocket_router)
    return app


app = create_app()

if __name__ == "__main__":
    import uvicorn
    uvicorn.run("app:app", host="0.0.0.0", port=8000)
