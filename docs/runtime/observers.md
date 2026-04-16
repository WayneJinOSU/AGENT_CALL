# `runtime/observers.py`

## 作用
这个文件把 Pipecat 的 observer 机制接到本项目的持久化和指标模型上。

它不改变 pipeline 行为，只做旁路观测：
- 记录 transcript
- 切分 assistant turn
- 聚合 provider metrics
- 在 pipeline 完全 ready 后通知 runner 发送 `session.ready`

## `RuntimePersistenceObserver`

### 初始化参数
- `session_id`
  当前 session 的数据库主键
- `repositories`
  仓储集合，用于写 transcript 与 turn metrics
- `metrics_collector`
  `RuntimeMetricsCollector`，用于更新内存指标
- `ready_event`
  当 pipeline 真正启动完毕后置位，runner 会等待它再发 `session.ready`

### `_seen_frames`
observer 用 frame id 去重，避免同一 frame 被重复入库。

这很重要，因为 Pipecat 的某些 frame 在复杂广播/转发场景下可能被 observer 多次看到。

## `on_pipeline_started()`
这里只做一件事：

- `ready_event.set()`

这意味着：
- transport 已启动
- providers 已初始化
- pipeline 已经进入可运行状态

runner 以这个事件作为 `session.ready` 的真正发送时机。

## `on_push_frame()`
这是整份文件的核心。

### 1. 用户转写落库
如果 frame 是：
- `InterimTranscriptionFrame`
- `TranscriptionFrame`

则直接写入 `repositories.transcripts.create()`。

写入时会带上：
- `speaker="user"`
- `transcript_type="interim"` 或 `final`
- `turn_id`
  这里取当前 `active_turn.turn_id`

注意：
这里的 `turn_id` 仍然是当前 assistant turn 的 id，用来把“这句用户输入发生在 assistant 哪一轮上下文附近”关联起来。

### 2. assistant turn 开始
如果收到 `BotStartedSpeakingFrame`：
- 调 `metrics.start_assistant_turn()`

这意味着当前系统把“bot 真正开始对外播报”当作 assistant turn 的开始点，而不是 LLM 开始生成文本的时刻。

### 3. assistant turn 被打断
如果收到 `InterruptionFrame`：
- 调 `metrics.mark_active_turn_interrupted()`

因此 `session_turn_metrics.interrupted` 的语义是：
- 这一轮 assistant 输出在播报期间被用户打断过

### 4. assistant 文本落库
如果收到 `TextFrame`：
- 先累计 `text_chars`
- 再落库到 transcript 表

这里的文本是 assistant 侧的最终文本流，不是中间思维链。

### 5. assistant turn 结束并写 turn metrics
如果收到 `BotStoppedSpeakingFrame`：
- 结束 `active_turn`
- 把 turn 指标 upsert 到 `session_turn_metrics`

这一步真正把一轮 assistant turn 固化为结构化数据。

### 6. provider metrics 聚合
如果收到 `MetricsFrame`：
- 根据 `item.processor` 判断 capability 是 `asr` / `llm` / `tts`
- 再把不同类型指标映射进 `RuntimeMetricsCollector`

当前处理的 metrics 类型包括：
- `TTFBMetricsData`
- `ProcessingMetricsData`
- `TurnMetricsData`
- `LLMUsageMetricsData`
- `TTSUsageMetricsData`

## 复杂点

### 为什么 assistant turn 用 `BotStartedSpeakingFrame/BotStoppedSpeakingFrame` 切？
因为本项目关注的是“用户真正听到 bot 的这一轮输出”。

如果用 `TextFrame` 或 `LLMFullResponseStartFrame` 切 turn，会把还没播出来的文本也算进去，和用户体感不一致。

### 为什么 `InterruptionFrame` 只做标记，不直接落库？
因为 turn 还没结束。observer 先把 `active_turn.interrupted=True` 写进内存，等 `BotStoppedSpeakingFrame` 到达后再一次性 upsert 落库。

这样能避免半轮数据过早落表。
