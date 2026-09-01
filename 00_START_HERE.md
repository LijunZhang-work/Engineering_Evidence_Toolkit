# Engineering Evidence Toolkit

中文名：**可组合工程事实与验证能力集**。

这是三份旧文档完成职责拆分后的唯一入口：

- `Code Fact Accelerator v3.1`；
- `Code Fact Accelerator Post-v3.1 v1.1`；
- `Recovery Review v2.5`。

它不是一篇更大的总文档，也不是一个默认强制执行的工作流。它是一组可以单独调用、也可以被 Profile 组合的工程能力。旧文档保留为历史来源证据，不再作为新的运行入口。

> 当前版本交付的是**规范与建设蓝图**。所有 Capability、Profile 和 Adapter 的真实状态以 `CURRENT_STATE.yaml` 为准；在实现和验收完成前，不得声称工具已经可用、检查已经生效或项目没有问题。

## 1. 先选择入口，不要通读整个目录

| 你的目的 | 应读取 | 不应自动加载 |
|---|---|---|
| 平常搜索符号、调用链、影响面 | `capabilities/code-fact/` | Recovery Review 的阶段和 Gate |
| 检查 AI 修改是否误删、截断、少括号 | `capabilities/change-safety/` | 完整遗留审查 |
| 判断文件是否真正编译进目标、include/宏/链接/DT 注册是否成立 | `capabilities/build-dependency-audit/` | clangd 等于真实构建的假设 |
| 只在 Windows 做快速静态预检 | `capabilities/windows-static-precheck/` | WSL 或产品镜像全量编译 |
| 确认多人协作代码是否已到齐 | `capabilities/collaboration-snapshot/` | 把缺失消费端推断为死代码 |
| 追一条信号从规格到 C++、DataBuff、图元、算法和南向 | `capabilities/signal-lineage/` | Recovery Review 全套流程 |
| 设计 DT 侧与业务侧下一阶段观测方案 | `capabilities/observability-planner/` | 擅自给高频模块刷屏日志 |
| 处理用户给出的真实错误或运行日志 | `capabilities/external-evidence/` | 用本地“绿”覆盖外部“红” |
| 让 AI 记住、召回或纠正工程经验 | `capabilities/experience-memory/` | 把旧记忆当当前代码事实 |
| 首次核对 CodeGraph、Memory、clangd 等工具源码/制品路径 | `capabilities/third-party-supply-chain/ENVIRONMENT_ASSET_INVENTORY_TEMPLATE.md` | 擅自下载或因一个可选工具缺失冻结全部工作 |
| 体检本工具集自身结构、看板和Schema依赖 | `python tools/toolkit_doctor.py`、`lifecycle/README.md` | 把doctor成功解释成业务检查通过 |
| 判断DeepSeek Harness当前到底支持哪些能力 | `adapters/HARNESS_CAPABILITY_MATRIX.yaml` | 根据其他Harness能力推断等价支持 |
| 一眼查看各能力建设百分比和证据缺口 | `dashboard/capability-progress.html` | 让 AI 主观填写一个好看的进度数字 |
| 正式审查一批遗留 AI 改动 | `profiles/recovery-review/` | 直接调用 Provider 私有接口 |
| 只做一次安全 AI 修改 | `profiles/safe-ai-edit/` | Recovery 的 S0–S7 全阶段 |
| 建设或升级这套工具 | `roadmap/`、`acceptance/` | 修改业务源码的授权 |

## 2. 四种合法调用方式

### A. 建设或升级工具集

读取 `roadmap/IMPLEMENTATION_SEQUENCE.md`，生成本次建设 Manifest，展示范围、制品、风险和验收题。在用户输入下面这句之前，只能设计、盘点和准备：

> **确认并锁定工具集建设基线，开始自主建设。**

该确认只授权建设工具集、Adapter、测试夹具和文档，不授权修改任何业务仓源码。

### B. 单独调用 Capability

读取目标目录下的 `CAPABILITY.yaml` 与 `SPEC.md`。Capability 必须能独立使用，不需要先进入 Recovery Review，也不需要知道调用它的是哪个 Profile。

### C. 运行可选 Profile

读取目标 `PROFILE.yaml` 与 `RUNBOOK.yaml`。Profile 只能组合 Capability 的公开输入输出，不得复制 Capability 内部规则、读取 Provider 私有数据库或改变证据语义。

Recovery Review 的标志性确认语句是：

> **确认并锁定本次审查，开始自主执行。**

该确认只在对齐仓库、Revision、协作代码到齐状态、权威依据、权限和运行范围，并展示 Manifest Hash 后有效。

### D. 查看、恢复或审计实例

读取 `runs/README.md` 与对应外部运行目录。运行状态、Receipt、索引、缓存和报告不写回本规范目录，也不写入业务仓。

## 3. 三种模式不是三个质量等级

| 模式 | 用途 | 正式结论资格 |
|---|---|---|
| `EXPLORE` | 日常查找、理解和提出候选线索 | 不得支撑“没有问题” |
| `EVIDENCE` | 绑定快照、覆盖、新鲜度和 Receipt 的事实采集 | 可支撑限定范围的 Claim |
| `ENFORCE` | 由 Profile 将能力输出映射为 Gate | 只有 Profile 可以给总体 Verdict |

一个 Capability 可以支持前两种模式；`ENFORCE` 是组合层行为，不代表 Provider 有裁决权。

## 4. 不可绕过的证据规则

1. 没有执行证明，就只能写 `NOT_EXECUTED`，不能写“没问题”。
2. 环境、编译器、头文件、宏、Target、Revision 或索引不匹配时，必须降低资格或返回 `NOT_PROVEN`。
3. Windows 静态预检不能冒充产品镜像内的真实 Linux 构建，也不能冒充 DT 动态执行。
4. 用户提供的明确错误是新的外部证据；在完成同一代码快照的矛盾对账前，它不能被本地成功结果覆盖。
5. 搜到文件、符号或 include 不等于该文件进入了目标；必须单独证明 Target、条件宏、传递依赖、链接和测试注册。
6. 协作者代码未到齐或外部组件不可见时，不得把“当前无消费者”写成“无人使用”或“死代码”。
7. 修改后必须重新取得当前字节上的结构、依赖和 Code Fact 证据；旧索引和旧 Receipt 自动失效。
8. 任一工具只能声明其证据天花板。Provider、模型和报告渲染器都不能自行提高权威等级。
9. “看起来合理”“通常应该”“大概率没事”不是证据状态。
10. 准备合入仓库的代码、注释、名称、测试与消息必须仅凭仓库上下文可理解；`fix1.1`、会话轮次或用户与 AI 的审批暗语不得进入合入候选。
11. 表达通用 behavior 的规则、字段和标识必须写完整的 `BEHAVIOR`；`BEH` 只保留给有仓内权威依据的 BEH 产品、工具、模型或专名。
12. Memory 只保存历史经验与调查线索。召回内容必须在当前快照重新验证；错误经验用更正/替代链失效，不得静默覆盖，也不得支撑当前 PASS。
13. 公司网络、模型 API、密钥、数据外发、运行期下载与制品来源只由 `adapters/company-runtime-boundary/ADAPTER.yaml` 决定；Capability 和其他 Adapter 不得复制或放宽。
14. 自动检查与Hook只能产生Receipt、发现或阻断信号，不能自行提升总体结论；默认不得自动修改业务源码。
15. Harness兼容性必须逐能力登记和验证；`DESIGNED`、`NOT_ASSESSED`、`VERIFIED`与`UNSUPPORTED`不得互相替代。

## 5. 文件类型的权威顺序

发生冲突时，按以下顺序处理，并返回 `CONFLICTED`，不得让 AI 自行挑选喜欢的版本：

1. JSON Schema：对象形状和字段约束；
2. `CAPABILITY.yaml` / `PROFILE.yaml` / `TOOLKIT_MANIFEST.yaml`：公开接口与组合关系；
3. `RULE_CATALOG.yaml`、策略文件：可执行强制规则；
4. `SPEC.md`、Runbook：解释与操作说明；
5. 示例、模板和报告：非规范性展示。

同一条强制规则只能有一个 Canonical Owner；其他位置通过稳定 ID 引用。

## 6. 当前状态与下一步

- 目录架构：已设计；
- 共享契约：已设计；
- Capability/Profile/Adapter：规范已设计，尚未实现；
- Experience Memory：能力、Provider候选与MVP标准已设计，尚未安装或运行；
- 公司运行边界：单一外层规格已设计，尚未在真实环境强制执行；
- 能力拼图看板：自动渲染器已实现；当前20个Capability均为20%，只表示规格完成；9项聚焦回归测试通过；
- 工具集生命周期：只读doctor已实现并通过聚焦测试；自动安装、修复和卸载尚未实现；
- DeepSeek Harness：逐能力兼容矩阵已建立，运行环境兼容性尚未验证；
- 自动检查：安全策略已定义，Harness Hook运行时尚未实现或激活；
- 自动化验收：用例已定义，尚未运行；
- 公司真实项目验证：未运行；
- 旧文档：历史保留，新的执行入口已迁移到本目录。

开始任何实际工作前，先读 `CURRENT_STATE.yaml`。如果状态与文件文字冲突，以更保守的状态为准。
