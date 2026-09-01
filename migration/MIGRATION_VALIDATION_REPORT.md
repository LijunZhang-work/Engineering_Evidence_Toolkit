# 三源迁移验证报告

报告日期：2026-08-29  
报告范围：规范迁移完整性，不包含工具实现验证或真实项目有效性验证。

## 结论

三份历史来源已经完成**章节分组级映射**，其来源哈希也已在本地重新计算并与登记值一致。当前可以确认的是：旧规范的去向已经被明确记录，规则漂移与新增要求没有被静默吞掉。

当前**不能**确认工具集已经实现、能运行、能约束 Agent、能正确检查 C/C++、能替代产品镜像编译，或已经适合激活。新工具集状态仍为：

- 规范迁移：`SPECIFICATION_SUPERSEDED_FOR_NEW_WORK`
- 实现：`NOT_IMPLEMENTED`
- 验证：`NOT_VALIDATED`
- 激活：`INACTIVE`

## 1. 来源完整性复核

| 来源 | SHA-256 复算结果 | 结构覆盖 |
|---|---|---|
| Code Fact Accelerator v3.1 | `9a414470967ce8bfb2184823838aa3e8bcb5f276a47d1a6b3555ab9cb82617f7` | 0–31、附录 A–F 已映射 |
| Code Fact Accelerator Post v1.1 | `7b59446163c7cd0aa23c27ae8f3f9406b5e476f07a2cdc2e1a09c1ecd970fe7a` | 0–21、附录 A–C 已映射 |
| Recovery Review v2.5 | `6a6c82d265dcb9003130813fb859fba83b85b347b65a253652e7c639d5ab8344` | ENTRYPOINT、ALIGNMENT、LAUNCH LOCK、0–43（含 15A–15G）、附录 A–C 已映射 |

说明：这里的“已映射”表示每个一级章节均有去向，不表示逐句语义等价已经由独立审查者证明。

## 2. 已完成的迁移检查

### 2.1 来源身份

- 三份文件均固定了文件名、Library ID、文件 ID 和 SHA-256。
- CFA 主文档被识别为基础规范。
- CFA Post 被明确识别为**后续 Campaign/执行计划**，不是当前能力。
- Recovery Review 被识别为混合了能力、Profile、适配器、运行状态、Gate 和报告的历史组合协议。

### 2.2 结构覆盖

`REQUIREMENT_TRACEABILITY_MATRIX.yaml` 对三份来源的全部一级章节做了分组级映射，并列出了 Recovery Review 的全部已知规则族。映射目标区分为：

- 独立能力（Capability）
- 稳定交换契约（Contract）
- 可选组合（Profile）
- 可替换工具接入（Adapter）
- 尚待建设/验证的 Campaign（Roadmap）
- 历史研究或示例（Archive）

这样可以避免把所有内容重新塞进另一个单体“工作流文档”。

### 2.3 规则漂移

已经单独登记以下问题，未做静默猜测：

- `RR-CG-004` / `RR-F3-004`：相同增量同步语义的编号漂移。
- `RR-UR-005` / `RR-UR-201..207`：旧编号与新区间并存，且定义不连续。
- `RR-A-002`、`RR-T-004`：孤立引用或示例编号。
- `RR-R4-003`：旧版示例残留。
- `RR-EV-001`：Evidence-first 章节的规则编号覆盖不完整。
- `RR-BD-001`：Build/Target/Include/DT 章节的规则编号覆盖不完整。
- `RR-AL`、`RR-D`：概念存在但规则族缺失或不完整。
- S6、S7：阶段存在但没有规则 ID。

处理原则是：保留旧 ID 供追溯；新工具集使用唯一的新 ID；只有语义完全等价时才建立 alias。新补规则必须标记为 `NEW_AFTER_FREEZE`。

### 2.4 旧后续讨论的吸收

冻结后新增要求已经独立登记，包括：能力可单拆、文档不能充当唯一约束、建设确认和运行激活分离、多人协作快照、未知消费端边界、Signal Lineage、双层观测规划、Windows-only 证据上限、传递依赖、编辑后多探测结构门禁、用户错误证据优先、预检资格与 Canary、增量事实同步、长时自主诊断、Design-Fit 和双版本报告共享事实等。

这些要求没有伪装成三份历史文档的原文。

## 3. 不得丢失的安全不变量

迁移重构可以淘汰旧的单体表达，但以下不变量必须继续存在：

1. 任何结论都必须可回到原始证据，工具输出本身不是自动真相。
2. 用户提供的明确错误不能被本地“没有发现问题”或语气覆盖。
3. 编辑前必须可恢复；编辑后必须检查完整文件，而非只看局部 diff。
4. 分隔符、Parser、顶层符号、文件尾、冲突标记和内容绑定必须多探测并带负向 Canary。
5. Windows 预检必须先证明环境资格和命令能真实失败；不与产品镜像编译等价。
6. Target membership、include ownership/resolution/propagation、宏、生成依赖和 DT 静态关系必须有独立证据链。
7. Code Fact 证据必须绑定当前快照、内容、Coverage 和 Freshness；修改后必须增量同步。
8. Provider 必须有来源、构建/包、执行和资格 Receipt；示例 `ACTIVE` 不是现实状态。
9. 独立 Reviewer 必须 fresh、只读并使用结构化结果。
10. 自主执行必须先走诊断阶梯，不能把普通问题批量冻结为等待用户。
11. 修复必须解释根因、不变量、责任归属和方案选择，不能为变绿贴膏药。
12. 专业版与小白版必须从同一事实集渲染。

## 4. 仍未完成的验证

以下项目仍然是明确缺口：

| 缺口 | 当前状态 | 完成证据 |
|---|---|---|
| 逐条规则语义等价审计 | 未完成 | 独立 Reviewer 对规则目录和旧原文的逐项签名 |
| 规范 Schema/Validator | 已实现，待本包最终复跑 | `tools/validate_toolkit.py` 的解析、Schema、路径、ID、状态与越权检查；它不验证业务源码 |
| Capability/Profile Runtime | 未开始 | 对应公开契约的可执行实现、失败样例和 Receipt |
| 截断 C++ 文件拦截 | 未验证 | 完整文件截断 Canary 必须稳定失败 |
| 预检假成功拦截 | 未验证 | 缺 include/错编译器/吞退出码 Canary 必须失败或降级 |
| 陈旧索引拦截 | 未验证 | 修改后旧索引查询必须被 Freshness Gate 拒绝 |
| 用户错误冲突处理 | 未验证 | 用户原始错误存在时总体 PASS 必须被单向否决 |
| Provider 供应链与部署 | 未开始 | Source/Build/Execution/Qualification Receipts |
| 真实多仓适配 | 未开始 | 公司工作流 Manifest、Revision Freeze 和只读验证 |
| clangd/Joern/Kythe | 仅计划/候选 | 对应 Campaign Gate 的真实结果，不得引用计划作为证据 |
| Recovery Review Profile | 未实现 | 能力组合、Gate 计算、状态恢复和双报告的一致性测试 |
| 长时间自主执行 | 未验证 | Liveness、Question Deferral、同根因合并和恢复测试 |
| Signal Lineage与观测方案 | 未实现 | 静态轨迹、业务侧观测计划与跨模块关联样例 |

## 5. 激活判定

本次迁移报告的判定是：

```yaml
specification_migration: SPECIFICATION_SUPERSEDED_FOR_NEW_WORK
source_hashes: VERIFIED
chapter_group_coverage: COMPLETE
rule_family_gaps: EXPLICITLY_REGISTERED
independent_semantic_audit: NOT_COMPLETED
implementation: NOT_IMPLEMENTED
validation: NOT_VALIDATED
activation: BLOCKED
```

本目录已经取代三份旧文档成为**新工作的规范入口**；这一规范替代不等于可执行激活。只有 `roadmap/RELEASE_GATES.yaml` 中规定的门禁获得真实 Receipt 后，才可以把某个独立能力或 Profile 从 `INACTIVE` 改为 `ACTIVE`。不得通过编辑本报告来改变实现或验证状态。

## 6. 对旧文档的处理

- 不删除、不改写、不移动三份历史来源。
- 它们只可用于历史阅读和迁移核对，从现在起不再作为新工作的运行入口。
- 工具集是否可以执行由实现、验证和激活状态单独控制，不能倒退回旧文档入口。
- 若发现遗漏，先追加迁移修正记录和新版本哈希，不回写伪造旧来源。
