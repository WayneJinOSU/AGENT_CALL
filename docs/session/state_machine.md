# `session/state_machine.py` 解释文档

## 文件与定位 (Overview & Purpose)
`session/state_machine.py` 提供了一种防止代码编写逻辑错乱的状态转换验证机器模块。通过定义状态路径有效集，约束由于系统异步交错导致的状态覆写乱象。

## 核心逻辑与类定义 (Core Classes / Functions)

### 1. `_ALLOWED_TRANSITIONS`
一个在模块级定义的允许字典映射。严格表明：
- 只能从 `CREATED` 跃迁向 `READY` 或 `FAILED`。
- `READY` -> `ACTIVE`... 以此类推，构建一个线性单向流水阀门引擎。

### 2. `SessionStateMachine`
封装并管控状态的对象：
- 提供一个具有防护能力的内部属性 `_state` 和其对应获取入口的计算属性。
- 采用唯一写入方法 `transition(new_state)`。它在接到变化请求时首先经过转换字典对照。如果违规（例如：试图将终态重新置为活跃状）则无情抛出内部防呆错误 `InvalidStateTransitionError`，维护引擎不崩塌。
