---
document_status: DESIGNED
document_version: 0.1.0-draft
---

# Profiles：可选组合，不是能力本体

Profile 只回答一个问题：针对某类任务，要以什么顺序调用哪些独立能力、如何把能力公开输出映射为门禁和报告。它不是新的“大工作流”，也不是能力的唯一入口。

任何能力都可以脱离 Profile 单独调用。例如，日常搜索代码只调用 `code-fact`；修改前做影响面核查只调用 `build-dependency-audit`；准备测试追踪只调用 `signal-lineage` 与 `observability-planner`。只有当用户选择某个 Profile 时，Profile Runner 才按该组合配置执行。

## 不可跨越的边界

1. Profile 只能读取 Capability Contract 声明的公开输入、公开输出和 Evidence Bundle。
2. Profile 不得读取能力私有缓存、私有数据库、临时索引目录或实现内部状态。
3. Profile 不得直接调用 CodeGraph、clangd、编译器或其他 Provider；它只能向能力提出请求，由能力选择、验证并记录 Provider。
4. Profile 不得把“工具退出码为 0”直接改写成“代码正确”。它只能依据证据包里的有效性、覆盖度、环境等价性与结论上限。
5. Profile 负责组合与门禁，Capability 负责产出事实；两者不得互相越权。
6. Profile 版本、Capability 版本和运行实例相互独立。升级 Profile 不得静默改变历史运行结论。

## 当前设计的组合

| Profile | 用途 | 是否允许独立拆用能力 | 当前状态 |
|---|---|---:|---|
| `recovery-review` | 多仓遗留改动恢复、审查、证据化修复与无人值守检查 | 是 | DESIGNED |
| `safe-ai-edit` | 防止 AI 误删、截断、硬凑修复，并验证修改后结构与影响面 | 是 | DESIGNED |
| `ad-hoc-code-investigation` | 普通代码查找、依赖追踪、事实问答，不强制进入 Review | 是 | DESIGNED |
| `test-trace-preparation` | 设计 DT 侧静态追踪与业务侧观测方案，为后续真实测试留证 | 是 | DESIGNED |

所有 Profile 的机器可读入口均是其目录下的 `PROFILE.yaml`；执行顺序在 `RUNBOOK.yaml`。当前文件均为设计规范，不宣称已有 Runner 实现。
