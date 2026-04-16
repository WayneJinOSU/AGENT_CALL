# `gateway/serializer.py` 解释文档

## 文件与定位 (Overview & Purpose)
`gateway/serializer.py` 是处理核心进出帧序列与反序列化的适配模块层。作为 Pipecat (一个 RTC 对话框架) 的自定义 serializer 插件，它在 WebSocket 的双向流中对不同格式的数据（纯音频二进制 vs JSON 文本指令）进行精确的拦截、鉴别、降频重采样和转发包装。

## 核心逻辑与类定义 (Core Classes / Functions)

### `SessionProtocolFrameSerializer(FrameSerializer)` 
它继承自 `FrameSerializer`，全权控制了流媒体和控制帧的互相转换。

#### 1. 签名过滤与保护机制相关:
- `_DISALLOWED_BINARY_SIGNATURES`: 设计了一个字典用以防呆黑客或错误调用导致的非 PCM 音频文件。内含常见的图片（PNG, JPEG, GIF）、媒体容器 (OGG, MP3, ZIP) 的二进制文件头 (Magic Bytes)。如果不小心流进去将被过滤器剔除。
- `_is_valid_pcm16_frame`: 检查音频缓冲数据载荷：根据声道确保 PCM16 特点对应的长度必须与采样字节对齐一致（如总是为偶数）。

#### 2. `deserialize(data)` - 流入(上传)反序列化处理
- 它的入参是一个未知对象 (bytes 或者 str)：
- **当收到 bytes/bytearray (语音)**：检测非法文件特征，记录安全拦截次数 (`_filter_drop_count`)；如果是合法的 PCM 流但环境采样率或者系统处理率不同，它就会内联调用高效率库 `audioop.ratecv` 做自动的音频升降频降采样。结束封装并返回合法的 `InputAudioRawFrame`。
- **当收到 str (控制文本)**：利用 `protocol.py` 里的 `parse_text_message` 处理这部分消息，如果报错仅仅是提示并丢弃避免服务器级挂掉。最终封装进自定义的 `SessionControlFrame` 供给运行时层跑管线处理指令。

#### 3. `serialize(frame)` - 射出(广播)序列化处理
- 管线里的下游模块在向外发射时调用：
- 把 `AudioRawFrame` 再转一波采用适当的输出采样率的原始字节；同时收集系统写出了多少个 bytes。
- 当有业务指令帧 `SessionControlFrame` 时，转回普通 JSON。

## 模块依赖与关系 (Dependencies)
- **底层加速模块**: 使用 python 内嵌 C 包 `audioop` 处理底层的音波升降频算法以最小化毫秒级延迟；使用 `hashlib` 来记录抛弃垃圾帧的具体指纹用于审计日志。
- **跨模块交互**: 大量使用 `pipecat` 框架内部的数据类如 `InputAudioRawFrame`, `StartFrame` 与 `FrameSerializer` 构成组件插拔件依赖。引入了自己系统内部的 `runtime.transport.SessionControlFrame`。
