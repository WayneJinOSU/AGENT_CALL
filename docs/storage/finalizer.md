# `storage/finalizer.py` 解释文档

## 文件与定位 (Overview & Purpose)
`storage/finalizer.py` 是会话落幕清算模块。此文件的核心职责是在一次 AI 对话完全结束或异常断开后，集中整理统计自 `metrics` 所有的运行时度量信息和资源，并利用数据库访问仓储类将结算快照持久化到关系型数据库中。

## 核心逻辑与类定义 (Core Classes / Functions)

### `Finalizer`
实例化该类时会被注入整个仓储库的句柄 `_repositories`。

**1. `finalize()`** (核心业务逻辑)
- 传入参数：包含全景状态的 `session_context` 和统计器 `metrics`。
- **服务监控数据的清理盘点**: 遍历整理所有上游（ASR, LLM, TTS）抛出的度量记录 `metrics.provider_metrics.values()`（比如 Token 使用了多少、首字用时多长等等），整理成可被写入的纯净字典列表并调拨 `provider_metrics.replace_for_session` 强制刷新数据库本回合并存储。
- **总控账单级汇总落地**: 抓取该对话会话的 `id`, `状态`, 最早的建立启动拨号时间戳至目前的时间并换算成跨度毫秒级时长。提取通话打点记录等基础档案以及音频上下行共处理的字节数，打包用 `upsert` （不存在新增，存在更新的形式）落地写入 `SessionRecord` 表。

## 模块依赖与关系 (Dependencies)
- **数据源**: 非常依赖从传参进来的 `RuntimeMetricsCollector` 及 `SessionContext` 中解构对象。
- **执行方**: 调用 `storage.repositories` 的相关异步入库函数执行真正的写盘操作。
