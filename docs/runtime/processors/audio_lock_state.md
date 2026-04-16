# `runtime/processors/audio_lock_state.py`

## 作用
这是一个非常小的工具类，用来表示“音频合成或播报仍然处于忙碌窗口”。

它不依赖 Pipecat frame，也不直接参与当前主 pipeline。

## `AudioLockState`

### 状态
- `busy_until`
  用单调时钟保存忙碌截止时间

### 方法

#### `is_locked()`
判断当前是否仍处于锁定窗口。

实现上会加一个 `0.1s` 的缓冲，避免刚好卡在边界时出现抖动。

#### `extend_lock(duration_seconds)`
把锁窗口向后延长。

行为分两种：
- 如果当前时间已经超过 `busy_until`，从现在重新开始计时
- 如果当前仍在锁定中，则在原窗口上继续叠加

## 当前状态
这个工具类目前只是保留在代码库中，还没有接入 `runtime/pipeline_factory.py` 的主链路。

可以把它理解为：
- 为后续更细粒度的 TTS 播报互斥控制预留的本地状态模型
