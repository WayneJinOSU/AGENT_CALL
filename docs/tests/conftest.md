# `tests/conftest.py` 解释文档

## 文件与定位 (Overview & Purpose)
`tests/conftest.py` 是 pytest 库原生的自动执行全局测试配置文件。它保证了在其同级或下级目录在执行单元测试时提前挂载所需的设置或钩子函数。

## 核心配置与定义
包含 `pytest_configure(config)`:
其定义和显式注册了一个测试标记器 `@pytest.mark.integration`。使得整个测试体系内可以利用 CLI 的 `-m` 开关针对性剥离并决定是否只挑出依赖真正 MySQL 强依赖和慢连接的集成测试。
