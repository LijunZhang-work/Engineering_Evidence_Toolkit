# 存储与事实源边界

## 1. 目标

把“规范、实现、来源代码、派生索引、运行证据、最终报告”分开，避免示例被当成真实状态、索引被当成源码、报告反过来改写证据。

## 2. 存储域

| 域 | 内容 | 可否作为事实源 | 可变性 |
|---|---|---|---|
| `governance/` | 全局规则 | 规则事实源 | 版本化、发布后不可变 |
| `contracts/` | Schema 与词汇 | 数据契约事实源 | 版本化 |
| `capabilities/` | 能力规范 | 能力行为事实源 | 版本化 |
| `profiles/` | 组合、Gate、报告要求 | 特定任务裁决规则源 | 版本化 |
| `adapters/` | 外部环境接入与唯一运行边界 | 环境接入事实源 | 可替换、版本化 |
| `implementation/` | Runner/CLI/脚本实现 | 执行实现，不覆盖规范 | 可构建 |
| `runs/<run_id>/` | 本次快照、Receipt、Evidence、状态、报告 | 本次运行事实 | 追加式、实例不可变 |
| 外部仓库/工作区 | 产品源码与构建定义 | 当前实现事实源 | 由 Snapshot 固定 |
| 派生索引/缓存 | 代码图、clangd 索引、数据库 | 发现/取证辅助 | 可重建，不是唯一事实源 |

## 3. 推荐实例布局

```text
runs/<run_id>/
├── instance-state.json
├── snapshots/
├── inputs/
├── receipts/
├── evidence/
├── mutations/
├── reports/
└── logs/
```

`inputs/` 保存用户外部证据和授权输入的不可修改副本；解释或摘要放在 `evidence/`，不能覆盖原件。

## 4. 源码边界

- Toolkit 不把产品代码复制进自身规范目录。
- Workspace Snapshot 记录仓库路径、remote、commit、branch、submodule/LFS、patchset、未跟踪文件和哈希摘要。
- 仅有 commit 不足以描述未提交修改、submodule、LFS 或协作者交付；这些必须独立记录。
- 多仓任务必须列出所有预期仓库与代码到齐状态。缺失但“预期尚未交付”的模块不能被误判为本仓缺陷；接口正确性则保持未证明。

## 5. 派生数据边界

CodeGraph、clangd、SCIP、语法树、搜索数据库和缓存均为派生数据：

- 必须关联生成它们的 Workspace Snapshot；
- 记录覆盖文件、排除规则、失败文件、构建画像和生成工具版本；
- 过期或覆盖未知时不得用于 ENFORCE；
- 删除派生数据不应损坏源码或规范；
- Provider 输出需经 Contract 转为 Receipt/Evidence，消费者不得直接依赖私有数据库结构。

## 6. 内容与来源寻址

Artifact 的存储路径不是永久身份。每个重要 Artifact 同时记录：

- `content_id`：规范化内容哈希；
- `provenance_id`：来源链哈希；
- `location`：当前可读取位置，可变化；
- `media_type`、`size_bytes` 与采集时间。

移动文件可改变 location，但不应改变 content_id。重新采集同一内容会产生新的或复用已有 provenance_id，取决于来源链是否相同。

## 7. 写入与保留

- 规范目录的修改走版本审查，不允许运行时自动改写。
- Run 数据默认追加；更正以新版本/新 Artifact 表示，并通过 `supersedes` 关联旧对象。
- Receipt、外部失败、waiver、最终 Verdict 和支撑它们的 Evidence 不得被静默删除。
- 临时日志和缓存可按保留策略清理，但其摘要和影响结论所需的 Artifact 必须保留。
- 报告是派生视图；报告与 Evidence 冲突时，以原始 Evidence 和规则计算结果为准。

## 8. Memory 存储边界

- Memory 的 Canonical Page 存在批准的独立 Memory Runtime 根目录，不进入业务源码仓，也不写回本规范目录。
- Canonical Page 使用可读 Markdown，包含项目范围、来源、适用条件、验证状态与替代关系。
- Provider 的全文、向量、图或逻辑索引是派生数据；可删除重建，不能成为唯一记忆副本。
- Memory 更正采用追加与 `supersedes` 关系；旧内容仍可审计，但 `WRONG/STALE/SUPERSEDED` 默认不参与正常召回。
- 当前 Workspace Snapshot 的新证据可以使旧 Memory 失效；Memory 不能反向覆盖当前证据。
