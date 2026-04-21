# `runtime/processors/silence_detector.py`

## 作用
`SilenceDetector` 负责实现“bot 说完后，如果用户一直不回应，就进行追问或结束”的控制逻辑。

它不是基于 STT 文本内容判断沉默，而是基于 speaking 控制帧管理一个计时器。

这点非常重要：
- “看到了 STT 文本” 不等于 `SilenceDetector` 一定会复位
- 它真正依赖的是 `UserStartedSpeakingFrame`
- 而 `UserStartedSpeakingFrame` 又依赖 user turn start 策略能成功触发

## 设计目标
它要解决的是：

- bot 说完后，什么时候开始等用户
- 用户一开口，如何立即取消等待
- bot 又重新开始说，如何取消上一轮等待
- 会话结束或挂断收尾时，如何彻底关闭沉默检测

## 初始化参数
- `post_bot_grace_ms`
  bot 刚说完后的缓冲期
- `user_response_timeout_ms`
  缓冲期结束后，再等待用户回应的时间
- `max_silence_follow_ups`
  最多允许多少轮沉默追问

## 内部状态
- `_silence_count`
  当前已经触发过多少次沉默
- `_silence_task`
  当前挂起的等待任务
- `_closed`
  是否已关闭 detector
- `_wait_generation`
  每次 arm 新任务时递增，用于日志排障
- `_last_arm_monotonic`
  最近一次启动沉默计时器的时间
- `_last_bot_started_monotonic`
  最近一次 bot 开始说话的时间
- `_last_bot_stopped_monotonic`
  最近一次 bot 停止说话的时间

## `process_frame()`
这是全部行为入口。

### 收到 `EndFrame`
- 立即 `disable()`
- 停止一切沉默追问逻辑

### 收到 `UserStartedSpeakingFrame`
- 调 `_reset_after_user_response()`
- 清零 `_silence_count`
- 取消当前等待任务

这里不再依赖 frame 方向判断。

这是一个关键修复点，因为 Pipecat 广播 `UserStartedSpeakingFrame` 时可能不是早期假设的固定方向。

但还要再注意一层：
- 如果 start strategy 自己被错误状态卡住
- 后面虽然持续有 `InterimTranscriptionFrame` / `TranscriptionFrame`
- 也可能迟迟收不到新的 `UserStartedSpeakingFrame`

这时表面现象会像：
- 用户已经在说话
- STT 也出了文本
- 但沉默检测还是继续超时

根因通常不在 `SilenceDetector` 本身，而在 user turn start 链路。

### 收到 `BotStartedSpeakingFrame` 且方向是 `UPSTREAM`
- 取消当前沉默等待

语义是：
- bot 又重新开始说了
- 说明上一轮“等待用户回应”窗口应该作废

### 收到 `BotStoppedSpeakingFrame` 且方向是 `UPSTREAM`
- 启动新的沉默等待任务

语义是：
- bot 这轮真正停止输出
- 从现在开始进入“等用户回应”的观察窗口

## 计时器模型
`_wait_for_user_response()` 分两段睡眠：

1. 先等 `post_bot_grace_ms`
2. 再等 `user_response_timeout_ms`

只有这两段都走完，才会：
- `_silence_count += 1`
- 触发 `on_silence_detected`

所以它的语义不是“bot 一停就立刻算沉默”，而是：
- 先给 bot 停止后的自然缓冲
- 再给用户一个真正回应窗口

## 事件处理器
本类会暴露：
- `on_silence_detected`

runner 在外部注册这个事件后，可以根据 `silence_count` 做两种动作：
- 未达到上限时，播报“您好，还在听吗？”
- 达到上限时，追加 system prompt 让 LLM 礼貌结束通话

## 最容易误判的地方

### 1. 看到“刚播完就追问”不一定是计时器有问题
如果日志显示：
- `Silence timeout fired ... elapsed=8.004s`

那说明计时器是正常的。出现“bot 刚停就立刻开始生成追问 TTS”的现象，往往是：
- 追问早就被排进了下游队列
- 只是前面的 TTS 播完后才轮到它

### 2. `BotStoppedSpeakingFrame` 可能短暂抖动
长回复内部可能出现短暂的 `BotStopped` / `BotStarted` 成对抖动。

当前实现会在 `BotStartedSpeakingFrame` 到达时立刻 cancel 上一轮等待，所以这种抖动本身通常不是问题。

### 3. 告别收尾时必须先 disable
如果已经进入 hangup 流程，但 `SilenceDetector` 没被关闭，就可能出现：
- bot 说完告别语
- 沉默追问还在继续工作
- 告别后又跟上一句“您好，还在听吗？”

因此 runner 在收到 `WordAwareSanitizer.on_hangup_started` 时会立刻 `disable()` 它。

## 调试日志怎么看
当前文件专门补了一组高信号日志，主要用于排查：
- 什么时候 arm
- 什么时候 cancel
- timeout 是第几代任务触发的
- 触发时真正经过了多久

出现异常时最值得看的是：
- `BotStoppedSpeakingFrame received; arming silence wait`
- `Cancelling silence wait`
- `Silence timeout fired`

如果还想确认是不是 turn-start 链路导致的误判，再往上看两类日志：
- `LoggingMinWordsUserTurnStartStrategy ... should_trigger=True`
- `session.runner:_on_user_turn_started ...`

如果前者持续出现、后者却没有出现，说明：
- STT 文本到了
- 但用户 turn 没真正开始
- `SilenceDetector` 因而不会收到复位所需的 speaking 控制帧
