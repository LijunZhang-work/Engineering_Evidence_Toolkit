# Engineering Experience Memory

状态：**DESIGNED / NOT_IMPLEMENTED / NOT_RUN / INACTIVE**。

## 1. 它解决什么

当用户说“记住这条经验”“把这次教训写入记忆”或“总结一下这次误删代码的经验”时，AI 先把零散对话整理成一条人能读、能纠错、能追来源的工程经验，再交给可替换的 Memory Provider 保存。以后遇到相似任务，它可以召回这条经验作为调查线索。

它不把聊天记录整段塞进数据库，也不让旧结论冒充当前事实。Memory 的定位是：**帮助记得去哪里查、过去踩过什么坑、哪些条件必须重新验证**。

## 2. 四个公开操作

| 操作 | 作用 | 是否写入 |
|---|---|---|
| `CURATE` | 把明确要求记住的经验整理成 Canonical Markdown | 是 |
| `RECALL` | 按项目、仓库、主题和适用条件召回候选经验 | 否 |
| `CORRECT` | 用新证据指出旧经验哪里错、为什么错 | 追加更正 |
| `SUPERSEDE` | 新规则取代旧规则，同时保留历史链 | 追加新版本 |

`CURATE / CORRECT / SUPERSEDE` 必须回读刚写入的内容并生成 Receipt。只收到“总结一下这段材料”时默认只返回总结；只有“记住/写入记忆/保存为经验”，或明确的“总结一下……经验”语义，才构成 Memory 写入意图。无法判断时先生成待确认草稿，不得静默落库。

## 3. Canonical Memory Page

持久记录使用 Markdown，至少包含：

- 标题与稳定 Memory ID；
- 项目、仓库、模块和任务范围；
- 当时遇到的问题与可观察症状；
- 原始证据或 Receipt 引用；
- 归纳出的经验、适用条件和不适用条件；
- 推荐动作与禁止的错误捷径；
- 当时如何验证、哪些仍未证明；
- 生命周期：`ACTIVE / STALE / WRONG / SUPERSEDED`；
- 更正、替代关系和时间。

Provider 的向量、图、全文索引或数据库都是派生缓存。即使 Provider 更换或索引丢失，Markdown 仍应能重建记忆。

## 4. 证据边界

召回的 Memory 只能生成 `CLUE / HYPOTHESIS / CHECKLIST_CANDIDATE`。例如旧记忆写着“这个模块曾因传递 include 出错”，它可以要求重新检查 include 链，但不能证明当前版本仍有同一问题，也不能证明当前版本没有问题。

任何准备进入 Gate、Review Verdict 或代码修改依据的主张，都必须回到当前 Workspace Snapshot，用 Code Fact、构建定义、用户材料、测试或运行证据重新验证。当前证据推翻旧 Memory 时，应先降低旧记录资格，再追加更正；模型不得一边看到反证，一边继续沿旧结论推理。

## 5. 范围与多人协作

每条记忆必须绑定至少一个项目范围；可进一步绑定仓库、模块、分支族、产品版本或团队边界。跨项目召回默认不发生。协作者未交付的代码、未知消费端或临时接口样本必须保留条件，不能被压缩成全局规则。

## 6. Provider 与外层边界

Memory Provider 可替换，候选状态见 [`PROVIDER_CANDIDATES.yaml`](PROVIDER_CANDIDATES.yaml)。Capability 不保存公司模型端点、API Key、网络路由或制品下载规则；这些只由 `adapters/company-runtime-boundary/ADAPTER.yaml` 决定。

Provider 返回成功只证明这次调用完成。写入是否真实存在必须以 write-readback Receipt 证明；召回为空也不能证明“没有相关经验”，除非范围、索引覆盖和 Provider 状态都已证明。

## 7. 明确禁止

- 自动保存全部聊天、源码、日志或用户附件；
- 把模型归纳写成“源码事实”；
- 用 Memory 覆盖用户新提供的错误；
- 静默覆盖、删除或隐藏错误经验；
- 跨项目泄漏或无范围召回；
- Provider 失败后返回空列表并声称成功；
- 在能力内部配置公司端点或密钥。
