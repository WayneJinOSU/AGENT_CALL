# `runtime/processors/word_aware_sanitizer.py`

## 作用
`WordAwareSanitizer` 负责观察 assistant 文本流中的结束语，并把“说到再见以后该如何收尾”拆成两个阶段：

1. 先发出“挂断开始”事件
2. 再在下游延迟推 `EndFrame`

这样做的目的是让当前告别 TTS 可以自然播完，同时提前关闭其他还在运行的控制逻辑，例如沉默追问。

## 为什么它放在 `LLM -> TTS` 之间
因为它既需要：
- 看到 assistant 文本

又不应该：
- 影响上游 user aggregation

把它放在 TTS 前可以做到：
- 先识别是否进入挂断流程
- 仍然允许下游 TTS 把已生成好的告别内容播完

## 核心状态
- `_buffer`
  最近的 assistant 文本缓冲
- `_is_hanging_up`
  是否已经进入挂断流程
- `_is_ended`
  是否已经看到或推送过 `EndFrame`
- `_exit_delay`
  从识别结束语到真正推 `EndFrame` 的延迟

## 结束语识别
使用两层正则：
- `_endcall_regex`
  常规短语匹配
- `_COMPACT_ENDCALL_REGEX`
  去空格后匹配，适配中文和紧凑拼写

支持的代表性结束语包括：
- `goodbye`
- `chao`
- `再见`
- `拜拜`
- `[[HANGUP]]`

## 事件：`on_hangup_started`
这是当前文件最关键的设计点。

一旦检测到结束语，它不会直接先推 `EndFrame`，而是先：

1. 置 `_is_hanging_up = True`
2. 触发 `on_hangup_started`
3. 再异步启动 `_perform_hangup_sequence()`

runner 监听这个事件后会立刻：
- `disable()` 掉 `SilenceDetector`
- 把 session 状态切到 `HANGING_UP`

这样才能避免出现：
- bot 已经在告别
- 但沉默追问链路还在工作
- 告别后面又补一句“您好，还在听吗？”

## `process_frame()`

### 已进入挂断流程时
如果 `_is_hanging_up` 为真：
- 非文本 frame 继续透传
- 文本 frame 直接丢弃
- 如果看到 `EndFrame`，补 `_is_ended = True`

这意味着：
- 进入挂断后，不再允许新的 assistant 文本继续扩展内容
- 但控制帧仍然可以向下游传，保证收尾完整

### 仍在普通对话时
如果收到 `LLMTextFrame` 或 `TextFrame`：
- 把文本累进 `_buffer`
- 做结束语匹配
- 命中时记录日志，打印文本尾部
- 触发 `on_hangup_started`
- 启动异步挂断任务
- 当前文本仍继续往下游传给 TTS

### 收到 `LLMFullResponseEndFrame` / `EndFrame`
直接透传。

## `_perform_hangup_sequence()`
这一步在后台运行：

1. `sleep(exit_delay)`
2. 如果还没 `_is_ended`
3. 向下游 `push_frame(EndFrame(), direction)`

这里的 `EndFrame` 是从 sanitizer 当前所在位置往下游走的。

## 非常重要的边界

### 1. 这个 `EndFrame` 看不到上游 processor
因为 sanitizer 位于：

`... -> llm -> WordAwareSanitizer -> tts -> output -> ...`

所以它推下游 `EndFrame` 时：
- 后面的 `tts`、`output`、`assistant_aggregator` 能看到
- 前面的 `SilenceDetector` 看不到

这也是为什么需要先发 `on_hangup_started` 给 runner，由 runner 主动关闭上游沉默检测。

### 2. 它不会直接改 session 状态
session 状态切换属于 runner 职责，不在 processor 内完成。

processor 只负责：
- 识别结束语
- 发事件
- 延迟推 `EndFrame`

## 调试时重点看哪几条日志
- `Detected end phrase ... text_tail=...`
- `Hangup started; disabling silence detector ...`
- `request_stop accepted ...`

这几条连起来可以判断：
- 有没有识别到结束语
- 有无进入 hangup 模式
- stop 是谁触发的
