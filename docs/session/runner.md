# `session/runner.py` 解释文档

## 文件与定位 (Overview & Purpose)
这是整个通话控制的核心中枢（“心脏模块”）。`run_session` 将前面介绍的网关接线、提供商选取、Pipecat管线的拼装和持久化仓促全部编排在一起，执行总调度流程。

## 核心流程与结构拆解 (Core Executions)

### 1. 工具链生成与准备环节
- `create_runtime_context`: 利用传入的 WebSocket 以及从它身上解包出的网络载荷生成带 UUID 的上下文 `SessionContext`。同时连接并组装数据库存取操作源实例。
- `create_services` & `create_transport`: 对下游隐藏复杂性，通过之前解析出来的厂商需求构造管线的服务和监听模块；从传输器获得字节拦截通道。

### 2. 状态扭转守卫体系 (System Guards)
- **拦截控制**: 构建一个给框架调用的内部函数 `request_stop(reason)`，统一拦截断网、业务故障以及结束指令，向安全机器报备并将下行帧流关闭收尾。
- **并行任务护航**: 提供异步任务 `max_duration_guard()` 来确保即使模型出问题了卡死也会在一定时长后强制释放。同时把“沉默追问”主逻辑交给 `SilenceDetector`，由它围绕 `BotStoppedSpeakingFrame` 启停等待窗口，并通过事件 `on_silence_detected` 驱动追问和最终挂断收口。

### 3. Pipecat 总干线启动 (`run_session()`)
- 当资源就位后，该流控制器被启动 `runner_task = asyncio.create_task(runner.run(task))`。
- 并给调用客户端返回第一帧安全启动的事件信号包 (`SessionReadyMessage`) 让客户端能够准备对向讲话。此后进入无限接收轮询并在最后抛出计算好的系统整体流量情况 (`metrics`) 并执行落地善后的任务 (`finalize_session`) 返回所有统计。
- 使用强力的异常拦截层进行失败处理(`finally`, `except`) 清理内存注册池内的任务和游离 Task 线程垃圾。

## 模块依赖与关系 (Dependencies)
- 这几乎是一个高维度的缝合器。依赖大量外部类，向上依靠网关投递包、向下使用管线装配与最终的基于 SqlAlchemy `repositories`（落库脚本）完成善后收容。
