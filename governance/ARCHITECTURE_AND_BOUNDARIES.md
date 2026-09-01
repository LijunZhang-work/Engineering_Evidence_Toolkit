# 架构与边界

## 1. 定位

Engineering Evidence Toolkit 是一组可组合、可审计的工程事实与验证能力，不是一个不可拆分的“大工作流”。每个 Capability 都必须能够被独立调用；Profile 只是把若干能力、门禁和报告视图组合为某类任务的执行方案。

本文定义不可越过的架构边界。具体能力、Provider、Profile 和运行实例不得重新解释这些边界。

## 2. 分层模型

| 层 | 负责 | 不负责 |
|---|---|---|
| Capability | 接收明确输入，产出事实、证据或变更候选 | 决定整个任务是否通过 |
| Provider | 用具体搜索、解析、编译、图或 Memory 后端实现能力接口，并生成 Receipt | 拥有公司环境策略、赋予证据最终权威 |
| Adapter | 把 Harness、源码控制或外部系统映射到公共契约 | 读取 Provider 私有状态、创造业务结论 |
| Outer Runtime Boundary | 统一裁决网络、模型 API、密钥、外发、下载与制品来源 | 理解业务事实、选择结论或保存能力私有语义 |
| Evidence Kernel | 规范 Claim、Evidence Bundle、Receipt、冲突与上限 | 猜测缺失事实 |
| Profile | 选择能力、绑定规则、定义门禁与报告要求 | 篡改能力产出的原始证据 |
| Runner | 调度、恢复、超时、持久化实例状态 | 以“执行成功”替代“事实已证明” |
| Reporter | 把同一事实渲染为专业版或小白版 | 创造原始证据中不存在的确定性 |

## 3. 三种运行模式

### EXPLORE

- 目标是发现候选位置、建立假设、缩小搜索范围。
- 可使用启发式搜索、不完整索引或模型推断。
- 输出必须标记为 `CLUE` 或 `HYPOTHESIS`，不能作为通过门禁的唯一依据。
- “没有找到”只表示当前搜索未命中，不等于对象不存在。

### EVIDENCE

- 目标是形成可复查的 Claim、Evidence Bundle 与 Receipt。
- 每项结论必须声明快照、作用域、推导方法、覆盖度、新鲜度和证据上限。
- 证据不足时只能输出 `NOT_PROVEN` 或 `UNKNOWN`，不得补写一个看似完整的答案。
- Provider 的成功退出码只能证明工具执行成功，不能自动证明 Claim 成立。

### ENFORCE

- 目标是由 Profile 把证据映射为 Gate 与最终 Verdict。
- 只有 Profile 可以定义“何种证据足以通过哪个门禁”。
- 门禁规则必须版本化、可追溯、可复算；不得在运行中临时放宽。
- 有外部错误、证据冲突、关键输入未知或覆盖不足时，必须按规则阻断或降级，不得被局部绿色结果覆盖。

## 4. 独立性与组合规则

1. Capability 通过公开 Contract 交换数据，不读取其他 Capability 的私有目录或内部状态。
2. Capability 不得要求某个 Profile 存在才能运行；Profile 也不得复制 Capability 的实现逻辑。
3. Provider 可以替换；替换后只要满足同一 Capability Contract，消费者无需改动。
4. Profile 通过声明式清单绑定 Capability、Provider 约束和 Gate Rule，不得硬编码到 Provider。
5. 同一 Capability 可被日常检索、安全改码、遗留恢复、测试追踪等多个 Profile 复用。
6. 动态运行数据放入 `runs/<run_id>/`，不得回写静态规范或伪装成默认配置。
7. Capability 和普通 Adapter 只能声明环境访问需求；唯一的 Outer Runtime Boundary 返回允许、拒绝或未配置的 Receipt。内部模块不得复制公司环境规则。

## 5. Provider 禁止事项

Provider 只能报告“观察到什么、如何观察、观察范围与限制”。它不得：

- 输出最终 `PASS`、`SAFE`、`NO_PROBLEM` 等任务裁决；
- 把工具未报错解释为源码无错；
- 隐去编译器、头文件、宏、构建目标或索引覆盖不一致；
- 用本地预检绿色覆盖用户提供的失败日志；
- 把模型推断写成源代码事实；
- 在没有 Receipt 的情况下声称检查已经生效。

## 6. 标识与可复现性

- `content_id` 标识规范化内容本身；同样内容应得到同一标识。
- `provenance_id` 标识该内容从何处、在何种上下文、经何种链路取得；同样内容可能有多个来源标识。
- 两者必须分开保存。不得用文件路径、提交号或 URL 同时冒充内容和来源。
- 可复现运行至少固定：工作区快照、仓库与修订、构建/工具链画像、Profile 版本、Capability/Provider 版本、规则版本。

## 7. 失败关闭边界

以下情况不得宣称“没有问题”：

- 关键仓库、协作者代码、权威文档或构建输入状态未知；
- 检查使用的编译器、宏、头文件路径、生成文件或目标与目标环境不等价；
- 结构检查未覆盖修改文件，或大面积删除未被解释；
- 用户给出的错误与本地绿色结果同时存在且尚未完成适用性判定；
- Provider 失败、超时、索引过期或覆盖率不足；
- Claim 仅由假设、注释或模型推断支撑。

失败关闭不等于遇事停止。Runner 应继续执行仍可独立完成的诊断、收集反证并缩小未知范围；只有确实需要新增授权、秘密信息或不可替代用户决策时才进入等待。

## 8. 静态规范与运行实例

静态规范包括 `governance/`、`contracts/`、`capabilities/`、`profiles/` 和版本化 Adapter 说明。运行实例包括快照、日志、证据、差异、状态、报告和临时索引。

静态规范回答“必须如何做”；实例回答“这一次实际做了什么”。两者混写会导致示例被误认作真实状态，因此必须物理分离。

## 9. Memory 边界

Experience Memory 是可单独调用的 Capability，不是 Evidence Kernel 的隐藏状态，也不是每个 Profile 自动加载的全局提示词。它保存历史经验、适用条件、来源和纠错链；召回结果只能作为调查线索。

- 只有明确的记忆意图允许写入；通用总结不会静默持久化。
- 当前源码、构建、测试和用户新证据优先于历史 Memory。
- 旧经验被反证时追加 `WRONG / STALE / SUPERSEDED` 关系，不静默覆盖。
- Canonical 记录是人可读 Markdown；全文、向量或逻辑索引均为可重建派生物。
- Memory Provider、模型端点和 API Key 通过外层运行边界接入，不进入能力规格。

## 10. 首次环境资产对齐

第三方工具的源码路径、固定 Revision、制品路径与用途先登记在 `capabilities/third-party-supply-chain/ENVIRONMENT_ASSET_INVENTORY_TEMPLATE.md`。供应链能力负责检查“有什么、是否匹配”；外层运行边界负责裁决“能否下载”；用户负责在三种处理策略中确认授权和影响接受。

可选 Provider 缺失时，Runner 继续执行 Native Provider 和所有独立任务。只有本次必需且没有合法替代路径的范围被标为 `BLOCKED/NOT_PROVEN`，不得全局冻结。
