from __future__ import annotations

from fastapi.testclient import TestClient
from starlette.websockets import WebSocketDisconnect

from app import create_app


def _valid_start_message() -> dict:
    return {
        "type": "session.start",
        "request_id": "req_1",
        "payload": {
            "conversation": {
                "language": "zh-CN",
                "system_prompt": "You are an assistant",
                "initial_messages": [{"role": "user", "content": "hello"}],
            },
            "media": {
                "encoding": "pcm_s16le",
                "sample_rate": 8000,
                "channels": 1,
            },
            "providers": {
                "asr": {"provider": "reference"},
                "llm": {"provider": "reference"},
                "tts": {"provider": "reference"},
            },
            "runtime": {
                "barge_in": True,
                "silence_timeout_ms": 6000,
                "max_session_duration_ms": 180000,
            },
            "metadata": {},
        },
    }


def test_websocket_rejects_non_start_first_message() -> None:
    app = create_app()
    client = TestClient(app)
    with client.websocket_connect("/v1/outbound/session") as ws:
        ws.send_json(
            {"type": "session.stop", "request_id": "x", "payload": {"session_id": "s", "reason": "test"}}
        )
        try:
            ws.receive_json()
        except WebSocketDisconnect as exc:
            assert exc.code == 1003


def test_websocket_start_delegates_to_runner(monkeypatch) -> None:
    app = create_app()
    client = TestClient(app)
    called = {}

    async def fake_run_session(websocket, start_message):
        called["type"] = start_message.type
        await websocket.close(code=1000)

    monkeypatch.setattr("gateway.websocket.run_session", fake_run_session)

    with client.websocket_connect("/v1/outbound/session") as ws:
        ws.send_json(_valid_start_message())
        try:
            ws.receive_json()
        except WebSocketDisconnect:
            pass

    assert called["type"] == "session.start"
