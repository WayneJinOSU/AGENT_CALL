# `gateway/websocket.py` 解释文档

## 文件与定位 (Overview & Purpose)
`gateway/websocket.py` 是处理 FastAPI 异步 WebSocket 连接的核心终端路由定义。它是外部客户端建立 WebSocket 通道（拨号呼入）的直面窗口，连接被成功建构后，在此进行初始的握手验证，并将其托管给底层的运行会话逻辑执行模块（Session Runner）。

## 核心逻辑与定义 (Core Functions)

### 1. `router` (APIRouter)
导出一个 FastAPI Router 作为被 `app.py` 注册引入使用的容器基座。

### 2. `outbound_session(websocket: WebSocket)` 
此异步接口被挂载在路由 `/v1/outbound/session`。
- **会话握手**: 利用 `await websocket.accept()` 接受浏览器/语音端的全双工通讯连接。读取第一条客户端发送的消息（预期是鉴权和启动消息）。
- **心跳/防抖与强类型校验**: 强迫第一条被执行的信息必须经历 `parse_text_message` 以排查乱码和不合法的开头。并强行检查该第一帧协议类型是否规定为 `session.start`，否则会以 HTTP 强踢退出，抛出 `1003 (Invalid protocol / payload)` 错误反馈。
- **接管放权 (Delegation)**: 一旦以上全流程经过确认，WebSocket Socket 句法操作符以及经过良好解析得到的第一个配置对象 `parsed`，被直接丢给位于 `session.runner.py` 内的核心 `run_session` 流程来全权包揽后续的媒体流、管道、大模型生成等业务。

## 模块依赖与关系 (Dependencies)
- 对接 `FastAPI` 层获取连接升级。
- 业务依赖于 `gateway.protocol` 内的安全文本载荷解析体系。
- 业务流转下移至应用中枢的 `session.runner.run_session`。
