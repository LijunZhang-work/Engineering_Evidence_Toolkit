---
document_status: DESIGNED
document_version: 0.1.0-draft
---

# runs：运行实例占位目录

此目录只说明运行布局，不保存本机实例。工作集请求和控制台可见状态由 `tools/workset_control.py`
写入仓外 Runtime 根；真正的 Evidence、Receipt、Claim、Gate 和报告也必须写入获批的外部运行目录。

约束：

- 每次运行使用唯一 `instance_id`；不得复用目录伪装成新运行。
- 每次工作集运行使用唯一 `request_id` 和 `run_id`；工作集只冻结目标范围，不能替代实例证据。
- 历史实例不可被静态文档升级改写。
- 原始日志、证据包、门禁结果、诊断过程、检查点和双视图报告必须能按引用互相追溯。
- 无人值守期间持续运行 READY 项；只有符合 Profile Runner Contract 的真实人类依赖才进入 `WAITING_HUMAN`。
- 禁止在此目录提交密钥、访问令牌或未脱敏的敏感数据。

默认 Runtime 路径按当前操作系统和用户目录解析，也可由 `EET_RUNTIME_ROOT` 或
`--runtime-root` 提供；仓库不得保存电脑专属绝对路径。`WorksetRunState` 只负责让人和 AI
共享“现在做到哪一步”，没有最终 Verdict 权限，且 `COMPLETED` 步骤必须引用真实检查点或证据。
