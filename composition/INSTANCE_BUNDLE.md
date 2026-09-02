---
document_status: DESIGNED
document_version: 0.1.0-draft
---

# Profile Instance Bundle

每次 Profile 执行都必须写入一个独立实例目录。静态规范永远不与运行时证据混放；同一实例可以中断后恢复，但不能被另一轮任务覆盖。

## 建议结构

```text
runs/<instance_id>/
├── run-bundle.yaml
├── run-policy.yaml
├── instance.yaml
├── alignment/
│   ├── alignment-preview.yaml
│   ├── alignment-lock.yaml
│   └── confirmation.txt
├── snapshots/
├── capability-results/
├── evidence/
├── claims/
├── gates/
├── waivers/
├── diagnostics/
├── checkpoints/
├── ledger.jsonl
└── reports/
    ├── professional.md
    └── plain-language.md
```

`run-bundle.yaml` 是机器裁决入口，必须包含冻结的 Run Policy、Workspace Snapshot、
可选 Collaboration Snapshot、Instance、Typed Receipts、Evidence、Claims、Waivers 和
Provider Adoption Decisions。分目录文件可以作为便于追加和浏览的存储，但最终 Verdict
必须从同一 Bundle 重新装配并执行：

```powershell
.\.venv\Scripts\python.exe tools\validate_run_bundle.py <run-bundle.yaml>
```

CLI 会把 `run-bundle.yaml` 所在目录自动加入本次运行的受限制品根，因此放在同一实例目录下的
`reports/`、`evidence/` 等相对路径可以直接解析。其他外置根必须显式、可重复传入
`--artifact-root <approved-directory>`；相对路径不会搜索工作区之外的任意目录，绝对路径也必须
落在 Toolkit 根、Bundle 目录或显式批准根内。

`instance.yaml` 至少记录 Run Policy ID/版本/结论权限、Profile ID/版本/hash、能力契约集合、
仓库快照引用、开始时间、当前状态和最后检查点。`alignment-lock.yaml` 使用规范化序列化后
计算 SHA-256；确认语句本身与确认时间也进入锁定材料。

## 不变量

- Evidence 与 Claim 都是不可变对象；新证据用新对象补充，不覆盖旧对象。
- `ledger.jsonl` 只追加，不回写历史记录。
- 报告是事实集的视图，不是新的事实源。
- Resume 前必须验证 Profile、快照、对齐锁及已完成证据 hash；不匹配时保留原实例并创建补充快照，禁止静默“接着算”。
- 一个问题等待人工时，其他没有依赖它的 READY 项仍继续执行。
- 实例完成后必须保留所有局限与未决项，不能只保留最终摘要。
- EXPLORE 只能得到 `NO_VERDICT`；EVIDENCE 不能得到 `ACCEPT`；只有 ENFORCE 可进入最终 Verdict 重算。
- Gate 必须引用其 Claim 与 Evidence；Waiver 必须引用独立授权 Receipt，且永远不把原事实改写为 PASS。
