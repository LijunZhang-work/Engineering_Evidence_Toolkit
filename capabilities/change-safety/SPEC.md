# Change Safety

状态：`DESIGNED`。

## 职责

本能力有两个公开操作，但只有一个权限模型：

1. `apply_bounded_change` 在绑定当前 Workspace Snapshot 的显式授权范围内应用最小修改，并产生类型为 `MUTATION` 的 Receipt；该回执只记录已经发生的修改，不预先引用未来复验。
2. 复验检查完成后，Runner 产生独立的 `POST_MUTATION_VALIDATION` Receipt，反向绑定 `MUTATION`、当前结果快照和实际验证 Receipt；只有这个后置回执为 `PASS`，修改状态才可晋级为 `VALIDATED`。
3. `inspect_change_integrity` 对修改结果执行多探测器结构安全检查，捕获误删、文件截断、括号/作用域破坏、符号异常减少和意外大范围改动。

Profile Runner 是唯一调度与状态所有者；本能力只执行一次受控修改或一次只读检查。

## apply_bounded_change

必需输入为 Workspace Snapshot、`AUTHORIZATION` Receipt、候选修改和允许路径。授权必须声明仓库、允许/禁止路径、文件数和删除量上限，并绑定当前内容摘要。任何路径越界、授权过期、基线漂移或无法区分用户既有改动，都返回 `CHANGE_REJECTED`，不做部分修改。

成功输出必须包含：

- 授权 Receipt 引用；
- 修改前后内容摘要；
- 完整 changed-path 清单和 diff 内容摘要；
- 每个 hunk 的意图；
- 可用时的恢复引用。

`CHANGE_APPLIED` 只表示修改按授权落盘，不表示结构安全、可构建或业务正确。调用方必须立即执行 `inspect_change_integrity`，并重新冻结 Workspace Snapshot、失效旧证据、刷新受影响 Provider，再重新求值 Claim/Gate。

## inspect_change_integrity

必须组合下列互补探测器：

1. Diff 规模与删除异常；
2. 词法边界（括号、字符串、注释、预处理条件）；
3. 与语言匹配的 Parser/AST；
4. 符号清单前后差分；
5. 文件尾完整性；
6. 每个修改块的固定上下文窗口。

多探测器结论不一致时为 `SUSPICIOUS`。任一高风险截断或未闭合直接为 `UNSAFE`。Parser 缺失、基线缺失、change set 不完整或必需探测器未运行时为 `UNKNOWN/NOT_QUALIFIED`，不得输出 `SAFE_WITHIN_SCOPE`。

## 非职责

- 不证明业务语义、ABI、目标成员关系或正式构建成功。
- 不靠格式化掩盖结构错误。
- 不自行扩大授权，不丢弃、重置或覆盖用户既有改动。
- 不把修改成功、退出码 0 或单个探测器绿色解释为最终 PASS。

## 验收要点

- 删除函数左花括号后的文件尾，至少被三类探测器命中。
- 合法删除完整函数仍要求删除意图证据，不因编译绿色自动放行。
- 越界路径和超预算删除在写入前被拒绝。
- Mutation Receipt 能精确关联授权、基线、结果和 diff。
- 修改后若未重新冻结与复验，严格 RunBundle 不能 ACCEPT。
