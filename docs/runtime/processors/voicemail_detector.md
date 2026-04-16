# `runtime/processors/voicemail_detector.py`

## 作用
`VoicemailDetector` 负责检测用户侧转写里是否出现“语音信箱 / 自动答录机”迹象。

一旦命中，它不会把原始转写继续交给普通对话流程，而是强制注入一条高优先级 user message，让 LLM 立即切换到留言模式。

## 为什么不能只改写原始 `TranscriptionFrame`
当前实现使用的是：
- `LLMMessagesAppendFrame(messages=[...], run_llm=True)`

原因是这条链路要具备“绕过 mute”的能力。

在不可打断或函数调用期间，`LLMUserAggregator` 可能会 mute：
- `TranscriptionFrame`
- `InterimTranscriptionFrame`
- `InputAudioRawFrame`
- `UserStartedSpeakingFrame`

但 `LLMMessagesAppendFrame` 不在 mute 列表里，因此它仍能把 voicemail 指令强制注入上下文。

## 识别逻辑

### 缓冲区
- `_buffer`
  累积最近一段 STT 文本
- `_max_buffer_chars`
  限制缓冲长度，避免无界增长

### 两层正则
- `_voicemail_regex`
  处理中英西文的常规短语
- `_COMPACT_VOICEMAIL_REGEX`
  处理中文连写或去空格后的紧凑匹配

### `_detected`
一旦命中过一次，就不再重复触发。

## `process_frame()`
仅在 frame 属于：
- `TextFrame`
- `TranscriptionFrame`

且尚未 `_detected` 时做检查。

### 命中后会发生什么
1. 记录日志
2. 把 `_detected` 置为 `True`
3. 清空缓冲
4. 向下游推一条 `LLMMessagesAppendFrame`
5. `return`

注意最后这一步：命中后不会继续把当前原始转写往下游传。

这意味着普通用户语义被“留言系统指令”替换掉了。

## `_build_prompt()`
根据语言生成对应的 voicemail system-style instruction。

当前支持：
- 中文
- 英文
- 默认西语

所有版本都要求：
- 忽略之前上下文
- 立即开始留言
- 最后输出一个固定结束词，供挂断链路识别

## 读代码时要注意的点
- 这个处理器是一次性触发的，不会反复来回切换模式
- 它的核心价值不是“识别文本”，而是“以可绕过 mute 的方式强推新语义”
