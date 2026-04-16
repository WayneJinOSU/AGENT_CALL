# `session/context.py` 解释文档

## 文件与定位 (Overview & Purpose)
`session/context.py` 定义了一个贯穿于整个通话存活周期的“应用级上下文容器”实例 (`SessionContext`)。它被生成于一次通讯拨通时的第一刻，伴随着请求随处流动。

## 核心配置与行为
- 它的内部携带有关键引用句柄（如保持存活需要的 `websocket`），标识符：`session_id` 与跨链路追踪专用的 `trace_id`。
- **状态追踪器**: `status` （通过刚才提到的状态枚举不断流转），并携带开始于结束时间戳（`created_at`, `ready_at`, `ended_at` 等）。
- **递增发号器**: 提供了一个实例方法 `next_sequence()` 用做发送或落进库里每一条消息的绝对时间轴排序，保障查询系统不乱序。
