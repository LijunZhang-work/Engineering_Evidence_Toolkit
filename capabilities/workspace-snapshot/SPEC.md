# Workspace Snapshot

状态：`DESIGNED`。

## 职责

在分析、修改或验证前固化真实工作输入：多仓根目录、仓库身份、提交、分支、未提交改动、未跟踪文件、补丁、子模块、LFS、生成文件、构建 profile 和关键配置。单个 commit hash 不足以代表工作区。

## 非职责

- 不拉取、切换、清理、暂存或提交代码。
- 不判断代码正确性，不推断未提供仓库的内容。
- 不把当前目录中“没看到”解释为系统中“不存在”。

## 独立入口

`capture_workspace(workspace_roots, repo_manifest?, build_profiles?) -> workspace_snapshot`

可用于一次搜索前的快照，也可供多个 profile 共同引用。

## 输入与输出

每个仓库输出规范路径、remote 身份（脱敏后）、HEAD、分支/游离状态、dirty 摘要、变更文件清单、子模块 revision、LFS 指针/实物状态、稀疏检出、工作树、补丁来源和时间。构建相关输入须记录 target、配置、生成器、工具链、feature flags、宏和生成文件状态。

快照必须声明包含与排除范围，并产生内容摘要；后续 run 若输入漂移，不能沿用旧收据。

## 失败关闭

仓库不可读、Git 元数据缺失、子模块未知或 dirty 内容无法取证时输出 `PARTIAL/NOT_QUALIFIED`。不得只记录 HEAD 后声称“版本已冻结”。

## Side effects

只读探测工作区；只在 run 目录写快照和摘要。禁止自动修复行尾、权限位或文件状态。

## 验收要点

- canary 工作区含未提交补丁时，快照必须捕获而非只给 commit。
- 多仓中缺一个仓库时明确列为缺失，不静默跳过。
- 快照后新增/修改文件可被漂移检查发现。
- 输出不泄露凭据和不必要的敏感 remote 信息。

