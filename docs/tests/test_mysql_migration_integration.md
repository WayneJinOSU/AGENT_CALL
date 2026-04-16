# `tests/test_mysql_migration_integration.py` 解释文档

## 文件与定位 (Overview & Purpose)
这是一份真实的系统集成测试样例文件（标记为 `integration`）。用于确实验证项目中的 Alembic 数据库迁移工具能够无报错地连接物理 MySQL 并还原初版建表操作。

## 核心测试逻辑
- 提供开关锁：通过嗅探环境变量 `RUN_MYSQL_INTEGRATION=1` 来决定是否直接跳过 (Skip) 当前测试，保证日常 CI 极速走通。
- **环境迁移测试**: 直接使用 python 的 `subprocess` 打包进程调用命令 `./.venv/bin/alembic upgrade head`，测试是否出抛跨包或依赖异常。
- **建库架构验证**: 迁移完成后，主动利用 SQLAlchemy 异步构造一条游标，执行原生语句查询 `information_schema.tables` ，暴力比对并断言我们预期的五大核心应用账单表 (`session_record`, `event_log`..) 是否已经毫无遗漏的被落库创建完毕。
