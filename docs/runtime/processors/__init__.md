# `runtime/processors/__init__.py`

## 作用
这个文件只是 `runtime.processors` 子包的导出入口。

它把当前项目自定义处理器统一暴露为：
- `AudioLockState`
- `SilenceDetector`
- `VoicemailDetector`
- `WordAwareSanitizer`

## 为什么需要这一层
这样上层代码可以直接写：

```python
from runtime.processors import SilenceDetector, WordAwareSanitizer
```

而不需要逐个引用具体文件路径。

## 当前 processor 的角色分工
- `SilenceDetector`
  负责 bot 停止说话后的“等待用户回应”计时
- `VoicemailDetector`
  负责检测语音信箱并强制注入 voicemail 指令
- `WordAwareSanitizer`
  负责检测 assistant 结束语并启动挂断收尾
- `AudioLockState`
  负责提供一个简单的单调时钟锁窗工具，当前未接入主 pipeline
