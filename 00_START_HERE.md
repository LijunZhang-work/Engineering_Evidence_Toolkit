# Engineering Evidence Toolkit

中文名：**可组合工程事实与验证能力集**。

这是三份旧文档完成职责拆分后的唯一入口：

- `Code Fact Accelerator v3.1`；
- `Code Fact Accelerator Post-v3.1 v1.1`；
- `Recovery Review v2.5`。

它不是一篇更大的总文档，也不是一个默认强制执行的工作流。它是一组可以单独调用、也可以被 Profile 组合的工程能力。旧文档保留为历史来源证据，不再作为新的运行入口。

> 当前版本交付的是**规范与明确受限的可执行子集**。所有 Capability、Profile 和 Adapter 的真实状态以 `CURRENT_STATE.yaml` 为准；某个子集实现或测试通过，不得被扩写成整个工具已可用、完整检查已生效或项目没有问题。

## 0. Windows 首次使用

在 Toolkit 仓库根目录、获批的依赖获取环境中依次执行三步：

```powershell
py -3 -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r .\requirements-validation.txt
.\.venv\Scripts\python.exe .\tools\toolkit_doctor.py
```

然后可以用仓内 clean fixture 做一次可复制的 PowerShell 烟测；输出只写入系统临时目录：

```powershell
$eetSmokeOutput = Join-Path $env:TEMP "eet-clean-smoke"
.\.venv\Scripts\python.exe .\tools\windows_precheck_mvp.py `
  --workspace .\acceptance\fixtures\windows-mvp\clean `
  --target-manifest .\acceptance\fixtures\windows-mvp\clean\target.yaml `
  --policy balanced `
  --output $eetSmokeOutput
```

预期进程退出码为 0，机器输出的 `final_verdict` 仍为 `NO_VERDICT`；这只证明受限烟测可执行，不是产品编译、链接、DT 或公司环境通过。

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
| 体检本工具集自身结构、看板和Schema依赖 | `.\.venv\Scripts\python.exe tools\toolkit_doctor.py`、`lifecycle/README.md` | 把doctor成功解释成业务检查通过 |
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

## 3. 用户可以选择快或严，但不能选择过度声称

默认界面只需要三个按钮：

| 用户选项 | 机器模式 | 适合什么情况 | 结论上限 |
|---|---|---|---|
| 快速探索 | `EXPLORE` | 尽快找到符号、候选根因和下一步 | 只给线索，`NO_VERDICT` |
| 平衡取证 | `EVIDENCE` | 按风险决定是否交叉验证 | 给证据与风险报告，不签发 `ACCEPT` |
| 严格门禁 | `ENFORCE` | 正式审查、交付或高风险修改 | 完整 RunBundle 通过后才可能给 Verdict |

高级 `Custom` 必须绑定基础预设及其内容哈希，并由机器重新推导结论上限。完整 RunBundle 可内嵌它；Windows MVP 使用 `--policy-file <custom-policy.yaml>`，不会把 Custom 压回单一强度数字。

开发者若要验证“启动→快照→修改→复验→三报告”的 Runner 代码路径，运行
`.\.venv\Scripts\python.exe -m unittest tools.test_profile_runner_mvp -v`。它只修改 OS 临时目录的
固定验收夹具复制件；不能拿来修改真实项目，也不产生 `ACCEPT`、资格或激活结论。

这三个按钮不是只保存一个“强度百分比”的模糊滑块。每次运行都会把选择展开并冻结为
`RunPolicy`：覆盖要求、独立来源数、鲜度、负向 Canary、Provider 选择、调用/时间预算、
阻断方式和最终结论权限分别记录。高级用户可以单独调整这些轴；任何降级都必须同步降低
结论上限。

例如，`zg → CodeGraph → rg` 只能是某类“广泛发现”查询的 Provider 偏好，不是每次查询
都强制执行的链。快速模式可以在第一个合格结果后停止；严格模式要求的是与 Claim 风险匹配
的独立证据，而不是机械地把所有工具都跑一遍。

无论选择哪一档，五条规则不可关闭：不得编造、不得隐藏冲突、用户错误是一等证据、不得
越权修改、不得把较少检查包装成更高结论。

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
16. `PASS`、`PROVEN`和最终 Verdict 必须来自完整 RunBundle 的结构与语义校验；单个文件合法、退出码 0 或报告写成绿色都不够。
17. Authority Registry 只是 Authority 目录，不是自认证信任根；正式 RunBundle 必须由外层运行边界提供仓外固定摘要或独立签名，缺失时不得产生 Verdict。

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
- Capability/Profile/Adapter：大多数仍只有规范；`windows-static-precheck` 有受限纵向 MVP，其余状态逐项见看板；
- Experience Memory：能力、Provider候选与MVP标准已设计，尚未安装或运行；
- 公司运行边界：单一外层规格已设计，尚未在真实环境强制执行；
- 能力拼图看板：自动渲染器已实现；Windows MVP 使对应能力进入部分实现/验证，其余能力仍在规格阶段；完整快照防协同伪绿测试已加入；
- 工具集生命周期：只读doctor已实现并通过聚焦测试；自动安装、修复和卸载尚未实现；
- DeepSeek Harness：项目Skill发现、自定义GLM选择、Windows工作区和只读命令调用已有PARTIAL运行观察；完全只读预设会阻断临时目录，Capability验收仍为NOT_RUN；
- 自动检查：安全策略已定义，Harness Hook运行时尚未实现或激活；
- 自动化验收：完整矩阵尚未运行；RunBundle 红队、状态晋级和 Windows 纵向 MVP 子集已经执行；
- 真实开源项目：固定 commit 的 Catch2 已执行五个隔离场景静态子集并保留修复前后哈希记录；缺 include 仍是静态盲区，外部错误仅为验收夹具；
- 正式 Windows 构建/测试与公司真实项目资格：未运行（本机缺 MSVC/CMake/Ninja）；
- 旧文档：历史保留，新的执行入口已迁移到本目录。

开始任何实际工作前，先读 `CURRENT_STATE.yaml`。如果状态与文件文字冲突，以更保守的状态为准。
