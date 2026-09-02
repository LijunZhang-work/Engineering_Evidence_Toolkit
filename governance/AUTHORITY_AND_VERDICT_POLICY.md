# 权威与裁决策略

## 1. 目的

本策略回答三个问题：什么可以作为依据、谁可以解释冲突、谁可以给出最终 Verdict。任何具体工具的输出都不天然拥有最高权威。

## 2. 权威是任务相关的

权威层级必须在 Profile 中按 Claim 类型声明。例如：

- 需求/协议语义：经确认的设计文档、接口契约、用户明确确认；
- 当前实现事实：冻结快照中的代码、构建系统、生成物声明；
- 实际构建结果：与目标画像匹配的真实构建日志；
- 运行行为：与目标版本和配置匹配的测试、运行日志、数据库记录；
- 外部失败：用户提供的失败 Artifact，在适用性未被证伪前必须保留；
- 搜索索引、代码图、clangd：用于发现和结构化取证，不自动高于源码或真实构建。

“官方工具”“知名工具”或“退出码为 0”都不是权威层级。

## 3. 角色权限

| 角色 | 可以 | 不可以 |
|---|---|---|
| Provider | 观察、采集、生成 Receipt、声明限制 | 给出任务最终 Verdict |
| Capability | 计算局部 Claim 状态和证据缺口 | 修改 Profile 门槛 |
| Profile Gate Engine | 按版本化规则计算 Gate | 改写原始证据或忽略冲突 |
| Reviewer | 复核证据、提出反证、签署审阅结果 | 无 Receipt 地宣布“没问题” |
| User / 授权负责人 | 确认范围、权威源、接受残余风险 | 被系统伪造确认 |

最终 Verdict 只能由 ENFORCE 模式下的 Profile Gate Engine 根据已固定规则产生；人工可以接受例外，但必须生成独立的、带理由与范围的 waiver，不得回写原证据为绿色。

### Authority Registry 不是自己的信任根

仓内 `TRUSTED_AUTHORITY_REGISTRY.yaml` 只是一份内容可寻址的 Authority 目录。RunBundle 中保存它的摘要只能证明“本次运行引用了哪一版”，不能证明该版本值得信任；Registry、pin 列表和 Bundle 不能互相给自己背书。

任何正式 RunBundle 校验都必须从外层运行边界取得仓外固定的 Registry 规范化摘要，或先验证由独立权限域签发的 Registry 签名。CLI 必须同时接收显式 Registry 路径和外部摘要；缺失或不匹配时 fail closed。仓内固定摘要只允许驱动 `ACCEPTANCE_FIXTURE`，不具有本地开发或公司资格 Authority。

## 4. Verdict 与其他状态分离

禁止用一个 `status` 字段承载所有含义。至少分离：

- `execution_status`：NOT_STARTED/READY/RUNNING/WAITING_HUMAN/BLOCKED/COMPLETED/FAILED/CANCELLED；
- `claim_status`：PROVEN/DISPROVEN/NOT_PROVEN/CONFLICTED/UNKNOWN/NOT_APPLICABLE；
- `gate_status`：PASS/FAIL/INCONCLUSIVE/NOT_APPLICABLE/WAIVED/NOT_EVALUATED；
- `final_verdict`：ACCEPT/ACCEPT_WITH_RISK/REJECT/INCOMPLETE/NO_VERDICT；
- `freshness_status`、`coverage_status`、`tool_qualification_status`；
- `collaboration_readiness` 与 `mutation_validation_status`。

执行完成不等于 Claim 成立，Claim 成立也不自动等于整体接受。
`BLOCKED` 只描述执行状态；Gate 缺证据或有冲突时使用 `INCONCLUSIVE`。
`WAIVED` 是有范围的风险处置，不是 PASS 证据。

## 5. 冲突裁决

证据冲突时按以下顺序处理：

1. 校验 `content_id`、`provenance_id` 和 Receipt 是否完整；
2. 比较快照、修订、目标、工具链、配置与时间范围；
3. 判断证据是否在同一 Claim 作用域；
4. 比较任务相关权威层级与证据上限；
5. 必要时执行可区分两种解释的新检查；
6. 记录被接受和被排除证据及理由。

若无法消解，Claim 保持 `CONFLICTED`。不得用“多数工具绿色”投票覆盖一个更相关的真实失败。

## 6. 用户外部证据

用户给出的错误日志、构建/测试结果、截图或描述必须先登记，再判断可用性：

- 原文/原文件保留，不改写；
- 记录用户声明的环境、版本、时间和复现步骤；
- 无法确认的字段标记 `UNKNOWN`；
- 本地检查只能补充或缩小范围，不能自动覆盖；
- 若其揭示本地预检环境不完整，应降低本地工具资格并重新评估既有绿色结论。

## 7. Profile 的裁决责任

每个 ENFORCE Profile 必须声明：

- 必需 Claim 与 Gate；
- 每个 Gate 可接受的权威层级、覆盖和新鲜度；
- 哪些 `UNKNOWN`/`NOT_PROVEN` 会阻断；
- 外部失败的适用性消解规则；
- waiver 权限、有效期和影响范围；
- 最终 Verdict 计算式；
- 专业版和小白版报告必须引用同一组事实标识。

没有这些声明的 Profile 只能用于 EXPLORE 或 EVIDENCE，不能宣称任务通过。
