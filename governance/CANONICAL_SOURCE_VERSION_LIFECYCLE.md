# 规范源、版本与生命周期

## 1. 唯一规范源

本文件夹成为后续维护的规范入口后：

- `00_START_HERE.md` 负责路由，不复制各能力完整规则；
- `governance/` 定义全局不可变边界；
- `contracts/` 定义机器可读交换契约；
- `capabilities/` 定义独立能力；
- `profiles/` 定义可选组合与 Gate；
- `adapters/` 定义可替换 Provider；
- `runs/` 只保存实例事实。

原有单体文档保留为历史资料，由迁移映射标记为 `SUPERSEDED`，不得同时继续作为活跃规则源。

## 2. 版本对象

以下对象分别版本化，不共享一个含糊的“工具包版本”：

- Toolkit release；
- Governance policy；
- JSON Schema / Contract；
- Capability manifest 与实现；
- Profile manifest、Gate Rules；
- Provider adapter 与供应链 Artifact；
- Workspace Snapshot 与 Run Instance。

静态对象使用语义版本或明确版本号；动态实例使用不可变 ID 和时间戳。

## 3. 兼容性规则

- Major：删除/重命名字段、改变语义、收紧导致既有合法输入失效，或改变 Verdict 计算；
- Minor：新增可选字段、能力、Provider 或向后兼容规则；
- Patch：澄清文字、修正不改变语义的错误、更新示例。

消费者必须声明可接受的版本范围。不得以“最新版本”替代固定版本。

## 4. 生命周期状态

| 状态 | 含义 |
|---|---|
| `DRAFT` | 设计中，不可用于强制裁决 |
| `CANDIDATE` | 契约稳定，等待验收 |
| `ACTIVE` | 已通过要求的验收，可被 Profile 绑定 |
| `REVALIDATION_REQUIRED` | 环境、依赖或证据变化，必须复验 |
| `DEPRECATED` | 仍可读/有限使用，但不得新增绑定 |
| `RETIRED` | 不再运行，保留审计记录和替代关系 |
| `SUPERSEDED` | 规范内容已迁移到新的唯一来源 |

不得删除生命周期记录。`RETIRED` 比“REMOVED”更准确，因为审计链仍须可见。

## 5. Provider 的三个生命周期

不得把 Provider 生命周期混成一个状态，至少分别记录：

1. `artifact_lifecycle`：源码/二进制供应链 Artifact 是否固定、验证、弃用；
2. `deployment_lifecycle`：是否已部署、索引是否新鲜、覆盖是否合格；
3. `binding_lifecycle`：哪些 Capability/Profile/语料/构建画像当前允许绑定。

Artifact 已验证不代表当前索引可用；Provider 可运行也不代表某 Profile 允许用它裁决。

## 6. 晋级与降级

从 `CANDIDATE` 晋级 `ACTIVE` 至少要求：

- Contract 测试、失败注入与 Schema 校验通过；
- 真实项目用例验证，包含正例、反例与未知；
- 固定供应链、版本和复现步骤；
- 性能数据声明样本、重复次数、冷热启动、超时与裁决方法；
- 退出/替换演练证明不会污染消费者。

以下事件触发 `REVALIDATION_REQUIRED`：工具/编译器升级、目标画像变化、索引快照变化、Schema Major 变化、真实失败与既有绿色结论冲突、供应链 Artifact 变化。

## 7. 变更流程

规范变更必须包含：变更动机、影响对象、兼容性判定、迁移说明、验收证据和回滚策略。改变 Gate/Verdict 的变更还需独立 Reviewer 签署。

版本发布后，运行实例只能引用固定版本；禁止静默追随工作区中尚未发布的文件。
