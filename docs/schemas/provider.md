# `schemas/provider.py` 解释文档

## 文件与定位 (Overview & Purpose)
这是一个针对 “供应厂商设置” 提供的 Pydantic 参数强类型校验载体。被网关使用以提取请求中指定模型 API 的片段。

## 核心配置与类
- `ProviderConfig`: 声明了一个基础服务的最少需要求：服务商名称（`provider`）、以及可能带有的具体的模型号 (`model`) 或者特定声线 (`voice`)。
- `ProviderSelection`: 定义为将上面的基座套用到此大模型电话系统的具体三个主要应用域，即指派给： `asr`（识别）、`llm`（语言模型）和 `tts`（语音生成）。
