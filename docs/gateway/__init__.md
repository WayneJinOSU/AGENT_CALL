# `gateway/__init__.py` 解释文档

## 文件与定位 (Overview & Purpose)
这是 Python 对网关层（`gateway`）的传统包标记文件。此文件主要被用来告知 Python 解释器 `gateway` 目录应该被当作一个可导入的 Python Package 处理。

## 核心内容与设计
它当前为空文件，并未在顶层向外导出特定的符号或者组件。它的存在使得别的目录里可以直接进行 `from gateway.websocket import router` 类似的相对/绝对路径引入。
