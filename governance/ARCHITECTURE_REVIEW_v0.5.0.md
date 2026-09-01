# Engineering Evidence Toolkit 架构 Review v0.5.0

Review 日期：2026-09-01  
Review 对象：`Engineering_Evidence_Toolkit` 规范目录  
结论：**架构方向成立；本次边界收敛通过静态检查，但整体仍是 DESIGNED，不能进入真实代码结论或 Provider ACTIVE。**

## 1. 本次已经解决的结构问题

| ID | 原问题 | 本次处理 | 证据 |
|---|---|---|---|
| AR-001 | 公司环境限制散落在 Harness、Code Fact 和第三方供应链 | 新建唯一 `company-runtime-boundary`；内部只声明需求或引用 Receipt；校验器拒绝旧策略键回流 | `adapters/company-runtime-boundary/ADAPTER.yaml`、`tools/validate_toolkit.py` |
| AR-002 | “总结经验”只有 Markdown 杂记，没有可替换、可纠错的长期能力 | 新建独立 `experience-memory`，规定显式触发、Markdown Canonical Page、范围隔离、回读 Receipt、失效与替代链 | `capabilities/experience-memory/` |
| AR-003 | Memory 容易把旧结论继续当真 | 明确 Memory 只产出线索；当前 Workspace/构建/用户新证据可推翻旧记忆；无复验不得支撑 Gate | `experience-memory/CAPABILITY.yaml`、`SPEC.md` |
| AR-004 | CodeGraph 等工具路径、源码和制品是否存在靠猜 | 增加 Markdown 环境清单；缺失时必须对齐 AI 下载、用户下载或本次跳过，并说明影响 | `third-party-supply-chain/ENVIRONMENT_ASSET_INVENTORY_TEMPLATE.md` |
| AR-005 | 工具缺失可能导致随意全局冻结 | 可选 Provider 缺失只降低相关范围；Native 和独立任务继续；同根因阻塞去重 | 环境清单、Recovery Runbook S0A |
| AR-006 | 包版本与 Manifest/State 版本漂移 | Manifest 与 Current State 统一为 `0.5.0` | `TOOLKIT_MANIFEST.yaml`、`CURRENT_STATE.yaml` |

## 2. 当前分层判断

| 层 | 评价 | 关键边界 |
|---|---|---|
| Governance / Contracts | 基本清晰 | 规则与对象形状优先；冲突失败关闭 |
| Capability | 方向正确 | 可单拆；只产出事实/线索/证据，不给总体 PASS |
| Provider | 方向正确 | 可替换；成功退出不等于准确；索引绑定快照 |
| Adapter | 已进一步澄清 | 只接 Harness、源码控制或外部系统，不拥有事实 |
| Outer Runtime Boundary | 本次补齐 | 唯一环境策略所有者；允许/拒绝/未配置均有 Receipt |
| Profile / Runner | 基本清晰 | 只组合与求 Gate；失败后继续可独立工作 |
| Runtime Storage | 基本清晰 | 规范、业务源码、运行证据、Memory Canonical Page 物理分离 |

整体没有退化成不可单拆的大工作流。Memory 可以在普通任务中独立调用，也可以被 Recovery Review 条件调用；缺少 Recovery Profile 不影响它使用。

## 3. 仍未解决、不能假装完成的问题

### High — AR-R01：没有可执行 Memory Runtime

当前只有能力规格、候选表和 MVP 判定。`ai-memory` 是首选研究候选，不是已安装或已验证后端。写入、回读、范围隔离和纠错链均未真实执行。

下一动作：在公司环境先跑 `experience-memory/MVP_GUIDE.md` 六题；只需反馈失败编号与一句现象。

### High — AR-R02：Adapter 没有统一 JSON Schema

Toolkit Manifest 能发现 Adapter，Validator 也检查 ID，但 Adapter 字段形状尚无共享 Schema。不同 Adapter 仍可能出现字段漂移。

下一动作：v0.6 建立最小 Adapter Contract，覆盖公开操作、边界引用、副作用、Receipt 和失败语义；不要把公司策略值复制到 Schema。

### High — AR-R03：Capability Schema 仍特殊照顾 Code Fact

现有 Schema 只强制 Code Fact 提供完整的状态维度、模式、边界和 Provider Policy；其他旧 Capability 的严格程度较低。Memory 本次主动写全关键维度，但整个能力家族尚未统一迁移。

下一动作：分批升级所有 Capability Manifest，并为每次升级加正反例，避免一次机械重写造成大面积误删。

### Medium — AR-R04：完整 Draft 2020-12 Schema 校验未运行

当前环境缺少 `jsonschema`，内置结构检查通过，但完整 Schema 引擎没有执行。正确状态是 `PASS_WITH_LIMITATION`，不是完整 PASS。

下一动作：由外层运行边界提供批准的依赖取得方式后重跑；不允许校验器自行下载。

### High — AR-R05：真实环境资产尚未对齐

CodeGraph、Memory Provider、clangd 等实际源码路径、固定 Revision、制品路径和可用性还没有用户清单与现场 Receipt。模板只是入口，不是环境事实。

下一动作：用户填写或确认环境清单；AI 只读检查后逐项锁定三种策略之一，再进入无人值守阶段。

## 4. 历史文字例外

`migration/` 中仍可检索到旧文件名和旧需求中的“内网”字样。这些是冻结的来源身份和迁移证据，不是活动策略。活动环境策略值只存在于 `company-runtime-boundary/ADAPTER.yaml`；导航、验收与 Review 中出现的相关文字仅说明所有权或检查反例，不构成第二份策略。

## 5. 本次静态验证证据

- 原目录执行 `python tools/validate_toolkit.py`：`errors=0`，结果 `PASS_WITH_LIMITATION`；限制是当前环境没有 `jsonschema` 引擎。
- 在隔离副本向 Code Fact 注入 `provider_policy.default_network`：Validator 以 `DISPERSED_ENVIRONMENT_POLICY` 拒绝。
- 在隔离副本把首选 Memory Provider 标为 `ACTIVE`：Validator 以 `MEMORY_FALSE_ACTIVATION` 拒绝。
- 全部 Markdown 相对链接检查：缺失链接 `0`。

这些是规范静态测试，不是 Memory MVP、Provider 可用性或业务代码检查。

## 6. 静态 Review Verdict

- 架构职责：`PASS_WITH_OPEN_RISKS`
- Memory 规格接入：`PASS_DESIGN_ONLY`
- 环境策略单一所有者：`PASS_DESIGN_ONLY`
- 静态内置校验：`PASS_WITH_LIMITATION`
- Memory Provider 实现与 MVP：`NOT_EXECUTED`
- 公司运行边界真实强制：`NOT_EXECUTED`
- CodeGraph/clangd/Memory 环境资产资格：`NOT_EXECUTED`

这些状态不能合并成“项目已经可用”。本 Review 只证明 v0.5.0 的目录设计与静态规则在当前检查范围内一致。
