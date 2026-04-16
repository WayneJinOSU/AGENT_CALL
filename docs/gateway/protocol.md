# `gateway/protocol.py` 解释文档

## 文件与定位 (Overview & Purpose)
`gateway/protocol.py` 是网络通信网关层的协议定义与解析模块。负责处理外部流量传入后的 JSON 解析校验，将普通字符串转变为系统内部可信、严格定义的基于 `pydantic` 的特定网络数据消息对象（比如 Session 的开端与结束）。此外也含有协议序列化导出逻辑。

## 核心逻辑与类定义 (Core Classes / Functions)

### 1. `ProtocolError`
自定义异常类。在网络层捕捉到不合法的负载、乱传的代码文本或未知格式的载体结构时，向上传递以进行优雅阻断。

### 2. `parse_text_message(raw: str)`
- **作用**: 将字符串反序列化为内部对象流。
- **逻辑**:
  1. 通过 `json.loads` 解析传入的负载，不通过则抛出 `ProtocolError`。
  2. 提取 `"type"`，并判断类型。如果为 `"session.start"` 则用模型对象 `SessionStartMessage` 去验证封装。如果为 `"session.stop"` 则验证 `SessionStopMessage` 封装。（这些 Schema 定义在 `schemas/messages.py` 中）。
  3. 拦截任何非预期的消息类别、字段验证引发异常并抛出标准底层 `ProtocolError`。由于基于 Pydantic，所有缺失字段都会在这一步被精确发现并终止扩散。

### 3. 支持函数
- `json_payload(message) -> dict`: 获取各种不同状态消息类型的 `pydantic` 实例，以强制 JSON 的模式转换内部安全状态回写字典，最终便于发给外部协议层。
- `utc_now_iso() -> str`: 获取精准和格式化的标准时间戳字符串辅助记录。

## 模块依赖与关系 (Dependencies)
- `schemas.messages` 下的声明体 (`SessionReadyMessage`, `SessionStartMessage` 等)，协议校验完全依赖它的严谨性。
- `pydantic.ValidationError` 作为上层包裹校验问题的捕集。
