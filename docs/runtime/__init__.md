# `runtime/__init__.py`

## 作用
`runtime` 包承载整条 Pipecat 运行时链路的核心实现，负责四件事：

- 装配 pipeline
- 适配 WebSocket 传输
- 把关键帧转换成持久化和指标
- 提供一组文本级控制处理器

`runtime/__init__.py` 本身没有业务逻辑，只是把这一层标记为 Python package。

## 目录说明
- `pipeline_factory.py`
  负责把 transport、processors、LLM/TTS/STT、observer 装成一条可运行的 `PipelineTask`
- `transport.py`
  负责把北向协议消息转成内部控制帧，并创建底层 `FastAPIWebsocketTransport`
- `observers.py`
  负责把 Pipecat 的 frame/metrics 事件映射到数据库与内存指标
- `metrics.py`
  负责维护一次 session 的 provider 指标和 assistant turn 指标
- `processors/`
  放项目自定义的文本级和控制级处理器

## 当前最关键的控制链路
runtime 层里有三条最容易出问题、也最需要读文档时重点关注的链路：

1. 打断链路
   `runtime.pipeline_factory.build_user_aggregator_params()` 同时控制 `PipelineParams.allow_interruptions`、`LLMUserAggregatorParams.user_mute_strategies`、`user_turn_stop_timeout` 和 `SileroVADAnalyzer.stop_secs`
2. 沉默追问链路
   `runtime.processors.silence_detector.SilenceDetector` 只在 bot 真正停止说话后开始计时，并在用户开始说话或 bot 重启播报时取消
3. 挂断收尾链路
   `runtime.processors.word_aware_sanitizer.WordAwareSanitizer` 检测告别语，先发 `on_hangup_started` 给 runner 关闭沉默检测，再在下游推 `EndFrame`
