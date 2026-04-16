# `tests/test_serializer.py` 解释文档

## 文件与定位 (Overview & Purpose)
用于针对 `gateway` 的定制的 Pipecat 字节反序列化器 (`SessionProtocolFrameSerializer`) 进行行为检测的集成测试用例。它确保恶意攻击包和正常的语音脉冲在进入信道前的有效管理。

## 核心测试用例
均为 Asyncio 包装函数的检测点：
- **`test_serializer_accepts_pcm_binary`**: 发送合法短音频头序列（偶数位的 `bytes` 组合），测试它是否返回一个带着音频数组和指定采样的 `InputAudioRawFrame` 标准内部格式类。
- **`test_serializer_drops_non_pcm_binary`**: 安全网断言。故意注入带 `\x89PNG` 图像头标志的错乱字节包，保证返回的结果会被断死为 `None` (说明包已安全过滤被截)。
- **`test_serializer_parses_stop_control_message`**: 断言从底层收到底层协议网络 JSON 命令格式时，自动包装为管线可识别拦截的专用 `SessionControlFrame` 结构。 
- **`test_serializer_serializes_audio_output`**: 测试发送（出站），确认机器抛出的声音被剥离只转为了符合预期的纯 `bytes`，能通过网络发送到对端扬声器。
