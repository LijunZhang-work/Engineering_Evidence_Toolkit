# Code Fact 架构与证据模型

规范状态：**DESIGNED**  
执行状态：**NOT_RUN**

## 1. 设计目标

Code Fact 的目标是让代码调查可复现，同时不把调用方绑定到某一种搜索引擎、图数据库、编译器索引、源码管理系统或 Review 流程。长期稳定的是 Capability Contract；Provider 只是完成特定证据方法的可替换实现。

整体分五层：

1. **查询契约**：说明问题、范围、所需置信程度和成本上限；
2. **快照契约**：固定仓库、修订、本地修改、生成输入和构建上下文；
3. **Provider 执行**：使用明确的一种或多种证据方法；
4. **证据归一化**：输出 Claim、位置、回执、上限和未解决项；
5. **调用方策略**：独立用户或组合 Profile 判断证据是否足够。

只有第五层可以把证据映射成门禁。Code Fact 只报告“已知、未知、部分支持或无法支持”，自己不宣布 Review 通过。

## 2. Stable Evidence Kernel

稳定内核应缓慢变化，只定义：

- `FactQueryRequest`；
- `WorkspaceSnapshot` 和可选 `BuildContext`；
- `ProviderReceipt`、`CoverageReceipt`；
- 标准化 Claim 与证据位置；
- `EvidenceBundle`；
- 明确的失败与不确定状态；
- Provider Artifact 的身份、新鲜度和覆盖；
- Content ID 与 Provenance ID 的分离。

Provider 特有的参数、安装命令、缓存、索引结构和配置不进入内核。

## 3. Provider Contract

每个 Provider 至少必须声明：

| 字段 | 含义 |
|---|---|
| `provider_id`、`provider_version` | 谁产生了结果 |
| `supported_query_kinds` | 声称可以回答哪些问题 |
| `derivation_methods` | 结果如何推导出来 |
| `required_inputs` | 所需快照、构建元数据、索引或凭据 |
| `artifact_id` | 使用的二进制/包/配置身份 |
| `deployment_id` | 具体部署实例（如有） |
| `index_id` | 语料/索引身份（如使用索引） |
| `coverage_model` | “搜过了”具体覆盖了什么 |
| `freshness_model` | 如何发现过期 |
| `known_ceilings` | 该 Provider 不能支持哪些结论 |
| `receipts` | 可重放的输入与调用证据 |

Provider 返回的是候选证据，不是最终真相。归一化层保留 Provider 原始回执，同时把材料转换成通用 Claim 格式。

## 4. Evidence Bundle

重要的 Evidence Bundle 至少应表达下面这些语义；不知道的字段也要显式写 `unknown`：

```yaml
bundle_id: run-local-unique-id
capability: code-fact
capability_contract_version: v1
query:
  request_id: ...
  normalized_question: ...
  query_kind: ...
scope:
  repositories: [...]
  paths: [...]
  symbols: [...]
  build_targets: [...]
snapshot:
  workspace_snapshot_id: ...
  content_id: ...
  provenance_id: ...
provider_runs:
  - provider_id: ...
    artifact_id: ...
    deployment_id: ...
    index_id: ...
    invocation_receipt: ...
claims:
  - claim_id: ...
    statement: ...
    derivation_method: SOURCE_READ
    assertion_source: CODE
    authority: CORROBORATING
    evidence_locations: [...]
    freshness: ...
    ceiling: ...
coverage:
  searched_scope: ...
  excluded_scope: ...
  completeness: UNKNOWN|PARTIAL|SUPPORTED_EXHAUSTIVE
unresolved: [...]
status: ANSWERED|PARTIAL|INCONCLUSIVE|...
```

真正的共享 Schema 由工具箱 `contracts/` 目录定义。这里是语义示例，不另造一套竞争 Schema。

## 5. 三条正交证据轴

### 5.1 推导方法

回答“这条观察是怎么得出的”：

- 直接读取源码；
- lexical search；
- Git/历史查询；
- parser 或 AST 推导；
- compiler semantic 推导；
- graph query；
- test/runtime observation。

### 5.2 断言来源

回答“支撑断言的材料是什么”：

- 代码；
- 构建元数据；
- 测试；
- 版本管理记录；
- 生成物；
- 注释或文档；
- 用户提供的输出；
- 模型推断。

### 5.3 权威性

回答“这份证据对当前问题有多少决策权重”：

- `AUTHORITATIVE`：在限定 Claim 和快照内属于治理依据；
- `CORROBORATING`：独立支持权威依据；
- `INDICATIVE`：是有价值的线索，但不能单独定论；
- `UNVERIFIED`：尚未验证或 provenance 不完整。

三条轴不能压成一个数字。例如，编译器推导的边可以很精确，但如果 compilation database 不是产品目标，它对产品构建仍然不权威。注释可以被工具准确找到，却仍然只是提示。

## 6. Content ID 与 Provenance ID

二者解决不同问题，必须同时存在。

### Content ID

回答：**本次到底检查了哪些字节或归一化内容树？** 可包含仓库内容、本地 patch、生成头、构建配置及其他与查询相关输入的摘要。

### Provenance ID

回答：**这些内容从哪里来，又如何被拼成当前工作区？** 可包含仓库 URL/ID、分支、commit、变更号、本地脏状态、submodule、LFS、稀疏检出规则、公司 workspace manifest 和工具回执。

相同内容可以有不同来源；相同 commit 标签也可能由于生成输入、submodule、LFS 或未提交 patch 而得到不同内容。因此 commit hash 不能单独充当完整工作区快照。

## 7. Artifact、Deployment、Index 与 Binding

它们是四种不同对象：

- **Artifact**：固定版本、通过完整性校验的二进制/包/容器及依赖锁；
- **Deployment**：在某个环境中安装和配置好的 Artifact；
- **Index**：针对固定语料和构建/Profile 范围生成的 Provider 数据；
- **Binding**：允许某个调用方/Profile 在指定证据上限下选择该 Deployment/Index。

它们的生命周期彼此独立：Artifact 验证过不代表已经部署；部署健康不代表 Index 新鲜；Index 新鲜也不代表严格 Profile 已批准使用。

## 8. 新鲜度与覆盖率

“工具刚刚跑过”不等于新鲜。新鲜度是以下对象之间的匹配关系：

- 查询所用 Workspace Snapshot；
- Provider 的语料/Index Snapshot；
- 构建或生成输入；
- Provider 配置；
- 如有，时间敏感的外部输入。

覆盖回执需说明包含与排除的仓库、文件、语言、生成源、构建目标、宏和条件分支。只有独立证明查询范围被穷尽后，“零结果”才可能支持“不存在”。

## 9. Provider 无关的执行顺序

1. 规范化问题，识别所需语义；
2. 冻结或引用 Workspace Snapshot；
3. 选择能够支撑所需结论的最低成本 Provider 集；
4. 不修改源码地执行 Provider；
5. 归一化证据并保留原始回执；
6. 策略要求时，对重要 Claim 交叉验证；
7. 输出答案、范围、证据上限和未解决项。

选择器可以使用 native search、`ripgrep`、Git、clangd 或外部图/索引 Provider。外部 Provider 是加速器，不是天然真相源。

## 10. 失败关闭

仅因为下面任一情况，Code Fact 都不能说“没有问题”“没有使用”“没有编译进去”“没有依赖”：

- Provider 返回零行；
- Index 漏了某个仓库；
- 当前构建目标未知；
- 生成头文件缺失；
- compilation database 来自另一个编译器或目标；
- Provider 崩溃、超时或悄悄跳过文件；
- 模型只根据命名推测关系。

正确结果应是 `PARTIAL`、`INCONCLUSIVE`、`BLOCKED_CONFIGURATION` 或 `BLOCKED_COVERAGE`，并准确写出缺什么证据。

## 11. 修改代码后的证据失效与增量刷新

任何源码、头文件、构建声明、生成输入或影响语义的配置发生变化后，绑定旧 `content_id` 的 Provider 证据立即失效。不能因为查询语句相同，就直接在旧索引上“重新查一次”。

对支持增量索引或增量刷新的当前绑定 Provider，必须执行下面的顺序协议：

1. **使旧证据失效**：把引用旧 `content_id` 的相关 Evidence Bundle 标成 stale/superseded，保留审计引用但不再用于新结论；
2. **计算刷新范围**：至少包含变更文件及其受影响依赖闭包；闭包的计算方法、方向、构建目标和未知边必须写入回执；
3. **执行增量刷新**：通过 Provider 的公共 Adapter/Contract 刷新，不由 Profile 硬编码某个 Provider 的命令；
4. **核验新绑定**：确认刷新后的 Index/Deployment 明确绑定新的 `content_id`，并核对相关 build profile、生成输入与配置身份；
5. **保存 Refresh Receipt**：记录旧/新 Content ID、变更集、依赖闭包、刷新方法、成功/失败、跳过项、Index ID 和时间；
6. **重新查询**：只有前五步满足后，才能用该 Provider 重新生成新证据。

如果 Provider 不支持增量刷新，或增量刷新失败、覆盖不完整、无法证明绑定到新 `content_id`：

- 该 Provider 对本次新快照的证据状态必须是 `STALE` 或 `BLOCKED_COVERAGE`；
- 可以立即回到 Native Search、`ripgrep`、Git 等一级 Provider，在它们各自证据上限内继续；
- 也可以按 Profile 明确批准的成本策略执行全量重建；
- 在全量重建验证完成前，不得继续使用旧 Index，也不得把旧结果包装成当前快照事实。

这条协议适用于 CodeGraph、clangd 或任何带缓存/索引的 Provider，但核心契约不硬编码任何一个工具的刷新命令。

## 12. 供应链边界

第三方 Provider 按可复现供应链处理：canonical source、固定 revision、锁定依赖、确定性构建或固定 Artifact、完整性回执，再经最外层运行边界批准的来源与通道进入受控部署。运行时“安装 latest”不属于本设计。

公司用于 pull、workspace、submit 的 Python 脚本属于 source-control adapter，不属于第三方 Provider 供应链。混在一起会让内核公司化，也会模糊“究竟是源码快照变化，还是证据工具变化”。
