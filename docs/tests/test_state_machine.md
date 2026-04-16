# `tests/test_state_machine.py` 解释文档

## 文件与定位 (Overview & Purpose)
用于测试验证项目中专门编写的控制会话状态不可逆推转逻辑类（状态机 `SessionStateMachine`）。

## 核心测试用例
- **`test_state_machine_happy_path`**: 重演一套从创建到接通到挂断的标准健康正向通话路线，并断言每一步其保存的状态是否和期望转移到的终态吻合。
- **`test_state_machine_rejects_invalid_transition`**: 直接新立一通电话，并在没有任何激活响应的前提下尝试将其突变飞转入直接说话状态（`ACTIVE`），系统如期拦截请求且被 pytest 抓到抛出 `InvalidStateTransitionError`，维护了业务数据安全。
