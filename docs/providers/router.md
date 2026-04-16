# `providers/router.py` 解释文档

## 文件与定位 (Overview & Purpose)
该文件执行提供商配置（Provider Selection）的最终解析（Routing），在外部请求参数（用户通过网关传入）和运行时服务构建之间起桥接作用。

## 核心逻辑与类定义 (Core Classes / Functions)

### 1. `ResolvedProviders`
强类型数据类容器，保存处理或确认后三合一能力最终由谁执行。具体保存最终选定的 `asr`，`llm`，`tts` 的供应方明文名字、模型和自定义配置字典。

### 2. `ProviderRouter`
包含了核心判定逻辑 `resolve(selection: ProviderSelection)`：
- 将 `asr/llm/tts` 的 provider、model、voice 与扩展 options 原样标准化到 `ResolvedProviders`。
- 不再包含 `reference` fallback 路径；V1 仅支持显式 provider 选择。

## 模块依赖与关系 (Dependencies)
- 上游请求的元信息依赖定义自 `schemas.provider.ProviderSelection`。
