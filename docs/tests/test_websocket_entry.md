# `tests/test_websocket_entry.py` 解释文档

## 文件与定位 (Overview & Purpose)
`tests/test_websocket_entry.py` 利用 FastAPI 测试客户件模拟出外部通过浏览器发起的 WebSocket 建联请求。专注于断连与核心的 `Session` 的移交网关逻辑（路由暴露点）。

## 核心测试用例

### 1. `test_websocket_rejects_non_start_first_message`
- 打开对 `/v1/outbound/session` 的拨入，作为建立管道之后第一句话故意给出 `"type": "session.stop"`。
- **预期结果**: 系统因握手首句不规范且无会话存在而拒绝提供更多服务；异常代码为 `WebSocketDisconnect`，并保证捕捉到的切断反馈原因代码 `exc.code == 1003`，保护了网关免受恶劣攻击。

### 2. `test_websocket_start_delegates_to_runner`
- 因为管线的调用是一个很重而且不可预测的事，开发使用了 `monkeypatch` 重写覆盖原生的 `gateway.websocket.run_session` 下放控制器，使其只在触发并接过合法参数时记录一次 `{"type": start_message.type}` 并断开。
- 利用测试框架调用正确的格式，确保经过握手大厅能够成功把执行力分配过去（即模拟系统调用正常放行）。
