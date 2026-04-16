# `schemas/messages.py` 解释文档

## 文件与定位 (Overview & Purpose)
`schemas/messages.py` 是对 WebSocket 接洽阶段中互相传递信息的标准大字典。为了确保双向通讯在首发阶段或结果上报时的数据安全和类型不乱，此处利用 Pydantic 的 `Literal` 定义出了各种指令强绑定的网络载荷模板。

## 核心逻辑与类定义 (Core Classes)

### 1. 客户端发送 (Inbound Commands)
- **`SessionStartMessage`**: 第一帧呼叫。强制 `type='session.start'`，携带着包含媒体格式、三方供应商配置与会话开局预设的 `SessionStartPayload`。
- **`SessionStopMessage`**: 随时中断请求命令。强制包含会话 ID 和需要中断的原因（`SessionStopPayload`）。

### 2. 服务端回复 (Outbound Statuses)
- **`SessionReadyMessage`**: 基础库均初始化完成，随时等候客户说话。
- **`SessionFailedMessage`**: 初始化或提供商认证报错时的终结错误信封，携带着明确的错误终止码。
- **`SessionFinalizedMessage`**: 通话正常结束，报告统计报效、总时长(`total_duration_ms`) 以及通过了几个回合(`turn_count`)的信息总结。

## 模块依赖与关系 (Dependencies)
- 强依赖下层颗粒更小的数据模型提供类型定义：`ConversationConfig`, `MediaConfig`, `SessionStatus`, `TerminationCode` 等。
