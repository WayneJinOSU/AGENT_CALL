# `settings.py` 解释文档

## 文件与定位 (Overview & Purpose)
`settings.py` 是项目的核心配置中心模块。它通过读取环境变量信息（如 `.env` 文件），将其强类型化并封装为单例的 dataclass 对象，向整个系统（网关、引擎、路由等）提供一致的配置项读取接口。

## 核心类与配置表 (Core Classes)

### `Settings` (冻结数据类 `@dataclass(frozen=True)`)
利用 immutable 的特质定义所有的全局默认项级应用配置。
包含以下主要配置分组：

1. **基础信息**: `app_env`（环境），`app_name`（默认为 `AGENT_CALL`）。
2. **连接存储项**: `database_url` 提供 MySQL 的异步连接 URI，支持从环境变量提取或使用本地开发回退字符串。
3. **音频底层设定**: `default_audio_encoding` (默认 pcm_s16le)，`default_audio_sample_rate` (默认 8000Hz 电话级)，`default_audio_channels` (单向单通道 1)。
4. **会话默认项**: `default_session_type` (默认 `outbound_voice`)。

当前版本已移除 `reference` provider 相关开关，不再提供 fallback 配置项。

全局被实例化的 `settings: Settings = Settings()` 会用作配置进口。

## 模块依赖与关系 (Dependencies)
- 基于 python 的原生 `os` 和 `dataclasses` 进行对象构造。
- 借助 `dotenv` 提前载入本地的 `.env` 到虚拟环境内（`load_dotenv()`）。
