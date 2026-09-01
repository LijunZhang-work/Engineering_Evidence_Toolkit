---
document_status: DESIGNED
document_version: 1.0.0
---

# Profile Instance Bundle

每次 Profile 执行都必须写入一个独立实例目录。静态规范永远不与运行时证据混放；同一实例可以中断后恢复，但不能被另一轮任务覆盖。

## 建议结构

```text
runs/<instance_id>/
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
├── diagnostics/
├── checkpoints/
├── ledger.jsonl
└── reports/
    ├── professional.md
    └── plain-language.md
```

`instance.yaml` 至少记录 Profile ID/版本/hash、能力契约集合、仓库快照引用、开始时间、当前状态和最后检查点。`alignment-lock.yaml` 使用规范化序列化后计算 SHA-256；确认语句本身与确认时间也进入锁定材料。

## 不变量

- Evidence 与 Claim 都是不可变对象；新证据用新对象补充，不覆盖旧对象。
- `ledger.jsonl` 只追加，不回写历史记录。
- 报告是事实集的视图，不是新的事实源。
- Resume 前必须验证 Profile、快照、对齐锁及已完成证据 hash；不匹配时保留原实例并创建补充快照，禁止静默“接着算”。
- 一个问题等待人工时，其他没有依赖它的 READY 项仍继续执行。
- 实例完成后必须保留所有局限与未决项，不能只保留最终摘要。
