# `app.py` 解释文档

## 文件与定位 (Overview & Purpose)
`app.py` 是整个 FastAPI 应用的入口脚本。它主要负责组装和初始化应用，挂载各类路由（例如 WebSocket 相关的网关路由），以及管理应用的生命周期操作（如数据库生命周期连接的建立与断开）。

## 核心逻辑与类定义 (Core Functions)

### 1. `_lifespan(_: FastAPI)` (异步上下文管理器)
- **作用**: 用于管理 FastAPI 应用的完整生命周期。
- **逻辑**: 在应用启动时调用 `init_db()` 初始化数据库连接相关资源；在 yield 产生上下文提供服务后，无论如何最后都会在应用停止时通过 `finally` 调用 `close_db()` 优雅断开数据库连接。

### 2. `create_app() -> FastAPI`
- **作用**: 应用工厂模式，创建并配置应用实例。
- **逻辑**: 设置应用的基本信息（如应用名为 `AGENT_CALL`，版本为 `0.1.0`），挂载刚才声明的生命周期上下文 `_lifespan`，并加载网关层的路由 `websocket_router`，最终返回该 FastAPI 实例。

## 模块依赖与关系 (Dependencies)
- 依赖于第三方的 `FastAPI` 框架。
- 下游依赖 `db.py` 提供的数据库生命周期钩子函数 (`init_db`, `close_db`)。
- 引入本应用子模块 `gateway.websocket.router` 进行请求分发。
