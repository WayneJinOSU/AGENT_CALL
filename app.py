from contextlib import asynccontextmanager

from fastapi import FastAPI

from db import close_db, init_db
from gateway.websocket import router as websocket_router


@asynccontextmanager
async def _lifespan(_: FastAPI):
    await init_db()
    try:
        yield
    finally:
        await close_db()


def create_app() -> FastAPI:
    app = FastAPI(title="AGENT_CALL", version="0.1.0", lifespan=_lifespan)
    app.include_router(websocket_router)
    return app


app = create_app()

if __name__ == "__main__":
    import uvicorn
    uvicorn.run("app:app", host="0.0.0.0", port=8000)
