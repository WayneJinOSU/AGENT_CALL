# `schemas/event.py` 解释文档

## 文件与定位 (Overview & Purpose)
`schemas/event.py` 定义了与核心生命周期流水线紧密相关的持久化事件枚举体和数据库保存前的数据层信封对象。它常用于在流框架的关键节点向数据库记录结构化状态时作强类型规范。

## 核心配置与枚举
- `EventType` (Enum): 一张包含着引擎全部重要生命节点的状态字典表。如创建（`SESSION_CREATED`）、就绪（`SESSION_READY`）、应用启动/崩溃、结束等等。
- `EventEnvelope` (BaseModel): 基于 Pydantic 定义的外层事件包装器。包含事件类型、自增序号和包含多维事件相关数据的万能 Payload 字典。
