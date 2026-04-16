# `providers/factory.py` 解释文档

## 文件与定位 (Overview & Purpose)
`providers/factory.py` 是 AI 服务商整合工厂模块。针对不同的大模型 (LLM)、语音识别 (ASR)、和 语音合成 (TTS) 功能它定义并封装了对应服务提供商的调用。所有的底层提供商 SDK 将在这里被统一包装为标准化的 `FrameProcessor` 节点（以支持流框架 Pipecat）。

## 核心逻辑与类定义 (Core Classes / Functions)

### 1. `PipecatServiceFactory` (服务单例构造厂)
包含入口函数 `create_services`，返回 `(ASR, LLM, TTS)` 元组组成的管线节点。

- **ASR 支持**: 封装了 `DeepgramSTTService`，从配置抽取深知 (Deepgram) 所需参数（降噪、语言、通道、凭据）并将其配置。
- **LLM 支持**: 包含了与 OpenAI 兼容架构平台的适配体系代码 (`_create_openai_compatible_llm`)。支持接入正面的 `openai` 以及第三方聚合引擎 `openrouter`。
- **TTS 支持**: 目前深度绑定并封装了 `CartesiaTTSService` 作为先进声音的驱动，并内置配置和语速格式转化（pcm_s16le）。

### 2. 支持函数 (Helpers)
带有大量的带回退参数链的安全解构（例如 `_option`, `_required_secret_from_envs`）负责在环境变量 `.env` 或运行时配置字典中递归查找合法 API 凭据。

## 模块依赖与关系 (Dependencies)
- **底层驱动**: 主要由 `pipecat` 框架底层 `CartesiaTTSService`, `DeepgramSTTService`, 和 `OpenAILLMService` 支持运作。
