# `providers/registry.py` 解释文档

## 文件与定位 (Overview & Purpose)
`providers/registry.py` 是用于声明配置默认预设对象的地方，简单且小型的静态注册表。目前包含 AI 能力的基础档案的结构标记类型。

## 核心配置与数据类
- `ProviderProfile`: 是一个用于强类型标注某项模型资源档案的冻结配置类 (`@dataclass`)，含有一个必备字段 `provider` 和可选字段如指定的类型模型与指定声线。
- `DEEPGRAM_PROFILE`: V1 默认 ASR 档案。
- `OPENROUTER_PROFILE`: V1 默认 LLM 档案。
- `CARTESIA_PROFILE`: V1 默认 TTS 档案。
