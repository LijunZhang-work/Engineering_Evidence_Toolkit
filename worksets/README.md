# 目标工作集

`WORKSET_CATALOG.yaml` 把用户此刻的目标解析成一个**最小能力闭包**。它解决的是“这次先做什么”，不替代 Capability、Profile、Run Policy、Receipt 或 Verdict。

每次请求必须分别冻结四件事：

- 目标工作集：只纳入完成当前目标所需的能力，其余能力明确排除；
- 操作：`USE_AVAILABLE` 只调用当前可用子集，`BUILD_MISSING` 只建设选中的 Toolkit 能力；
- 保障档位：`QUICK / BALANCED / STRICT` 决定取证深度和结论上限；
- 时间与权限：时间预算不等于保障强度，建设权限也不等于业务源码修改权。

`BUILD_MISSING` 永远只能使用 `TOOLKIT_ONLY`，并保持 `NO_VERDICT`。界面或 CLI 生成的 `WorksetRequest` 是绑定 Catalog 和 Capability 状态摘要的本地计划意图，但普通 JSON 摘要不是人类签名。`REQUEST_SCOPED_BUSINESS_EDIT` 也只表示申请；未冻结仓库、路径、基线并取得 typed MutationAuthorization 前不能修改业务源码。

AI 必须另行接单并把可见活动写入外部 `WorksetRunState`。该对象只是 Workset 协调投影，不与 Profile Runner 争夺权威实例状态。状态文字不能代替证据；步骤标为 `COMPLETED` 时，引用必须能在 Toolkit 或 Runtime 中打开并通过 SHA-256 核对。全步骤跳过只能得到未完整执行，不能得到完成。

默认 Runtime 根按当前操作系统解析，也可通过 `EET_RUNTIME_ROOT` 或 `--runtime-root` 显式指定。Runtime 必须位于所有 Git 工作树之外，因此换电脑时不需要修改仓内绝对路径，也不会把个人运行状态提交到任何项目。
