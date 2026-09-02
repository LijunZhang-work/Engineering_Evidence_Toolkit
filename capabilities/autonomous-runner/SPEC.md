# Autonomous Continuation Policy

状态：`DESIGNED`。为保持 Capability ID 兼容，目录仍名为 `autonomous-runner`，但它不再是第二套 Runner。

## 唯一控制面

`composition/PROFILE_RUNNER_CONTRACT.yaml` 是唯一拥有任务调度、重试、Checkpoint、Instance State 持久化和 Verdict 重算的控制面。本能力是无状态的策略求值器：

`evaluate_continuation(instance_state, authority_envelope, stop_policy) -> continuation_decision`

它回答当前是否仍有 READY/可重试任务、等待用户是否有充分理由、预设停机条件是否真的成立。它不能执行任务、调用 Provider、写 Checkpoint 或修改 Instance State。

## 决策规则

- 仍有 READY 或安全可重试项时返回 `CONTINUE`。
- 一个分支受阻不能冻结不相关 READY 项。
- `WAITING_HUMAN_JUSTIFIED` 仅限缺少新增权限、密钥、不可恢复输入或会改变产品语义的用户唯一选择，并必须引用诊断 Receipt。
- 时间/资源预算耗尽可以返回 `STOP_CONDITION_MET`，但最终结果只能诚实地进入 `INCOMPLETE` 或 `NO_VERDICT`。
- 任务图循环、状态引用损坏、授权边界不明或无法证明停机条件时返回 `INVALID_STATE/UNKNOWN`。

## 非职责

- 不拥有调度循环、恢复令牌、重试计数或持久化格式。
- 不生产代码事实、Gate 或最终 Verdict。
- 不自行扩大任务范围、权限或进行外部操作。
- 不把“已经有一些结果”当作停机条件。

## 验收要点

- 有 READY 项却建议停止的样本必须失败。
- 阻塞项没有诊断 Receipt 时不能建议等待用户。
- 同一输入产生确定的 Continuation Decision。
- Profile Runner 能调用本能力，但本能力不能反向调用 Runner。
