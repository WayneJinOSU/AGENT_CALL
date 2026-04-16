# `runtime/metrics.py`

## 作用
这个文件定义了运行时内存指标模型。它不直接写数据库，而是先在 session 生命周期内持续累计，最后由 `Finalizer` 聚合落库。

这层的定位很明确：

- 不参与业务决策
- 只保存运行期统计状态
- 让 observer 在收到 frame 或 provider metrics 时能快速更新

## 核心数据结构

### `ProviderMetricSnapshot`
描述某个 capability 的 provider 统计快照。

当前 capability 维度固定是：
- `asr`
- `llm`
- `tts`

它记录的信息包括：
- provider/model 名称
- 连接、重连、failover 计数
- TTFB 样本
- processing time 样本
- usage 统计
- 自定义 metadata

两个只读属性：
- `avg_ttfb_ms`
- `max_ttfb_ms`

### `TurnMetricSnapshot`
描述一轮 assistant 输出的快照。

这里的“turn”不是用户 turn，而是当前系统关注的 assistant turn。字段里最重要的是：

- `turn_id`
- `turn_index`
- `started_at` / `ended_at`
- `interrupted`
- `asr_ttfb_ms` / `llm_ttfb_ms` / `tts_ttfb_ms`
- `e2e_latency_ms`
- `text_chars`

## `RuntimeMetricsCollector`
这是 session 级的运行时指标收集器。

### 状态字段
- `provider_metrics`
  保存每个 capability 对应的 `ProviderMetricSnapshot`
- `turns`
  保存已经开始过的 assistant turn 列表
- `active_turn`
  指向当前仍在进行中的 assistant turn
- `input_audio_bytes` / `output_audio_bytes`
  保存原始音频收发字节数

### 关键方法

#### `register_provider()`
在 session 启动阶段注册 provider 基础信息。

#### `start_assistant_turn()`
创建新的 `TurnMetricSnapshot`，并设置成 `active_turn`。

当前 turn id 规则是：
- 第一轮 `turn_1`
- 第二轮 `turn_2`
- 依此递增

#### `finish_assistant_turn()`
结束当前 assistant turn，补 `ended_at`，并清空 `active_turn`。

#### `mark_active_turn_interrupted()`
把当前 assistant turn 标记为被打断。

这个标记来自 `InterruptionFrame`，由 observer 在 frame 流中捕获。

#### `record_text_chars()`
累计 assistant 输出的文本字符数。

#### `record_ttfb()`
把 provider 的秒级 TTFB 转成毫秒并写入：
- provider 聚合样本
- 当前 active turn 的 capability 字段

#### `record_processing_time()`
记录 provider 处理耗时样本。

#### `record_turn_latency()`
记录当前 assistant turn 的端到端时延。

## 数据如何被填充
这个文件本身不主动监听任何 frame，所有写入入口都来自：

- `runtime.observers.RuntimePersistenceObserver`
- session 收口阶段对 serializer 音频统计的回填

## 读代码时要注意的点
- `active_turn` 只跟 assistant turn 绑定，不跟用户 turn 绑定
- `interrupted=True` 只表示 assistant 当前一轮被打断，不表示整通会话失败
- provider 指标是 capability 聚合，不是 processor 实例级别的原始明细
