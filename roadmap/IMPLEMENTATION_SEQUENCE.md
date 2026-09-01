# 工具集建设顺序

这是一条**建设路线**，不是已经完成的状态说明。它指导 Agent 把规范变成可执行资产，同时保持每个能力可单拆使用。

## 0. 两种确认必须分开

### 建设确认

标志性语句必须逐字为：

> 确认并锁定工具集建设基线，开始自主建设

该确认只表示：冻结本次建设基线，允许在 `Engineering_Evidence_Toolkit/` 内创建和修改治理工具、契约、测试夹具、适配器与文档，并按本路线持续自主建设。

它**不授权**：

- 修改任何业务源码；
- 自动提交、推送、删除或清理业务仓文件；
- 绕过 `company-runtime-boundary` 的环境访问决定；
- 把尚未实现或验证的能力标为 `ACTIVE`；
- 跳过真实证据，以报告措辞替代结果。

### 激活确认

能力或 Profile 完成实现并通过相应 Release Gate 后，仍需单独的激活决定。建设确认不等于运行激活。

## 1. 自主建设规则

建设确认后，Agent 应持续执行以下循环，直到完成、达到真实人类决策点或命中安全边界：

1. 从最早未通过的 Release Gate 读取缺口。
2. 把缺口拆成可独立验证的小任务。
3. 优先完成不需要业务源码写入的契约、验证器、Canary、测试和文档。
4. 每个任务完成后生成 Receipt，并重新读取实际 diff/产物。
5. 失败时先执行诊断阶梯、替代实现和无写入旁路任务。
6. 同根因问题合并，不批量制造 `WAITING_HUMAN`。
7. 只有权限、权威冲突、不可逆动作或会改变产品语义的选择才等待用户。
8. 状态由真实检查结果计算；禁止把 TODO 改成 PASS 来“完成”。

## 2. 建设阶段

### B0 — 冻结建设基线

目标：确保建设对象、来源和权限明确。

产物：

- 三源哈希登记与迁移矩阵；
- 新目录 Manifest；
- 新旧规则别名/冲突登记；
- 建设确认 Receipt（包含确认语句、时间、基线哈希、权限边界）。

停止条件：缺少建设确认时只能完善设计和待办，不进入可执行实现。

### B1 — 稳定契约与词汇

先实现最小、Provider 无关的契约：

- Capability Contract；
- Evidence Bundle、Claim、Receipt；
- Workspace Snapshot；
- Rule/Gate/Status；
- Deviation/Waiver/Taint；
- Benchmark Result 与 Provider Qualification。

要求：每个 schema 都有正例、反例和版本兼容策略。状态轴必须拆分，禁止一个 `PASS` 同时表示任务完成、环境合格、工具有效和结论正确。

### B1A — 工具集生命周期与 Harness 兼容基线

在批量接入 Provider 或自动 Hook 前实现：

- `inventory -> plan -> apply -> doctor -> repair -> uninstall` 生命周期；
- Install Plan 与 ownership state；
- dry-run、摘要前置条件、用户修改保留和可恢复回滚；
- DeepSeek Harness 逐能力支持矩阵；
- Harness事件、阻断、超时与显式信任的现场验证；
- Canonical Capability 到 Harness 投影的版本、摘要与漂移检查。

当前只有只读 `doctor` 已实现。不得因契约已形成而声称安装、修复、卸载或Hook运行时可用。

### B2 — Evidence Kernel 与审计底座

实现：

- Claim–Evidence 校验；
- 证据原始位置和内容哈希；
- 推导方法、断言来源、Authority、Verification 四轴；
- Unknown Budget；
- Evidence conflict 与单向否决；
- Append-only Ledger 和 Chain of Custody。

先用纯文件夹测试夹具验证，不依赖真实业务仓。

### B3 — Change Safety 最小闭环

这是最先要能真正挡错的能力：

- 修改前可恢复快照；
- Patch 先应用到验证副本；
- 完整文件分隔符扫描；
- Parser error/missing node；
- 顶层符号清单前后差异；
- 文件尾完整性与冲突标记；
- Changed-byte binding；
- 故意截断函数的负向 Canary。

Gate 未通过前，不允许任何 Profile 声称“修改已安全”。

### B4 — Workspace、Authority 与协作事实

实现独立能力：

- Workspace Snapshot：多仓、revision、dirty state、生成源、内容身份；
- Authority Governance：权威顺序、冲突、Waiver权限；
- Collaboration Snapshot：个人/多人、未上库依赖、交接样本、未知消费者。

这些能力既可单独用于日常探索，也可由 Review Profile调用。

### B5 — Code Fact核心与Provider适配

先实现 Native Provider，再接第三方：

1. 文件/文本/结构/精确语义等能力契约；
2. Coverage、Freshness、Corpus/Build Profile Binding；
3. 修改后增量刷新 Receipt；
4. Source/Build/Execution/Qualification Receipt；
5. Provider artifact、deployment/index、profile-binding 三生命周期；
6. Provider-Off、Swap 和 Removal 测试。

CodeGraph、Codebase-Memory、scip-clang、clangd 等只能作为适配器候选。任何一个 Provider 未通过现场资格检查时，不影响其他已实现能力被单独使用，但结论上限必须降低。

### B6 — Windows静态预检与依赖审查

实现两个可单拆能力：

- Windows Precheck：结构、可用语法检查、环境资格、编译器/版本/命令、include/macro、退出码和负向 Canary；
- Dependency Audit：Build graph、Include graph、Data/Signal graph 分离，Target membership、owner、resolution、propagation、条件宏、生成依赖与 DT 静态契约。

必须明确：Windows 检查不能冒充产品镜像全量编译。环境不完整时输出 `UNQUALIFIED_ENVIRONMENT` 或受限结论，而不是 PASS。

### B7 — 行为恢复、设计完整性与独立审查

实现：

- Contract Reconciliation；
- Behavior Recovery；
- Design Fit；
- Independent Review；
- External Evidence Reconciliation。

用例必须包含：用户给出明确错误但本地未复现、消费者尚未交付、DT答案被错误修改、为修Bug硬贴膏药等反例。

### B8 — 长时自主执行与报告

实现：

- 可恢复状态机与幂等任务；
- Autonomous Diagnostic Ladder；
- 同根因合并、心跳、Question Deferral；
- 真实 `WAITING_HUMAN` 判定；
- 专业版/小白版共享事实图的 Report Renderer。

验证必须包含进程中断后恢复、资源限制、连续无进展和大量表象错误来自同一根因的场景。

### B8A — Experience Memory 最小闭环

先实现 Provider 无关的显式记忆闭环，再评估候选后端：

- “记住/写入记忆/总结经验”意图识别与普通总结对照；
- 人可读 Markdown Canonical Page；
- 项目/仓库范围隔离；
- 写入后回读 Receipt；
- `WRONG / STALE / SUPERSEDED` 追加式纠错链；
- 召回只作线索、进入 Gate 前必须按当前快照复验；
- Provider 关闭、跨项目查询和反证到达的负向 Canary。

首先执行 `capabilities/experience-memory/MVP_GUIDE.md`。`ai-memory` 只是首选研究候选；不得因名气、已有集成或设计文档直接标记为 ACTIVE。

### B9 — Signal Lineage与Observability Planner

作为独立能力建设，不与 Recovery Review 绑死：

- 静态数据轨迹：类型、单位、增益、上下限、默认、转换、序列化与消费；
- DT侧验证点与预期值；
- 业务侧复用既有日志/数据库/采样机制的低侵入观测计划；
- correlation/trace字段把分散记录串成一条线；
- Markdown先行，后续可选网页视图。

仅生成观测**计划**不授权修改业务源码。实际插桩需要独立审批和变更协议。

### B10 — 组合Profile

在独立能力通过各自 Gate 后再实现：

- Ad-hoc Code Investigation；
- Safe AI Edit；
- Recovery Review；
- Test Trace Preparation。

Profile只做输入绑定、能力选择、顺序/并发、Gate映射、停止策略和报告视图；不得复制能力内部事实算法。

### B11 — 真实项目验证 Campaign

只有前置 Gate 通过后，才执行旧 CFA Post 的 N0–N7：

- 使用公司批准的 Python 工作流创建只读真实任务 Workspace；
- 冻结多仓 revision；
- 建立真实 Case 与 Golden Evidence；
- 先用环境工具源码与制品路径 Markdown 清单核对必需/可选 Provider；缺失时完成“AI下载/用户下载/本次跳过及影响”的对齐；
- 复核现有 Provider；
- Intake/Benchmark clangd；
- Provider-Off/Swap/Removal；
- Joern只在Trigger满足时进入；Kythe保持Watchlist。

该阶段仍不得通过计划文本宣布结果。

### B12 — 独立迁移审计与分能力激活

最终由 fresh、只读 Reviewer 检查：

- 旧三文档的安全不变量是否全部有落点；
- 新规则是否唯一且机器可判定；
- Canary是否证明门禁会失败；
- 状态是否由Receipt计算；
- 任何 Provider/能力/Profile是否被错误标为ACTIVE。

通过后按能力分别激活；不要求整个工具集一次性全开。

## 3. 优先级

推荐优先顺序：

1. B1–B3：先让最明显的大段误删无法漏过。
2. B1A：在引入更多自动化前补齐工具集归属和DeepSeek Harness真实能力边界。
3. B4–B6：建立多仓事实、Code Fact新鲜度、Windows和依赖证据边界。
4. B7–B8：解决语气覆盖证据、错误冻结和离席持续运行。
5. B9：为下阶段真实测试准备数据轨迹和观测方案。
6. B8A：用小型、可纠错的 Memory MVP 防止经验只散落在聊天总结中。
7. B10–B12：最后组合Profile、真实Campaign与激活。

## 4. 不允许的捷径

- 先写一个大Controller再补能力边界。
- 用同一个Markdown当配置、状态、证据和报告。
- 只验证happy path，不写负向Canary。
- 把“命令执行了”写成“检查有效”。
- 把“没找到”写成“不存在”。
- 把“Provider能启动”写成“Provider在当前仓正确”。
- 把“文档已生成”写成“工具已实现”。
- 把“建设确认”解释成允许修改业务源码。
