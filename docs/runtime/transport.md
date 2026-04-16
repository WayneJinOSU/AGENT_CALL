# `runtime/transport.py`

## 作用
这个文件负责把北向 WebSocket 会话接到 Pipecat runtime 上。

它包含两层职责：
- 把文本控制消息映射成内部控制 frame
- 创建带统一音频参数的 `FastAPIWebsocketTransport`

## `SessionControlFrame`
这是项目自定义的内部控制帧，继承自 Pipecat `Frame`。

字段：
- `message_type`
- `request_id`
- `payload`

当前主要用于承载：
- `session.stop`

## `SessionMessageRouter`
这是放在 pipeline 最前面的轻量路由器。

顺序上它紧跟 `transport.input()` 之后，所以它能最早看到：
- 北向文本控制帧
- 原始输入音频帧

### `stop_handler`
外部注入的异步回调，通常来自 runner 的 `request_stop()`。

### `input_activity_handler`
可选回调，用来统计原始音频活动。

### `process_frame()`

#### 1. 处理 `SessionControlFrame`
如果收到：
- `message_type == "session.stop"`

则直接调用 `stop_handler(reason)`，并停止继续向下游传播。

如果是未知控制帧：
- 打 debug 日志
- 丢弃

#### 2. 处理 `InputAudioRawFrame`
如果配置了 `input_activity_handler`：
- 把音频字节长度回调出去

当前这个钩子主要用于外部统计或 silence policy 相关扩展。

#### 3. 其他 frame
全部原样继续向下游传递。

## `SessionTransportAdapter`
对 `FastAPIWebsocketTransport` 的一层项目封装。

### 目的
- 统一采样率、声道数
- 固定 `audio_in_enabled/audio_out_enabled`
- 绑定项目自己的 `SessionProtocolFrameSerializer`

### `__init__()`
内部创建 `FastAPIWebsocketTransport`，并强制使用项目的媒体默认值。

### `create()`
类方法工厂。

它先创建：
- `SessionProtocolFrameSerializer`

再把 serializer 和 websocket 一起包进 `SessionTransportAdapter`。

## 读代码时要注意的点
- `SessionMessageRouter` 不做复杂协议解析，文本消息是否合法由 `gateway.serializer` 和 `gateway.protocol` 保证
- router 只处理控制帧，不负责音频编解码
- 这个文件的主要目标是“桥接”，不是“业务决策”
