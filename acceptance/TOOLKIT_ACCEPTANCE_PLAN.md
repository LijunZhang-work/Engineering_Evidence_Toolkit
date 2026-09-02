---
document_status: DESIGNED
document_version: 1.1.0
---

# Toolkit Acceptance Plan

本计划不是“让 AI 看一眼觉得合理”，而是为未来实现准备可重复、带预期结果的反例夹具。每个用例都要证明：能力真的看见了错误、证据来自正确快照与环境、Profile 没有把无效检查或未知项美化成通过。

当前状态为 **PARTIAL_EXECUTABLE**：完整矩阵仍只是设计，尚未整体执行；但 Windows 纵向
MVP 已为 `ACC-STRUCT-002`、`ACC-STRUCT-003`、`ACC-BUILD-001`、缺 include 子集、
`ACC-EXT-001` 以及干净反向对照提供静态夹具和自动测试。该子集通过不代表其余用例、
正式编译、DT、公司环境或完整 Capability 已通过。

此外，`cpp-target-selection/REAL_VALIDATION.yaml` 已在固定 Catch2 commit 的隔离 worktree 上复跑上述五类真实源码场景。它证明当前静态入口能发现两类结构破坏和目标未接线，也如实暴露缺 include 无法被当前静态启发式检出。由于本机没有 MSVC/CMake/Ninja，这仍不是正式编译、测试或资格验证。

## 已执行的纵向子集

运行 `python tools/test_windows_precheck_mvp.py` 会在只读静态夹具上实际完成：

1. 冻结工作区字节与 target manifest；
2. 运行内存 detector self-test，并明确它不能替代端到端 active Canary；
3. 通过 Target Manifest Schema，只检查 source 与可达 quoted header，拒绝工作区逃逸；
4. 检查缺右括号、文件尾截断、raw string、带引号 include、空范围与 source→target；
5. 接收并保留“本地结构绿、用户环境红”的外部错误；
6. 按 quick/balanced/strict 结论上限计算结果；
7. 从同一 fact-set hash 生成专业、小白和机器三视图（含同一 limitations）。

运行 `python -m unittest tools.test_profile_runner_mvp -v` 会只在 OS 临时目录复制件中完成一次
少右括号的授权修复链：首个 Workspace Snapshot、Solo Collaboration Snapshot、before FAIL、
固定 exact edit、content-addressed diff、after PASS 与三报告。该用例只证明隔离 Runner 路径可执行，
不证明生产 Profile Runner、真实项目写权限、MSVC 编译、DT、资格或激活。

这是一个诚实的纵向 MVP，不是完整矩阵的替代品。`ACC-PRECHECK-001` 要求的真实入口
active Canary 仍未实现，所以 Strict 干净样本保持 `INCOMPLETE`。

## 验收方法

每个夹具至少包含：

- `before/` 与 `after/` 源码快照；
- 仓库 Revision、dirty patch、target/build 配置与协作清单；
- 必要时的 Provider 索引、编译命令、用户错误日志或权威接口样本；
- 预期 Claim、Evidence、Gate、结论上限和禁止出现的错误结论；
- 一个反向对照，证明工具不是“无论输入都给相同答案”。

验收 Harness 必须校验公开 Capability Contract，而不是读取 Provider 私有数据库。所有测试要保存原始输出、版本、命令、环境清单和内容 hash。

## 必测矩阵

| ID | 注入问题 | 必须观察到 | 禁止结论 | 主要能力 / Gate |
|---|---|---|---|---|
| ACC-STRUCT-001 | 一个函数起点之后的大段代码被误删，连带多个后续函数 | 删除规模异常、符号消失、构造边界破坏、影响范围 | “diff 很小/没有问题” | change-safety / F1 |
| ACC-STRUCT-002 | 函数缺少右括号 | 不平衡边界及首个无法闭合的位置 | PASS | change-safety / F1 |
| ACC-STRUCT-003 | 文件尾被截断但中部改动看似正常 | EOF 异常、未闭合类/命名空间/条件块、尾部符号丢失 | 只验证编辑行后 PASS | change-safety / F1 |
| ACC-FACT-001 | Code Fact 索引对应旧 Revision | stale index receipt，拒绝用旧索引证明当前源码 | 当前快照全仓无引用 | code-fact / F2 |
| ACC-PRECHECK-001 | Canary 没进入真实检查输入，工具仍返回绿 | 机制无效，整次检查标记 INVALID | “编译无错” | windows-static-precheck / F1-F3 |
| ACC-PRECHECK-002 | Windows 预检与正式环境使用不同编译器、flags、头路径和宏 | 等价性差异与受限结论 | “与正式构建百分之百等价” | windows-static-precheck / F2 |
| ACC-BUILD-001 | `.cpp` 存在但没加入实际 target | target membership 缺失 | “文件在仓库里所以会编译” | build-dependency-audit / F2 |
| ACC-BUILD-002 | 源码只依赖偶然传递 include；目标上下文变化后缺头文件 | 直接/传递链、脆弱边、目标上下文 | 仅文本扫描后 PASS | build-dependency-audit / F2 |
| ACC-DT-001 | DT 文件存在但未注册或未加入测试 target | discovery/registration 或 target 断点 | “DT 文件存在所以会执行” | build-dependency-audit + behavior-recovery / F3 |
| ACC-EXT-001 | 本地预检为绿，用户提供同 Revision 的真实可复现错误 | 证据冲突；外部红覆盖本地绿，定位环境/覆盖差异 | 继续宣称没问题 | external-evidence / F5 |
| ACC-COLLAB-001 | 消费端由协作者开发且代码尚未到齐 | 未到达依赖、责任边界、可验证上限 | 臆造消费端或误判当前作者漏实现 | collaboration-snapshot / F0 |
| ACC-DATABUFF-001 | 生产者与消费者经 DataBuff key/注册表动态绑定，无直接引用 | key、schema、注册、写入、读取链 | “搜不到调用所以没有消费” | signal-lineage / F3-F4 |
| ACC-SIGNAL-001 | 信号增益在中间模块错误变化 | 各阶段值/公式及第一个有证据的分歧点 | 只报最终值错误不定位链路 | signal-lineage / F4 |
| ACC-DESIGN-001 | 在下游加特殊 if 掩盖上游契约错误 | 根因、正确责任层、膏药式修复风险 | 因症状消失就接受补丁 | design-fit-review / F4 |
| ACC-REPOSITORY-READER-001 | 在代码、注释或名称中写入 `fix1.1`、AI 修改轮次或用户审批暗语 | 会话局部上下文泄漏、仓内依据缺失、冷读失败 | “只是注释所以无害” | repository-reader policy / F1 |
| ACC-NAMING-BEHAVIOR-001 | 在 behavior 规则域继续使用 `RR-BEH-*` | 模糊缩写及与真实 BEH 专名的碰撞 | 接受为新的活动规则 ID | naming policy / specification validation |
| ACC-MEMORY-001 | 用户明确要求总结经验并写入；随后新证据推翻旧结论 | 可读Markdown、写后回读Receipt、旧记录失效与追加更正链 | “记住了”但无落盘；旧错误继续生效 | experience-memory |
| ACC-MEMORY-002 | 召回旧经验后询问当前代码是否没问题 | 将Memory限定为线索并要求当前快照复验 | Memory直接支撑PASS | experience-memory + evidence-kernel |
| ACC-MEMORY-003 | 项目A写入后在项目B普通查询 | 项目范围隔离及范围Receipt | 跨项目静默召回 | experience-memory |
| ACC-ENV-001 | 用户清单漏列必需工具，另一个可选工具路径失效 | 找出遗漏/错误，给出AI下载、用户下载、不下载三策及影响；其余工作继续 | 擅自clone、只报缺失、全局冻结 | third-party-supply-chain + outer runtime boundary |
| ACC-BOUNDARY-001 | 在内部Capability重新加入网络或API Key策略 | 规格校验拒绝非Canonical Owner的环境策略键 | 多处策略各自生效 | outer runtime boundary / specification validation |
| ACC-DASHBOARD-001 | 仅把一个能力的总分或外观改成100%，但至少一条证据轴未完成 | 识别伪绿色，拒绝100%分类 | “总分看起来够高所以完成” | capability progress dashboard / specification validation |
| ACC-DASHBOARD-002 | 五轴全0、缺少一轴证据和五轴全100三组输入 | 分别显示红色0%、灰色UNKNOWN、绿色100% | 把UNKNOWN当0%；把部分完成当100% | capability progress dashboard |
| ACC-DASHBOARD-003 | 先渲染页面，再修改Capability或CURRENT_STATE源事实 | 识别source digest不一致并要求重渲染 | 继续把过期页面当当前状态 | capability progress dashboard / specification validation |

## 用例细化

### 1. 结构安全组

`ACC-STRUCT-001` 的基线文件包含至少五个相邻函数。变体从第一个函数的 `{` 后删除到文件中后部，并让补丁表面上只显示“一次替换”。预期不仅报语法风险，还要列出消失的函数、引用方和大段删除统计。

`ACC-STRUCT-002` 同时准备一个字符串与注释中含花括号的对照文件，防止简单字符计数产生误报。预期实现需通过解析器、编译器语法模式或经验证的结构扫描识别真实函数边界。

`ACC-STRUCT-003` 把文件最后一个 `}`、`#endif` 或命名空间结束块截掉。检查范围必须覆盖完整文件和文件尾，不能只看被 AI 声称修改的行。

### 2. Code Fact 与预检有效性组

`ACC-FACT-001` 先为 Revision A 建索引，再将源码修改到 Revision B。查询一个只在 B 出现的符号。若能力未检测 stale，应直接判验收失败；允许回退到当前源码扫描，但必须把 derivation 与覆盖范围写清。

`ACC-PRECHECK-001` 的坏 Canary 故意放在未纳入命令的文件中；好的 Canary 放入真实目标输入并产生确定错误。只有坏 Canary 被识别为无效、好 Canary 被检测后再撤销且恢复绿，才能证明机制工作。

`ACC-PRECHECK-002` 准备 MSVC/clang-cl 与 Linux clang/gcc 的差异矩阵，至少改变一个编译器、一个宏和一个 include 根。预期结论只能是“在已记录 Windows 环境下未发现某类错误”，不得声称正式环境等价。

### 3. 构建、传递依赖与 DT 组

`ACC-BUILD-001` 创建未加入 CMake/公司 Python 构建清单的 `.cpp`，并创建同名已加入 target 的对照文件。能力必须给出 source→target 的正反证据。

`ACC-BUILD-002` 让 `a.cpp` 因 `A.h -> B.h -> Needed.h` 偶然可见某类型，再在另一个目标或 include 顺序下移除该偶然路径。预期输出必须包含目标上下文、传递链和建议的直接依赖声明，不能只说“目前能找到头文件”。

`ACC-DT-001` 分别制造“文件未注册”“注册但未入 target”“入 target 但被 feature flag 排除”三个变体，输出断点必须准确。Windows 上不能运行 DT 时，最高结论为 `STATIC_READY`，不是运行通过。

### 4. 外部证据与协作边界组

`ACC-EXT-001` 提供用户侧原始错误、Revision、编译器、flags 和头路径。若本地为绿，系统必须先解释 Canary、覆盖和环境差异；无法解释则 Gate 为 FAIL 或 INCONCLUSIVE，绝不能用自信语气覆盖用户证据。

`ACC-COLLAB-001` 的对齐信息声明：C++ 生产端由当前开发者交付，图元/HTML 消费端由协作者交付且尚未入库。系统应继续验证生产端契约、DataBuff 写入与现有通用机制，同时把消费端端到端验证标为待交接，不得无休止全局冻结。

### 5. DataBuff、信号与设计组

`ACC-DATABUFF-001` 使用字符串/枚举 key 与注册表动态连接生产者和消费者。验收要求输出“定义→注册→写入→传输→读取→消费”的证据链，并区分直接引用不存在与行为链不存在。

`ACC-SIGNAL-001` 定义输入 10、上游增益 0.1、DataBuff 值 1、下游误用增益 10、最终值 10。报告必须将“下游应用错误增益”标为第一个有证据分歧点，并保留类型、单位、默认值、最小值、最大值。

`ACC-DESIGN-001` 提供两个候选补丁：A 在最终输出处硬编码修正，B 在错误责任层修复契约/转换并补相邻场景。即使 A 让单个用例变绿，Design Fit 仍应拒绝 A，并解释重复策略、隐藏耦合和未来扩展风险。

### 6. 仓库读者与命名组

`ACC-REPOSITORY-READER-001` 在源代码注释、变量名、测试名和运行消息中分别注入 `fix1.1`、`aiFixPhase2`、“按本次和用户确认”等会话局部文本。扫描器只能负责提出候选；验收还必须让不读取聊天记录的 Reviewer 仅依据仓库内容解释其稳定含义。无法解释时必须拒绝合入候选。反向对照使用仓库既有、可定位到 Issue/ADR/协议规范的编号，证明规则不会把所有版本号或缺陷单号误杀。

`ACC-NAMING-BEHAVIOR-001` 向活动规则目录注入 `domain: behavior` 且 ID 为 `RR-BEH-999` 的规则。规格校验器必须拒绝它并要求完整的 `BEHAVIOR` 拼写；另准备一个有仓内权威来源的真实 BEH 专名作为对照，证明保留词仍可用于它原本的产品/工具含义。

### 7. Memory 与环境对齐组

`ACC-MEMORY-001` 先用明确记忆意图写入一条带条件的经验，再提供足以推翻它的新证据。预期 Canonical Markdown 可回读，旧记录保持可审计但退出普通召回，新记录通过 `corrects/supersedes` 指向旧记录。直接覆写、删除旧记录或只给自然语言承诺均失败。

`ACC-MEMORY-002` 证明召回不是证据升级器：无当前 Workspace Snapshot 和新鲜验证时，只能给调查线索和待验证清单。`ACC-MEMORY-003` 验证项目/仓库范围，防止别的项目经验无提示混入。

`ACC-ENV-001` 使用 Markdown 环境清单，注入一个漏列的必需 Provider、一个错误路径和一个正常 Native Provider。AI 必须附路径证据和影响，按用户选择执行三策之一；只有选 AI 下载且外层边界允许时才可下载。可选工具缺失不能阻止 Native 路径继续。

`ACC-BOUNDARY-001` 对规格副本注入 `default_network`、`network_default`、`runtime_package_install` 或 `no_runtime_download_by_default`。除 `company-runtime-boundary` Canonical 文件外出现这些环境决策键，静态校验必须失败。

### 8. 能力拼图进度组

`ACC-DASHBOARD-001` 直接篡改生成HTML中的汇总分或CSS分类，让未完成能力呈现绿色100%。校验器必须逐轴重算并拒绝伪绿色，不能只相信页面上的总分与颜色类名。

`ACC-DASHBOARD-002` 使用三组最小夹具：五轴均为0、至少一轴无状态/无证据、五轴均为100。预期只能分别为红色0%、灰色UNKNOWN（已知分显示为下限）和绿色100%。1%到99%的已知状态统一属于进行中，不得因为“接近完成”变绿。

`ACC-DASHBOARD-003` 先生成页面，再修改任一参与计算的Capability描述、状态或`CURRENT_STATE.yaml`。校验器必须根据源事实摘要报告页面过期；重新渲染后摘要一致才允许恢复通过。渲染命令返回0只证明输出成功，不证明任何Capability通过验收。

## Recovery Review 专项行为

- 未收到精确确认语句前，`ACC-RR-001` 必须阻止无人值守启动；确认后锁定内容与 hash 可复验。
- `ACC-RR-002` 同时放入一个需协作者提供样本的阻塞项和三个可独立检查项。预期后三项完成，阻塞问题只出现一次聚合记录。
- `ACC-RR-003` 故意让专业版与小白版模板走不同措辞。Harness 比较事实集 hash、Finding ID、数量、严重度、证据与局限，任何差异都失败。
- `ACC-RR-004` 注入一个试图直接读取 CodeGraph 数据库路径的 Profile。Runner 必须在执行前拒绝该越界配置。

## 通过标准

实现只有在全部 Mandatory Case 的预期结果、禁止结果、证据字段和反向对照均通过后，才能从 `DESIGNED` 候选升级为已验证状态。仅运行命令成功、仅生成报告或仅通过正常样本均不算验收完成。
