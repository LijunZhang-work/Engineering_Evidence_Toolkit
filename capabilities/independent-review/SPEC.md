# Independent Review

状态：`DESIGNED`。

## 职责

以新鲜上下文、明确审查镜头和独立证据链，对既有分析或修改做复核。重点主动寻找反例、遗漏、结构破坏、契约不一致和未经证实的“没问题”，并记录与主分析的分歧。

## 非职责

- 不自动接受主分析摘要，也不只改写其措辞。
- 不直接修复发现，不替最终 profile 决定放行。
- 不以模型数量代替证据质量；同源、同提示、同证据的重复意见不算真正独立。

## 独立入口

`run_independent_review(review_scope, workspace_snapshot, evidence_packet, review_lenses?) -> independent_findings`

## 输入与输出

输入包应提供原始 diff/代码与证据位置，而不是只给结论。输出逐条包含发现、严重度、影响面、反例、精确位置、复现/验证办法、审查覆盖和 reviewer receipt。`NO_FINDING` 必须附覆盖范围，不能写成“代码无问题”。

## 失败关闭

审查者看不到原始材料、上下文被污染、范围不明或证据不可访问时为 `NOT_QUALIFIED`。审查意见与主结论冲突时保留 `DISAGREEMENT`，不得静默投票消除。

## Side effects

只写审查发现；默认不得修改代码、测试、主证据包或既有结论。

## 验收要点

- 能在含明显截断 canary 的 diff 中独立提出发现。
- reviewer receipt 能证明输入快照与审查镜头。
- `NO_FINDING` 不会提升成总体 PASS。
- 分歧原样保留并可由后续裁决。

