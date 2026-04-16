# `storage/models.py` 解释文档

## 文件与定位 (Overview & Purpose)
`storage/models.py` 是 SQLAlchemy 的关系型数据物理表构造型模块（ORM）。通过强类型 Python 定义与实际 MySQL 服务器数据库中的列作全自动桥接映射。

## 核心逻辑与类定义 (Core Definitions)

包含基础基类 `Base(DeclarativeBase)` 衍生的五大核心数据库表：

### 1. `SessionRecord` (表: `session_record`)
主线大表。用来维护一次呼叫的极简主生命档案：存放记录比如系统会话标识符 (`session_id`)，用户终止理由，格式配置（语言、声频设定）以及各类重要切分时间节点（`created_at`, `ready_at`, `finalized_at`）。

### 2. `EventLog` (表: `event_log`)
密集且带有极高复用度的一张状态流失审计痕迹轨迹表。通过基于时间的插入方式，从各个外围捕捉被系统抛出的事件大信封记录到 JSON `payload_json`，是后续 BI 大盘和运维查表的“监控记录带”。

### 3. `SessionTurnMetrics` (表: `session_turn_metrics`)
回合级对话质量监控表。将长电话切为数个回合（Turn_0、1、2...），分别按字记录每一句的话的长短，是谁说的（Speaker），被强行插卡打断没有(`interrupted`)以及单独拆分的极细时延数据 (`asr_ttfb_ms` 等等)。

### 4. `SessionProviderMetrics` (表: `session_provider_metrics`)
核心 API 服务商能力消耗账单。跟踪一次电话花了多少外部大模型与音频处理的接口钱（统计请求体以及 `cost_usd` 字段等）。

### 5. `TranscriptLog` (表: `transcript_log`)
语音业务的绝对刚需库：逐句存放由 ASR 识别的和模型返回的声音翻译得到的文字档案以备留底审核等。包含类型以及信心度字段（`confidence`）。

## 模块依赖与关系 (Dependencies)
- 利用 `sqlalchemy` 与 `mapped_column`。
- 这是整个应用底层存储的数据地基，被 `storage.repositories` 引以调用操作。被 Alembic 读取出架构创建结构变更。
