# Code Fact 的独立使用与组合使用

规范状态：**DESIGNED**  
执行状态：**NOT_RUN**

Code Fact 是能力，不是必须整套跑完的 Workflow。同一个证据生产能力既可以回答开发者的临时问题，也可以服务依赖审计、Recovery Review 或后续的测试追踪 Profile。

## 1. 独立使用

独立调用方只需提供有边界的问题和范围，不需要先启动 Review 状态机。

例如：

```yaml
request_id: Q-LOCAL-001
mode: EVIDENCE
question: target product_x 下哪些翻译单元可能 include signal_limits.hpp？
query_kind: INCLUDE_REACHABILITY
scope:
  repositories: [business-cpp, shared-platform]
  build_targets: [product_x]
required_semantics:
  build_aware: true
allow_providers: [native-search, ripgrep, git, clangd]
```

如果没有有效的构建上下文，结果可以是 `INCONCLUSIVE`。这是准确且有价值的结果，不能为了给出“漂亮答案”而伪装成肯定结论。

适合独立调用的场景包括：

- 找信号的生产者与消费者；
- 查定义、引用、include 和构建声明；
- 检查重命名是否完整；
- 对照源码和 Git 历史；
- 设计讨论前收集事实；
- 调查用户提供的编译或测试错误；
- 不启动整套 Review，只准备一条数据链路的证据。

## 2. 被 Profile 组合

Profile 只能通过公共契约调用 Code Fact，并提供：

- 要调查的快照；
- 有边界的查询；
- 证据充分性政策；
- 允许的 Provider 与时间/资源预算；
- Evidence Bundle 的落盘位置。

Code Fact 返回证据与状态；Profile 再把状态映射到 Gate。例如，严格的 Recovery Review 可以把 `BLOCKED_COVERAGE` 当成硬门禁；普通探索则可以展示部分结果后继续。

Profile 不能直接读取 Provider 私有缓存或原生 Schema，否则 Provider 将无法替换。

## 3. 三种运行模式

| 模式 | 用途 | 允许的结果 | 决策者 |
|---|---|---|---|
| `EXPLORE` | 低成本找线索 | 明确标注不确定性的部分证据 | 人/调用方 |
| `EVIDENCE` | 生成可复现支撑 | Claim + 回执 + 范围 + 上限 | 人/调用方 |
| `ENFORCE` | 给严格 Gate 供应证据 | 相同契约，但必填字段更严格 | 调用 Profile |

`ENFORCE` 也不会把 Code Fact 变成判决器。它只是保证：要么返回调用策略要求的证据字段，要么明确失败。

## 4. Provider 选择集合

Provider 集是可替换 Binding，不是硬编码的产品等级。调用方可以定义：

- **Native**：native source access、`ripgrep`、Git；
- **Semantic local**：Native 加上针对指定构建上下文验证过的 clangd；
- **Indexed**：Native 加上一个或多个验证过的图/索引 Provider；
- **Company custom**：以上任一集合加公司自研 Provider 或 Adapter。

“Lite”“Full”可以作为 Benchmark cohort 的名字，却不能暗示 Provider 越多就越权威。选择集合要与查询语义和已证明的覆盖范围匹配。

## 5. Native Provider 永远是正式 Provider

外部图工具不可用时，不是“Code Fact disabled”。`native-search`、`ripgrep`、Git 仍按 Provider Contract 输出自己的证据与上限。反过来，图索引也不能替代每个问题中的直接源码检查。

能力可以组合多个 Provider，并把相互矛盾的结果保留下来交给 adjudication，不能暗中挑一个顺眼的答案。

## 6. 只允许 Thin Dispatcher

实现层可以有一个很薄的 Dispatcher：

1. 校验公共契约；
2. 把查询需求匹配到合格 Provider；
3. 记录选择理由；
4. 调用 Provider；
5. 归一化结果；
6. 输出回执。

它不能膨胀成巨型控制器，不能装入 Review 阶段、源码管理动作、报告文案、Provider 安装或隐藏启发式。这些分别属于 Profile、Adapter 和 Provider Package。

## 7. 与其他模块的边界示例

### Recovery Review

可以要求 Code Fact 证明符号归属、include reachability、消费路径、变更影响或缺陷 Claim 的证据。Recovery Review 自己拥有 Gate、严重度、修复政策和最终 Verdict。

### Safe AI Edit

可以在 patch 前后查询结构邻居和影响符号。删除预算、括号/分隔符检查、Diff 和验证要求属于 change-safety 能力。

### Signal Lineage

可以请求生产者、变换器和消费者的位置。值如何沿顺序传播、在哪一步发生转换、如何形成测试交接，则属于 signal-lineage 能力。

### Ad-hoc investigation

直接调用 Code Fact，问题回答完或明确无法回答后结束，不要求创建完整 Review 运行目录，只保留最低必要回执。

## 8. 禁止的捷径

- 不能把 Provider 名称本身当证据；
- 不能没有 Snapshot 对比就宣称 Index 新鲜；
- 不能用名字相似的目标替代缺失的构建元数据；
- 不能因为工具技术复杂就自动提高权威性；
- 不能把公司 pull/submit 脚本塞进 Evidence Kernel；
- 不能没有部署和验证回执就把示例 Provider 标成 `ACTIVE`；
- 不能把 validation campaign 计划写成已经完成的成果。
