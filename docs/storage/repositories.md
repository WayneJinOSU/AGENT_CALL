# `storage/repositories.py` 解释文档

## 文件与定位 (Overview & Purpose)
`storage/repositories.py` 是数据库访问层仓库模块。提供封装并对外暴露简单的面向对象式 API，专门进行单表查询、更删改的原子化和批量操作，实现底层数据库存根 (`db.py` 中 `SessionLocal`) 逻辑的抽离，降低主线程耦合。

## 核心逻辑与类定义 (Core Classes / Functions)

分别对应着 `models.py` 中五张主要关系表封装了五个专柜管理器：

### 1. `EventLogRepository`
提供 `append()` 方法：每次接受相关轨迹和 payload 时新建一个随机的系统 UUID 记录编号组装保存进主库，为事件系统服务。

### 2. `TranscriptLogRepository`
提供 `create()`：用来做极其高并发（可能每说一个字都会落一条 interim 消息）的转录消息落地持久化插表。

### 3. `SessionTurnMetricsRepository`
包含智能融合入库 `upsert()`：依据会话 `session_id` 和细分 `turn_id` 做排斥查找。若存在则更新状态，若无则新建。

### 4. `SessionProviderMetricsRepository`
包含毁灭重建函数 `replace_for_session()`：专门用来给收尾终结器批量使用。暴力用新状态删除之前写入的可能存在误差的供应商消耗打点对象。

### 5. `SessionRecordRepository`
也为 `upsert()` 逻辑：查询库里这条单调长表是否被建立，没有则建立，存在即仅替换发生值改变的新变量键。

### 整柜与实例化
定义了不可变的捆绑结构器 `@dataclass(frozen=True) class Repositories` 将上面的仓库实例一把包裹，通过对暴露出的全局单例工厂 `create_repositories()`，返回包含它们 5 者的全局字典给外部进行操作接驳。

## 模块依赖与关系 (Dependencies)
- 主要执行来自 SQLAlchemy 原生库中的 `select` 发射操作。
- 采用本项目的 `db.SessionLocal()` 和 `models.py` 内的关系映射实体运行事务。
