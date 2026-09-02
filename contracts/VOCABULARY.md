# 规范词汇表

本词汇表是文档和机器契约的共同语言。中文解释用于阅读，机器字段和值使用英文并保持大小写。

## 1. 核心对象

| 术语 | 机器名 | 定义 |
|---|---|---|
| 工具包 | `Toolkit` | 能力、Profile、契约、治理和 Adapter 的版本化集合；不是单一强制工作流 |
| 能力 | `Capability` | 可独立调用、通过公开 Contract 接收输入并产出事实或证据的模块 |
| Provider | `Provider` | 实现某项能力的具体工具或服务，只负责观察/推导，不拥有最终裁决权 |
| Adapter | `Adapter` | 把 Provider 私有输入输出转换为 Capability Contract 的薄适配层 |
| Profile | `Profile` | 面向某类任务的可选组合，声明能力绑定、Gate、权威与报告要求 |
| Runner | `ProfileRunner` | 唯一拥有调度、重试、恢复、Checkpoint、Instance State 和 Verdict 的运行控制面 |
| Claim | `Claim` | 有明确范围与判定条件、可以被证据支持或反驳的主张 |
| 证据包 | `EvidenceBundle` | 围绕一个 Claim 的 Artifact、Receipt、来源、限制与证据上限集合 |
| Receipt | `Receipt` | 检查、授权、边界决定、安装、激活、豁免或修改的一次类型化、不可含糊记录 |
| Artifact | `Artifact` | 源文件、日志、索引结果、diff、报告等可寻址内容对象 |
| Workspace Snapshot | `WorkspaceSnapshot` | 多仓修订、补丁集、工作区和构建画像的技术冻结描述 |
| Collaboration Snapshot | `CollaborationSnapshot` | 在 Workspace Snapshot 之后冻结交付模式、责任边界和代码到齐状态 |
| Gate | `Gate` | Profile 根据 Claim 和证据计算的局部门禁 |
| Verdict | `Verdict` | ENFORCE Profile 对整个运行给出的最终裁决 |
| Waiver | `Waiver` | 经授权接受某个已知 Gate 失败或风险的独立记录，不改变原始事实 |

## 2. 运行模式

| 值 | 含义 | 可否给最终 Verdict |
|---|---|---|
| `EXPLORE` | 找候选、建假设、缩小范围；启发式结果只作线索 | 否 |
| `EVIDENCE` | 形成带来源、覆盖、新鲜度和上限的证据 | 否 |
| `ENFORCE` | 由 Profile 依据固定规则计算 Gate 和 Verdict | 是 |

默认界面映射为 `快速探索 → EXPLORE`、`平衡取证 → EVIDENCE`、`严格门禁 → ENFORCE`。预设会展开成覆盖、交叉验证、鲜度、Canary、Provider 预算和结论权限等独立轴；它不是允许任意拔高结论的单一滑块。

## 3. 独立状态维度

### execution_status

描述任务/进程有没有执行完成，不描述结论真假。

`NOT_STARTED`、`BOOTSTRAPPING`、`READY`、`RUNNING`、`WAITING_HUMAN`、`BLOCKED`、`COMPLETED`、`FAILED`、`CANCELLED`；`BOOTSTRAPPING` 只负责从 BootstrapRequest 产生首个 Workspace Snapshot；Receipt 还可使用 `TIMED_OUT`、`SKIPPED`。

### claim_status

| 值 | 含义 |
|---|---|
| `PROVEN` | 在声明范围内已达到证明条件 |
| `DISPROVEN` | 已有足够反证 |
| `NOT_PROVEN` | 做过有效检查，但强度/覆盖仍不足 |
| `CONFLICTED` | 支持证据与反证尚未消解 |
| `UNKNOWN` | 必要输入、有效检查或适用性未知 |
| `NOT_APPLICABLE` | 有证据证明不适用于当前范围 |

`NOT_PROVEN` 和 `UNKNOWN` 都不等于成功；前者是“查了但不够”，后者是“不知道/没生效”。

### gate_status

`PASS`、`FAIL`、`INCONCLUSIVE`、`NOT_APPLICABLE`、`WAIVED`、`NOT_EVALUATED`。

`BLOCKED` 只属于执行状态，不属于 Gate。缺失关键证据或未决冲突使用 `INCONCLUSIVE`；`WAIVED` 表示风险被授权接受，不表示事实变为通过。

### final_verdict

`ACCEPT`、`ACCEPT_WITH_RISK`、`REJECT`、`INCOMPLETE`、`NO_VERDICT`。

### tool_qualification_status

`QUALIFIED`、`QUALIFIED_WITH_LIMITS`、`UNQUALIFIED`、`UNKNOWN`。工具资格必须针对 Capability、语料、构建画像和模式，不是永久全局荣誉。

### effectiveness_status

`EFFECTIVE_FOR_SCOPE`、`PARTIALLY_EFFECTIVE`、`INEFFECTIVE`、`UNKNOWN`。它回答“检查是否真正覆盖目标并在该范围有效”，与退出码、execution_status 分离。

### freshness_status / coverage_status

- `fresh` / `stale` / `unknown`
- `complete` / `partial` / `unknown`

## 4. 标识

| 标识 | 回答的问题 | 规则 |
|---|---|---|
| `content_id` | 内容是否相同 | 基于规范化内容哈希；路径改变不应改变它 |
| `provenance_id` | 内容从哪里、怎么来 | 基于来源、快照、采集链、工具和参数；同内容可有不同来源 |
| `snapshot_id` | 哪一次工作区冻结 | 关联所有 Repository、patchset 和构建画像 |
| `run_id` | 哪一次执行实例 | 关联 Profile/模式、状态、证据和报告 |
| `claim_id` | 哪一项待证明主张 | 在同一 Run 内稳定 |
| `evidence_id` | 哪一份证据包 | 可被多个 Gate 引用 |
| `receipt_id` | 哪一次具体执行 | 不等同 Evidence，也不直接决定 Claim |

不得用文件路径、commit、URL 或聊天消息 ID 同时替代 `content_id` 和 `provenance_id`。

## 5. 证据维度

### derivation_method

`direct_source`、`compiler`、`parser`、`language_server`、`graph`、`test`、`runtime_log`、`database_trace`、`authority_reconciliation`、`lexical`、`model_inference`、`user_supplied`。

### assertion_source

`code`、`build_system`、`test`、`runtime`、`authority_document`、`user_external`、`comment`、`model`、`derived_index`。

推导方法和主张来源是两条轴。例如 clangd 对源代码的解析可记录为 `derivation_method=language_server`、`assertion_source=code`。

### evidence_ceiling

证据上限说明该 Evidence 最多能支持什么结论。例如 Windows clangd 预检可以证明“在该编译数据库覆盖下未发现诊断”，不能证明“产品镜像全量编译一定通过”。

### authority_tier

权威层级由 Profile 按 Claim 类型定义。Provider 不得自封层级；“官方”“有名”“速度快”均不是层级依据。

## 6. 协作与代码到齐状态

### delivery_mode

`SOLO`、`COLLABORATIVE`、`MIXED`、`UNKNOWN`。

### collaboration_readiness

| 值 | 含义 |
|---|---|
| `ALL_EXPECTED_CODE_PRESENT` | 本次快照预期纳入的协作代码均已到齐 |
| `PARTIAL_EXPECTED_CODE` | 部分预期代码到齐，部分仍缺失 |
| `CODE_EXPECTED_LATER` | 已确认某些消费端/协作端尚未交付 |
| `UNKNOWN` | 尚未与用户或权威交付信息对齐 |

### code_availability

`PRESENT`、`PARTIAL`、`EXPECTED_MISSING`、`NOT_EXPECTED`、`UNKNOWN`。

`EXPECTED_MISSING` 不能被自动报成产品缺陷，但跨模块接口和端到端行为应保持 `NOT_PROVEN` 或 `UNKNOWN`。

## 7. 外部错误

`user_external` 表示用户提供的构建错误、测试失败、运行日志等。它的存在形成必须解释的反证义务：

- 本地绿色结果不得直接覆盖；
- 先核对快照、目标、工具链、宏、include、生成物和范围；
- 未完成适用性消解时，相关 Claim 为 `CONFLICTED`/`UNKNOWN`/`NOT_PROVEN`；
- 若确认不适用，必须有 Receipt 和明确理由，记录 `DOES_NOT_APPLY`，不能删除原证据。

## 8. 生命周期

规范对象：`DRAFT` → `CANDIDATE` → `ACTIVE` → `REVALIDATION_REQUIRED` / `DEPRECATED` → `RETIRED`。

迁移完成的旧规范使用 `SUPERSEDED`。`RETIRED` 和 `SUPERSEDED` 都保留历史与替代关系，不使用会抹去审计含义的“已删除”。

Provider 分为三条生命周期：

- `artifact_lifecycle`：供应链 Artifact；
- `deployment_lifecycle`：部署、索引和覆盖；
- `binding_lifecycle`：Capability/Profile 绑定许可。

## 9. 禁用模糊语句

以下表述不能单独作为结论：

- “看起来没问题”
- “工具没报错”
- “应该能编译”
- “CodeGraph 说有/没有”
- “本地是绿的，所以用户日志无关”
- “没找到消费者，所以没有消费者”
- “任务执行完了，所以通过”

应替换为可审计句式：

> 在 `workspace_snapshot_id` 对应的范围内，使用某 Capability/Provider 和固定配置覆盖了哪些对象；观察到什么；有哪些未覆盖项；该证据最多支持到何种 Claim 状态；是否存在外部反证或冲突。
