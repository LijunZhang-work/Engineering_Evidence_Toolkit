# 证据宪章

## 1. 核心原则

1. **先声明 Claim，再收集证据。** 没有明确对象、范围和判定条件的“检查”不可审计。
2. **事实、推断、假设分层。** 源码观察不等于行为事实，工具推断不等于权威结论。
3. **未知必须保留。** `UNKNOWN` 和 `NOT_PROVEN` 是合法结果，不得为了完整答卷改写为 `PASS`。
4. **证据带边界。** 每份证据必须说明快照、作用域、方法、覆盖、新鲜度、限制与适用工具链。
5. **冲突不被平均。** 相互矛盾的证据进入 `CONFLICTED`，必须解释适用性后才能裁决。
6. **外部失败优先保留。** 用户提供的真实错误、日志或复现结果不能被较弱的本地绿色检查覆盖。

## 2. Claim 状态

| 状态 | 含义 |
|---|---|
| `PROVEN` | 在声明的范围和判定条件下，已有足够、可追溯且无未决冲突的支持证据 |
| `DISPROVEN` | 已有足够反证证明 Claim 不成立 |
| `NOT_PROVEN` | 已执行部分检查，但证据强度或覆盖不足以证明 |
| `CONFLICTED` | 支持证据与反证同时存在，尚未完成适用性消解 |
| `UNKNOWN` | 缺少必要输入、能力未生效或未执行有效检查 |
| `NOT_APPLICABLE` | 有证据证明该 Claim 不适用于当前范围；必须写出理由 |

`UNKNOWN` 表示“尚不知道”；`NOT_PROVEN` 表示“做过检查但仍未达到证明门槛”。二者均不是成功。

## 3. 证据强度不是单轴等级

不得把所有证据压成一个模糊的 L0–L5。至少分别记录：

- `derivation_method`：direct_source、compiler、parser、language_server、graph、test、runtime_log、database_trace、lexical、model_inference；
- `assertion_source`：code、build_system、test、runtime、authority_document、user_external、comment、model；
- `verification_status`：verified、partially_verified、unverified、invalidated；
- `freshness_status`：fresh、stale、unknown；
- `coverage_status`：complete、partial、unknown；
- `authority_tier`：由权威策略定义，不由 Provider 自封；
- `evidence_ceiling`：该证据最多能支持到什么结论。

## 4. Evidence Bundle 最小组成

一份可进入 EVIDENCE/ENFORCE 的 Evidence Bundle 至少包含：

- 被检验的 `claim_id`；
- 独立的 `content_id` 与 `provenance_id`；
- `workspace_snapshot_id`、仓库/目标/文件/符号作用域；
- Capability、Provider、配置与版本；
- 推导方法、覆盖、新鲜度、权威层级、证据上限；
- 原始 Artifact 位置及其摘要；
- 至少一个 Receipt，记录命令、输入、退出码、时间和限制；
- 支持/反驳方向与可复查说明；
- 未解决冲突、缺口与下一步。

## 5. 内容标识与来源标识

### content_id

`content_id` 由规范化后的字节内容计算，例如 `sha256:<hex>`。换路径、换存储位置但内容相同，`content_id` 不变。

### provenance_id

`provenance_id` 由来源链计算，至少纳入：原始位置/系统、仓库与修订、采集时间、采集者、工具与版本、输入参数、父级 Receipt 或 Artifact。内容相同但来源不同，`provenance_id` 可以不同。

这两个标识用于不同问题：前者回答“是不是同一份内容”，后者回答“这份内容是怎么来的”。

## 6. 外部错误与本地绿色的冲突规则

用户提供的失败日志、测试结果或构建错误记为 `user_external` Evidence。它不能被“本地未复现”“静态检查通过”“另一个编译器无报错”直接否定。

只有在以下事项均有 Receipt 时，才可把外部错误判定为不适用于当前 Claim：

1. 修订/补丁集一致性已核对；
2. 目标、编译器、版本、宏、头文件、生成物和依赖画像已核对；
3. 错误关联文件、符号和执行路径已核对；
4. 有确定证据指出外部错误来自不同范围、已修复修订或无关环境；
5. 适用性结论由 Profile 规则计算，而非 Provider 口头判断。

在完成之前，相关 Claim 状态至少为 `CONFLICTED` 或 `NOT_PROVEN`，相关 Gate 不得通过。

## 7. “工具运行成功”与“检查有效”分离

Receipt 的 `exit_code = 0` 只证明进程成功结束。有效性还要求：

- 输入文件确实覆盖目标变更；
- 配置与目标环境满足声明的等价范围；
- 解析器/编译器实际消费了相关文件，而非跳过；
- 索引与快照一致且覆盖可量化；
- 输出被正确解析，警告未被静默丢弃。

任一关键条件未知时，检查有效性为 `UNKNOWN`，不得输出“无错误”。

## 8. 反证义务

对于高风险结论（例如“删除安全”“接口兼容”“编译无误”“修改可交付”），应主动寻找反证：

- 大面积删除、括号/预处理结构破坏、函数边界变化；
- 声明存在但目标未编译、include 路径不生效、传递依赖偶然可见；
- 生产者/消费者类型、单位、范围、默认值、增益、时序不一致；
- 本地预检与目标构建画像差异；
- 协作者代码尚未到齐导致的假阴性或假结论。

找不到反证不等于证明安全；仍需满足 Claim 的正向判定条件。
