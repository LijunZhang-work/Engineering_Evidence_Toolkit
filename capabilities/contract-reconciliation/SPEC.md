# Contract Reconciliation

状态：`DESIGNED`。

## 职责

将权威需求/设计、接口契约、实现字段和测试期望逐项对齐，形成一行一个义务的可追溯矩阵。适用于参数、信号、默认值、范围、单位、增益、枚举、buffer 布局、错误行为和兼容性。

## 非职责

- 不定义哪个来源权威；只消费 authority registry。
- 不把符号名相似当作语义一致。
- 不执行修复或用测试现状倒推需求必然正确。

## 独立入口

`reconcile_contracts(authority_registry, contract_sources, evidence_bundles?) -> contract_matrix`

## 输入与输出

每条 obligation 输出稳定 ID、权威原文位置、适用条件、生产端表达、传输表达、消费端表达、测试表达、变换规则、证据和状态。缺失协作者组件要引用 collaboration snapshot，状态为 `UNKNOWN/PENDING_EXTERNAL`，不能直接判错或判死代码。

## 失败关闭

类型、单位、增益、边界或版本任一无法对齐时，不得输出总体 `MATCHED`。仅有名字匹配或注释匹配不足以通过；必须列出未验证维度。

## Side effects

只生成矩阵和证据链接；不得改接口、代码、测试或文档。

## 验收要点

- 值相同但单位不同的 canary 被识别为 mismatch/unknown。
- 缺消费端不会被误报为无用字段。
- 每个 `MATCHED` 都可追到权威来源与实现位置。
- 汇总不会掩盖单项冲突和未知。

