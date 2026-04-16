# `tests/test_provider_support.py` 解释文档

## 文件与定位 (Overview & Purpose)
`tests/test_provider_support.py` 是一份庞大的服务测试覆盖群。它非常缜密的检验了本系统极为复杂而深邃的人工智能第三方 API 模型整合与生成工厂逻辑（`providers.factory`）。

## 核心测试用例

### 1. `test_router_preserves_provider_options` 
确保即使对于部分未做深度定制的服务提供商，其选项属性字典也会原封不动的由路由器流转回原端点。
### 2. 核心大厂支持断言 (`deepgram_and_cartesia`, `openrouter`)
它利用 `pytest` 的 `monkeypatch` 模块暴力向系统中注入虚假的测试 API Keys 以触发认证。然后调用 `create_services` 组建服务工厂，并逐项严格地（`assert type(asr).__name__ == "..."`）断言返回的 LLM 和 ASR 的 Python 处理对象名字是否确确实实地是对应的 `DeepgramSTTService` 或符合标准架构接口的 `OpenAILLMService`。
### 3. 环境隔离和别名解析容错
- `test_factory_supports_generic_env_key_names`: 修改环境变量叫法，尝试将 `DEEPGRAM_API_KEY` 改为兜底用的默认泛用的 `ARS_API_KEY`，测试系统是否能平滑向下搜索找齐变量从而不崩。
### 4. 健壮性报错拦截 
- `test_factory_xxx_requires_api_key`: 故意撤下并抹除 Key 值。测试 `create_services` 在配置大模型连接但缺乏环境变量依赖的极端环境下，是否正常被抛出 `UnsupportedProviderError` 提示缺少票据。
