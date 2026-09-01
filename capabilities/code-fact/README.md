# Code Fact：代码事实能力

规范状态：**DESIGNED**  
执行/基准状态：**NOT_RUN**

Code Fact 是工具箱中可以独立使用的代码证据能力。它把“这个值在哪里产生”“谁 include 了这个头文件”“实际选中了哪个定义”“这个符号是否发生过变化”等有边界的问题，转成带有可复现位置、调查范围、推导方法、新鲜度和证据上限的结果包。

它不是 Review 工作流，也不要求先启动 Recovery Review。开发人员平常搜代码、查依赖、讨论设计、检查多仓关系时都可以单独调用；Profile 可以组合它，但不能拥有或绑死它。

## 从哪里开始

| 需求 | 文件 |
|---|---|
| 理解稳定架构与证据模型 | [`spec/ARCHITECTURE_AND_EVIDENCE_MODEL.md`](spec/ARCHITECTURE_AND_EVIDENCE_MODEL.md) |
| 看独立使用和组合使用方式 | [`spec/STANDALONE_AND_COMPOSED_USAGE.md`](spec/STANDALONE_AND_COMPOSED_USAGE.md) |
| 查看 Provider 设计登记 | [`CAPABILITY_PROVIDER_REGISTRY.yaml`](CAPABILITY_PROVIDER_REGISTRY.yaml) |
| 理解 Provider 的三条生命周期 | [`lifecycle/PROVIDER_LIFECYCLES.md`](lifecycle/PROVIDER_LIFECYCLES.md) |
| 严谨判断 clangd 能证明什么 | [`providers/clangd.md`](providers/clangd.md) |
| 设计后续实测比较 | [`benchmark/BENCHMARK_AND_ADJUDICATION.md`](benchmark/BENCHMARK_AND_ADJUDICATION.md) |
| 查看真实项目验证计划 | [`roadmap/REAL_PROJECT_VALIDATION_CAMPAIGNS.md`](roadmap/REAL_PROJECT_VALIDATION_CAMPAIGNS.md) |
| 查看验收要求 | [`ACCEPTANCE.yaml`](ACCEPTANCE.yaml) |

## 真正稳定的部分

Code Fact 的稳定内核故意保持很小：

1. Provider 无关的查询契约；
2. 带回执和证据上限的证据包；
3. 可替换的 Provider；
4. 显式的工作区与构建快照；
5. 可检查新鲜度和覆盖率的 Provider 产物；
6. 分开的 Content ID 与 Provenance ID；
7. 对缺证据、部分证据和不确定结果“失败关闭”。

Provider 命令、分支、依赖、缓存路径和公司脚本都不是稳定内核。它们分别放进 Provider 或 Adapter 文件，替换时无需改写能力契约。

## Native 不是“没有高级工具时的弱降级”

`native-search`、`ripgrep`、`git` 是一级 Provider。没有图数据库、索引或语义引擎时，它们仍然工作，Code Fact 也没有“失能”。它们的证据上限可能较窄，但外部图工具也不会天然高于直接源代码证据。

`clangd` 是可选的本地语义 Provider。只有当 compilation database、目标、生成头文件、include 路径、宏、driver 与当前构建上下文匹配时，它的语义结果才有相应效力。它返回了符号结果，不等于它已经证明跨仓语义完整，也不等于产品编译一定成功。

## 证据必须拆成三个维度

每条重要 Claim 分开记录：

- **推导方法（derivation method）**：直接读源码、文本搜索、Git 查询、AST、编译器语义、图查询或测试观测。
- **断言来源（assertion source）**：代码、构建元数据、测试、版本记录、生成物、注释/文档、用户提供结果或模型推断。
- **权威性（authority）**：对当前这个问题是权威、佐证、提示，还是尚未验证。

不能把三者揉成一个“证据等级”。编译器感知索引里找到的注释仍然只是注释；过期图中的边仍然过期；直接看到一行源码可以证明文本存在，却不一定能证明它进入了当前产品目标。

## 事实状态用词

本目录刻意区分设计与现实：

- `DESIGNED`：契约或计划已经写出；
- `NOT_RUN`：没有附上执行证据；
- `REVERIFY_REQUIRED`：研究过的信息可能已变化，实际使用前必须重新确认。

这里列出的 Provider 没有任何一个因此就被视为已安装、已建索引、已验证或已绑定 Profile。示例中故意不使用 `ACTIVE`。

## 两份旧 Code Fact 文档如何合并

本模块吸收了早期 Code Fact 的可持续架构，以及后续“公司 Python 多仓适配、真实项目验证、clangd 补齐”的计划。后者现在明确放在 validation campaign 中，仍然是待执行计划，不能写成已落地成果。

公司拉取/工作区/提交语义放在 [`../../adapters/company-source-control/`](../../adapters/company-source-control/)；DeepSeek Harness 连接放在 [`../../adapters/deepseek-harness/`](../../adapters/deepseek-harness/)。这使 Code Fact 本身仍可在普通搜索、其他 Agent 或其他 Profile 中单独复用。
