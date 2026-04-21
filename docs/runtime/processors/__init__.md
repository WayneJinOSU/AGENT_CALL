# `runtime/processors/__init__.py`

## 作用
这个文件只是 `runtime.processors` 子包的导出入口。

它把当前项目自定义处理器统一暴露为：
- `AudioLockState`
- `EmergencyInterruptProcessor`
- `InterruptDeduper`
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
- `EmergencyInterruptProcessor`
  负责 assistant 播报期间的高优先级 stop 关键词打断
- `InterruptDeduper`
  负责维护最近用户句子窗口，给普通 barge-in / 关键词打断提供重复句抑制
- `VoicemailDetector`
  负责检测语音信箱并强制注入 voicemail 指令；命中时如果 bot 正在播报，会先走一次中断
- `WordAwareSanitizer`
  负责检测 assistant 结束语并启动挂断收尾
- `AudioLockState`
  负责提供一个简单的单调时钟锁窗工具，当前未接入主 pipeline
