# 自动检查与 Hook 安全策略

状态：**SPECIFIED / RUNTIME_NOT_IMPLEMENTED**。

本策略回答：哪些检查可以在 AI 修改代码后自动触发，自动化能做什么，失败时如何表达。它不假设 DeepSeek Harness、Codex 或其他 Harness 具有相同的 Hook 事件和阻断能力。

## 1. 基本原则

1. Hook 是执行约束，不是事实来源。它只能产生 Receipt、发现或阻断信号，不能把 Claim、Capability 或 Profile 自行提升为 PASS。
2. 默认自动化必须只读业务源码。允许写入经批准的 Runtime 目录，不得自动格式化、补括号、改测试期望值、恢复文件或提交代码。
3. Harness 不支持某事件、Hook 未受信任、命令未执行、超时或覆盖无效时，状态必须是 `NOT_EXECUTED / UNSUPPORTED / INEFFECTIVE`，不能表现为“没有发现问题”。
4. 自动化定义、命令、脚本版本或摘要变化后，既有信任和资格自动失效，必须重新审查。
5. 快检查负责尽早挡住明显事故；完整验证仍由独立 Capability 或 Profile 完成。Hook 成功不能替代 Changed-byte Binding、依赖审查、真实编译或 DT。

## 2. 自动化等级

| 等级 | 允许行为 | 默认策略 |
|---|---|---|
| `OBSERVE` | 读取文件、diff、状态；写 Runtime Receipt | 可在支持且已受信任的 Harness 自动运行 |
| `BLOCK` | 在高风险证据出现时阻止后续“完成/提交”动作 | 必须有稳定 Rule ID、超时和失败语义 |
| `SUGGEST` | 生成候选修复或下一步诊断，不落业务源码 | 可自动生成，应用前另行授权 |
| `MUTATE` | 修改业务源码、测试、构建文件或外部资源 | Hook 默认禁止；必须进入独立修改协议 |

## 3. 修改后的最小自动检查

一旦 Harness 能提供可靠的“文件已写入”事件，至少应调度：

- 重新读取实际文件和实际 diff，而不是信任编辑工具的请求参数；
- `change-safety` 的快速结构探测：删除规模、分隔符、文件尾、冲突标记、顶层符号差异；
- 使旧的 Code Fact、Parser、编译预检和依赖 Receipt 失效；
- 在需要时安排修改后增量刷新与受限增量检查；
- 记录 Hook 身份、脚本摘要、输入快照、覆盖、退出码、超时和有效性。

只有 `change-safety` 的正式实现和负向 Canary 通过后，Hook 才能宣称自己真正执行了该能力。此前只能标记为设计中的调度点。

## 4. 独立 Review 自动化

写代码的会话不能签发最终 Review 结论。自动调度独立 Review 时必须证明：

- Reviewer 使用新的上下文/角色实例，并记录 `review_context_id`；
- Reviewer 获得原始代码、完整 diff、权威依据和证据位置，而不是只读作者摘要；
- Reviewer 默认只读，不能边审边修后再审自己的结果；
- `NO_FINDING` 附带实际覆盖范围，且不能升级为总体 PASS；
- 分歧保留为 `DISAGREEMENT`，不通过投票或语气消除。

## 5. Harness 适配与显式信任

不同 Harness 必须分别声明支持的事件、同步/异步能力、阻断语义、超时和信任机制，登记在 `adapters/HARNESS_CAPABILITY_MATRIX.yaml`。未经真实环境验证的项目保持 `NOT_ASSESSED` 或 `DESIGNED`。

不得把 Claude Code 的 Hook 配置复制后声称 DeepSeek Harness 或 Codex 具有同等能力。外层运行边界仍是网络、模型 API、密钥、下载和数据外发的唯一策略所有者。

## 6. 失败和降级

- 快检查失败：保留原始错误，阻止“修改安全”结论；继续执行不依赖该检查的只读诊断。
- Hook 平台不支持：切换为 Runner 显式调用，并记录 `UNSUPPORTED_HOOK_SURFACE`。
- 检查超时：记录覆盖和超时点，不把未处理范围算作通过。
- 自动化产生大量同根因错误：归并根因，不制造大量冻结项。
- Hook 自身异常：不得吞掉异常；由 `doctor` 或 Harness 适配验证暴露。

## 7. 禁止事项

- 仅因命令退出码为 0 就宣称检查有效；
- Hook 自动修改业务代码后继续使用修改前的证据；
- 为了让报告变绿而关闭失败 Hook；
- 在 Capability 内散落公司网络或 API Key 限制；
- 把未经审查的第三方 Hook、Skill 或脚本直接设为全局自动执行。
