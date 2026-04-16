# `runtime/pipeline_factory.py`

## 作用
这个文件负责把一条完整的 Pipecat 运行时 pipeline 装出来。

它做的不只是“按顺序把 processor 串起来”，还负责决定当前 session 的控制策略，尤其是：

- 是否允许用户插话打断
- 用户 turn 的 stop timeout
- VAD 的 stop 灵敏度
- bot 首轮播报是否允许被打断

## `PipelineResources`
返回给 runner 的运行对象集合。

当前包含：
- `task`
  最终可运行的 `PipelineTask`
- `context`
  `LLMContext`，runner 可直接改写它来追加 system message 或重新触发 LLM
- `hangup_sanitizer`
  `WordAwareSanitizer` 实例，runner 通过它监听 `on_hangup_started`

## 打断策略常量
文件顶部有四个关键常量：

- `INTERRUPTIBLE_VAD_STOP_SECS = 0.5`
- `NON_INTERRUPTIBLE_VAD_STOP_SECS = 1.0`
- `INTERRUPTIBLE_USER_TURN_STOP_TIMEOUT_SECS = 2.0`
- `NON_INTERRUPTIBLE_USER_TURN_STOP_TIMEOUT_SECS = 5.0`

它们分别对应：
- 可打断时，用户说完判定更激进
- 不可打断时，用户说完判定更保守

## `_build_vad_analyzer()`
为当前 session 构造 `SileroVADAnalyzer`。

### 行为
- `allow_interruptions=True` 时使用更短的 `stop_secs`
- `allow_interruptions=False` 时使用更长的 `stop_secs`

### 降级策略
如果 Silero 初始化失败：
- 记录 warning
- 返回 `None`

这样 user aggregator 仍可继续工作，只是退化为更依赖 transcription/turn analyzer。

## `build_user_aggregator_params()`
这是整份文件最关键的控制策略函数。

它把一个上层布尔值 `allow_interruptions` 扩展成三层联动配置：

1. `user_mute_strategies`
2. `user_turn_stop_timeout`
3. `vad_analyzer`

### 可打断模式
`allow_interruptions=True` 时：

- `MuteUntilFirstBotCompleteUserMuteStrategy()`
- `FunctionCallUserMuteStrategy()`
- `user_turn_stop_timeout = 2.0`
- `vad.stop_secs = 0.5`

含义：
- 首轮 bot 播报期间仍然保护，不允许立刻插话
- 首轮之后允许 barge-in
- 函数调用期间仍然 mute 用户
- 用户停顿判定更快

### 不可打断模式
`allow_interruptions=False` 时：

- `AlwaysUserMuteStrategy()`
- `FunctionCallUserMuteStrategy()`
- `user_turn_stop_timeout = 5.0`
- `vad.stop_secs = 1.0`

含义：
- 只要 bot 在说话，用户输入就被压掉
- 函数调用期间也同样 mute
- 用户停顿判定更保守

## `build_pipeline_task()`
真正的 pipeline 装配入口。

### 1. 初始化上下文
从 `session_context.start_payload` 提取：
- `system_prompt`
- `initial_messages`

构造成 `LLMContext`。

### 2. 初始化聚合器与文本级控制处理器
- `LLMContextAggregatorPair`
- `VoicemailDetector`
- `WordAwareSanitizer`
- `AudioBufferProcessor`

其中：
- `VoicemailDetector` 负责把“语音信箱”类文本强制变成一条高优先级 user message
- `WordAwareSanitizer` 负责识别结束语并启动挂断收尾

### 3. 组装 pipeline 顺序
当前顺序是：

```text
transport.input()
-> router
-> silence_detector
-> stt_service
-> voicemail_detector
-> user_aggregator
-> llm_service
-> hangup_sanitizer
-> tts_service
-> transport.output()
-> assistant_aggregator
-> audio_buffer
```

### 为什么 `silence_detector` 放在 STT 前面？
因为它依赖的是：
- `BotStartedSpeakingFrame`
- `BotStoppedSpeakingFrame`
- `UserStartedSpeakingFrame`
- `EndFrame`

这些控制帧并不依赖 STT 文本本身。把它前置可以更早观察整条链路的 speaking 状态。

### 为什么 `hangup_sanitizer` 放在 LLM 和 TTS 之间？
因为它要看 assistant 文本流，但不应该改动上游 user aggregation。

它的职责是：
- 观察 LLM 文本
- 检测结束语
- 启动挂断事件
- 再让下游 TTS 把已经生成好的结束语播完

### 4. 组装 `PipelineParams`
主要配置：
- `allow_interruptions = session_context.start_payload.runtime.barge_in`
- metrics 开启
- usage metrics 开启
- 音频采样率对齐

注意：
`allow_interruptions` 只是 Pipecat 的全局开关之一，不等于完整的打断策略。真正的行为还由 `build_user_aggregator_params()` 决定。

### 5. 注入 observer
当前 observer 列表：
- `RuntimePersistenceObserver`
- `MetricsLogObserver`
- `TurnTrackingObserver`
- `UserBotLatencyObserver`
- `StartupTimingObserver`

## 最重要的复杂链路

### A. 打断链路
入口只有一个：
- `runtime.barge_in`

但它会影响四个地方：
- `PipelineParams.allow_interruptions`
- `user_mute_strategies`
- `user_turn_stop_timeout`
- `SileroVADAnalyzer.stop_secs`

所以看到“打断异常”时，不要只盯 `PipelineParams`。

### B. 沉默追问链路
`SilenceDetector` 在 pipeline 里独立观察 speaking 控制帧，不依赖 STT 文本。

它的定时器只有在 `BotStoppedSpeakingFrame` 后才会 arm，并在：
- `BotStartedSpeakingFrame`
- `UserStartedSpeakingFrame`
- `EndFrame`

时被 cancel 或 disable。

### C. 告别挂断链路
`WordAwareSanitizer` 检测到结束语后：

1. 先发 `on_hangup_started`
2. runner 收到后关闭 `SilenceDetector` 并把 session 标为 `HANGING_UP`
3. sanitizer 再延迟一小段时间向下游推 `EndFrame`

这样做的目的是：
- 先阻止沉默追问继续工作
- 再让当前告别 TTS 自然播完
- 最后统一收口
