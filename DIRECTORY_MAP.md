# 目录地图与职责索引

本文件回答两个问题：**东西放在哪里**，以及**为什么不能放到别处**。它是导航说明，不复制各模块的 Canonical 规则。

```text
Engineering_Evidence_Toolkit/
├── 00_START_HERE.md                # 唯一人工入口与任务路由
├── TOOLKIT_MANIFEST.yaml           # 可机器发现的模块清单与边界
├── CURRENT_STATE.yaml              # 规格/实现/验证/激活四维真实状态
├── DIRECTORY_MAP.md                # 本文件
├── governance/                     # 跨模块不变量与权威政策
├── contracts/                      # 最小共享对象 Schema
├── capabilities/                   # 可单独调用的长期能力
├── adapters/                       # 外部环境、Harness、源码控制与唯一运行边界接缝
├── profiles/                       # 可选能力组合；不是默认入口
├── composition/                    # 薄 Runner 的公开契约与实例结构
├── dashboard/                      # 由证据状态自动生成的轻量能力拼图看板
├── acceptance/                     # 事故样本、负向题与预期结果
├── migration/                      # 三份旧文档的冻结、映射与退役凭证
├── roadmap/                        # 从 DESIGNED 到 ACTIVE 的建设计划
└── runs/                           # 仅说明外部运行产物布局，不存真实运行数据
```

## 1. `governance/`

只放所有能力都必须遵守、但不属于任何一个业务能力的规则，例如：

- 证据与结论的关系；
- 权威来源和冲突裁决；
- 修改授权与业务源码边界；
- 合入文本的仓库读者视角，以及 behavior/BEH 的无歧义命名；
- Canonical Source、版本和生命周期；
- 第三方工具源码、业务源码、Runtime 产物的物理隔离。

这里不放 CodeGraph 命令、不放 Review 阶段，也不放某次任务状态。

其中 `REPOSITORY_READER_AND_NAMING_POLICY.yaml` 是代码修改后的共享门禁：会话局部审批语、修改轮次和私人编号不得进入合入候选；表达通用 behavior 的标识必须使用完整拼写，BEH 保留给真实专名。

## 2. `contracts/`

只保留跨模块交换所需的最小对象：Toolkit、Capability、Profile、Workspace Snapshot、Evidence Bundle、Claim、Receipt 和 Instance State。

模块自己的细节 Schema 归模块所有。例如信号每一跳的增益和默认值属于 `signal-lineage`，不应污染共享层。

## 3. `capabilities/`

Capability 是长期资产。每个能力都必须：

- 有稳定 ID、版本、真实状态、公开输入输出；
- 能够脱离 Recovery Review 单独使用；
- 只返回事实、证据、覆盖和资格，不计算整个任务的 PASS；
- 在缺证据时返回 `UNKNOWN/NOT_PROVEN/UNQUALIFIED`；
- 通过公开 Bundle 与其他能力协作，不读对方私有索引或数据库。

### 能力家族

| 家族 | 模块 | 主要问题 |
|---|---|---|
| 证据治理 | `evidence-kernel`、`authority-governance`、`audit-ledger` | 结论凭什么成立、谁更权威、执行是否可审计 |
| 工作区与协作 | `workspace-snapshot`、`collaboration-snapshot` | 当前到底是哪份代码、多人交付是否到齐 |
| 代码事实 | `code-fact` | 符号、结构、语义、影响面和跨来源证据 |
| 需求与行为 | `contract-reconciliation`、`behavior-recovery` | 规格原子事实、现状行为与意图差异 |
| 修改安全 | `change-safety`、`design-fit-review`、`independent-review` | 有没有误删，修复是否在正确责任层，复核是否独立 |
| 构建近似 | `build-dependency-audit`、`windows-static-precheck` | Target/include/宏/链接/DT 注册及 Windows 预检资格 |
| 外部与长任务 | `external-evidence`、`autonomous-runner`、`report-renderer` | 用户错误、持续执行、专业版与小白版一致报告 |
| 工具供应链 | `third-party-supply-chain` | 固定源码/制品、环境路径清单、构建与执行 Receipt |
| 下阶段测试衔接 | `signal-lineage`、`observability-planner` | 数据每一跳如何变化、DT/业务侧如何留下可串联记录 |
| 工程经验 | `experience-memory` | 明确触发的经验写入、范围召回、纠错、失效与替代链 |

## 4. `adapters/`

Adapter 只解决“如何接到具体环境”，不能拥有工程真相或总体 Verdict。

- `deepseek-harness`：工具暴露、fresh session、权限和结构化输出；
- `company-source-control`：公司 Python 拉取/工作区/提交脚本、Repo Manifest 与 Revision；
- `company-runtime-boundary`：唯一拥有网络、模型 API、密钥、数据外发、运行期下载和制品来源策略；
- 具体 Provider 的命令和版本卡放在对应 Capability 的 Provider 区域。

业务源码供应链与第三方工具供应链严格分开。Capability 只声明访问需求，不能把公司运行限制写进自身规格；所有环境访问决定通过外层边界 Receipt 传入。

## 5. `profiles/`

Profile 是一个可选配方，只能做四件事：

1. 选择 Capability；
2. 决定顺序和覆盖率；
3. 把 Capability 的公开状态映射成 Gate；
4. 渲染 Profile 自己的最终状态和报告视图。

`recovery-review`、`safe-ai-edit`、`ad-hoc-code-investigation` 和 `test-trace-preparation` 互不从属。删除任何一个 Profile 都不应破坏 Capability。

## 6. `composition/`

这里定义一个**可选的薄 Runner**，而不是新的单体控制器。没有 Runner 时，Capability 仍能独立调用。Runner 不得实现结构检查、代码搜索、依赖分析或报告事实，只负责调用、状态、重试、Gate 和恢复。

## 7. `acceptance/`

把真实事故转成可复现的负向题。尤其要证明：

- 明显少括号、文件尾截断和大段误删一定被拦截；
- 无效 Canary 不能得到“预检通过”；
- 用户给出的错误不会被模型的淡定判断覆盖；
- stale Provider、缺失 Target 证据和未到齐协作者代码会正确降级；
- 症状膏药、错误责任层、为了让 DT 绿而改 DT 会被设计审查识别。

## 7A. `dashboard/`

只放由规范和状态证据生成的只读视图。`capability-progress.html` 是单文件静态页面；`tools/render_capability_dashboard.py` 扫描 Toolkit Manifest、Current State 和各 Capability Manifest 后重新生成。百分比由五个固定证据轴计算，页面不得成为新的状态事实源。

## 8. `migration/`

旧文件不复制进这里。这里只记录其 Library 身份、Hash、章节/规则族去向、冲突修正、新增需求和退役范围。这样既保留历史证据，又避免 AI 同时解释新旧两套规范。

## 9. `roadmap/`

把“我们想要什么”变成“要建设什么、如何验收、何时激活”。任何 `DESIGNED` 对象必须经过实现、合成负向测试、公司环境资格和真实项目验证，才可变为 `ACTIVE`。

## 10. `runs/`

规范仓内只保留说明。真正的实例写入经批准的外部 Runtime 根目录，按 run ID 不可变保存：输入、快照、证据、Claim、Receipt、日志、状态和报告。不得覆盖前一次 Receipt。
