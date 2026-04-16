# `schemas/session.py` 解释文档

## 文件与定位 (Overview & Purpose)
此文件提供业务最基础的属性描述符集、常量集与内联参数定义集。它是连接各个模块的核心公用常数和格式要求。

## 核心业务定义表

### 1. 状态记录枚举 (Status Constants)
- `SessionStatus`: 包含了业务级流状态：从 `CREATED` 经过 `ACTIVE` 走到 `HANGING_UP` （挂断处理中）并最终导向 `ENDED` 或 `FAILED`。
- `TerminationCode`: 面向日志和外部系统的中止理由黑匣子记录码，比如静音超时（`silence_timeout`）、到达最大时间被迫切断(`max_duration_reached`) 或 上游供应商错误 (`provider_error`)。

### 2. 会话内部装配约束子集 (Payload Components)
- `ConversationConfig`: 关于此通交流本身的环境设置。包括语言以及核心系统 Prompt。
- `MediaConfig`: 被打上了硬核校验钩子（`@field_validator`）。在现有的 V1 版本强迫校验仅支持 `pcm_s16le`、`8000` Hz，以及仅限单声道 `channels=1`。不合法会阻断连接建立。
- `RuntimeConfig`: 给底层引擎用的功能配置，比如打断机制（`barge_in=True`）、机器人说完后的反应缓冲（`post_bot_grace_ms`）、等待用户回应的超时窗口（`user_response_timeout_ms`）、沉默追问轮数（`max_silence_follow_ups`）以及整通会话的大时长上限。
- `MetadataPayload`: 提供开放式字段存放业务 ID 和被叫方电话等补充说明数据供最后落库使用。
