# `tests/test_protocol.py` 解释文档

## 文件与定位 (Overview & Purpose)
`tests/test_protocol.py` 用于针对网关解析层（`gateway.protocol`）的强类型入站命令做自动化断言检测，防止格式变更时引发静默错误。

## 核心测试用例
- **`test_parse_start_message`**: 提供了完整的内层打分表格式字符串 JSON，调用函数 `parse_text_message` 断言其输出不但能精确识别自己是 `session.start`，同时其内部层级复杂的 `media.sample_rate` 子属性都能被 Pydantic 成功接管赋默认或转化。
- **`test_parse_stop_message`**: 测试当发起主动中止的简短断连网络包时，系统的反应。
- **`test_parse_invalid_message_raises`**: 反面教材。传进去不符合期望的内容，验证网络协议解析函数是否如期甩出 `ProtocolError` 以保护主控心智。
