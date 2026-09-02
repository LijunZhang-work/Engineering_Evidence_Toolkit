# 规范自检工具

这里的工具只检查 **Engineering Evidence Toolkit 自身的结构和诚实状态**，不检查业务源码，也不等于任何 Capability 已经实现。

Windows PowerShell：

```powershell
.\.venv\Scripts\python.exe .\tools\validate_toolkit.py
```

Linux/macOS：

```bash
python3 tools/validate_toolkit.py
```

依赖：Python 3.10+、PyYAML、`jsonschema`。使用批准的隔离环境安装固定范围依赖：

```powershell
py -3 -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r requirements-validation.txt
.\.venv\Scripts\python.exe .\tools\toolkit_doctor.py
```

依赖取得方式由最外层运行边界决定；脚本不会自行下载依赖。缺少 `jsonschema` 时 Validator
和 Doctor 都失败，不再产生 `PASS_WITH_LIMITATION`，因为没有完整 Schema 引擎就不能声称
机器契约已经验证。

当前检查：

- 根入口、Manifest、状态文件和核心目录是否存在；
- 所有 JSON/JSON Schema 是否可解析；
- 所有 YAML 是否可解析；
- 所有核心 Schema 自身是否合法，根 Manifest、全部 Capability/Profile、三档 Run Policy、
  Lifecycle 与 Harness Matrix 是否符合 Draft 2020-12 Schema；
- 正向严格 RunBundle 是否通过结构、引用、Receipt 有效性、证据鲜度/覆盖/上限和 Verdict 重算；
- Manifest 中声明的 Capability/Profile/Adapter 路径是否真实存在；
- Capability/Profile ID 是否与目录和清单一致，Profile/Runbook 引用的 Capability ID
  是否真实登记在根 Manifest；
- Profile 是否声明禁止读取 Capability 私有状态和直接访问 Provider；
- 规格、实现、验证、资格、启用五个状态维度是否被诚实分开；
- 每次实现、验证、资格或激活状态晋级是否附带可定位证据；
- `RULE_CATALOG.yaml` 中 Rule ID 是否重复；
- 是否把旧的三份大文档复制进新规范目录；
- 是否把真实运行产物误写进规范目录的 `runs/`；
- 能力拼图是否覆盖全部已登记 Capability、五轴权重是否为100%、是否存在伪绿色、伪红色或隐藏的 UNKNOWN；
- 能力状态源文件变化后，现有 HTML 是否已过期并需要重新渲染；
- 关闭 JavaScript 时是否仍有完整静态首屏，页面是否依赖外部 CDN 或网络资源。

检查通过只表示“规范包内部一致”，不表示 Windows 预检、Code Fact、Recovery Review、编译或 DT 已经运行。

## 只读 Doctor

需要一次性查看当前规范包健康状态时运行：

```powershell
.\.venv\Scripts\python.exe tools\toolkit_doctor.py
.\.venv\Scripts\python.exe tools\toolkit_doctor.py --json
```

Doctor 会检查 PyYAML、强制的 `jsonschema`、能力看板、Lifecycle/Harness、RunBundle 红队测试和整体规范校验器。`UNHEALTHY` 表示至少一项强制检查失败。Doctor 不修改文件，也不运行任何业务 Capability。

它还运行生命周期、Harness 矩阵和 RunBundle 的负向检查，证明能力漏登记、无证据
`VERIFIED`、Adapter/矩阵漂移、空运行 ACCEPT、PASS 无证据、假有效 Receipt、隐藏用户错误
以及超越 Policy 结论上限都会被拒绝。

## RunBundle 语义校验

正式调用必须从受保护的运行配置或 CI 变量取得 Registry 摘要，并显式传入 Registry 路径：

```powershell
.\.venv\Scripts\python.exe tools\validate_run_bundle.py <run-bundle.yaml> `
  --authority-registry <trusted-authority-registry.yaml> `
  --authority-registry-content-id <externally-pinned-sha256>
```

不得在同一次调用中从 Bundle 或 Registry 文件现算这个“期望摘要”，否则攻击者可同时重铸 Registry、pin 列表和 Bundle。仓内常量只用于 `ACCEPTANCE_FIXTURE` 的确定性负测，不是生产信任锚。

Doctor 自身聚焦测试：

```powershell
.\.venv\Scripts\python.exe tools\test_toolkit_doctor.py
```

## 隔离 Profile Runner MVP

`tools/profile_runner_mvp.py` 已打通 `BOOTSTRAPPING → Workspace Snapshot → Solo Collaboration
Snapshot → Windows 静态检查 → exact edit → diff → 后置复验 → 三报告`。修改分支不是生产编辑器：
它只认仓内固定摘要的验收授权与计划，并强制 workspace/output 都位于操作系统临时目录中的复制件。
它不授予真实仓库修改权，不激活 Profile，也永远不能把静态结果升级为 `ACCEPT`。

聚焦验收：

```powershell
.\.venv\Scripts\python.exe -m unittest tools.test_profile_runner_mvp -v
```

## Windows 纵向 MVP

这一入口是 `windows-static-precheck` 的已实现子集，不是完整产品构建器：

`--policy` 提供 `quick`、`balanced`、`strict` 三个便捷预设；高级 `Custom` 使用 `--policy-file`，并在读取工作区前经过 RunPolicy Schema、基础策略内容哈希和结论上限派生校验。

```powershell
.\.venv\Scripts\python.exe tools\windows_precheck_mvp.py `
  --workspace <cpp-workspace> `
  --target-manifest <target.yaml> `
  --policy balanced `
  --output <external-run-directory>
```

可选 `--user-error <log.txt>` 必须同时声明 `--external-error-source UNVERIFIED_EXTERNAL`；它只表示未经认证的
外部输入，不能自行冒充 `USER_PROVIDED`。自动化反例只能使用 `ACCEPTANCE_FIXTURE`。两者都会保留为未解决证据；
真实用户来源需要由外层受信入口另行签发来源 Receipt。本脚本只检查已声明的结构、带引号 include 和 target 元数据；
手工/有界文件集、CMake File API 或 build export 在解析器落地前都不会得到 F2 PASS，当前只有仓内固定自动夹具
可验证 F2 探测器本身。即使结果干净也不能解释为正式产品编译、链接或
DT 通过。Target Manifest Schema、范围/路径边界、raw string、用户错误与三视图一致性测试：

```powershell
.\.venv\Scripts\python.exe tools\test_windows_precheck_mvp.py
```

## 能力拼图看板

在工具集根目录运行：

```powershell
.\.venv\Scripts\python.exe tools\render_capability_dashboard.py
.\.venv\Scripts\python.exe tools\test_capability_dashboard.py
.\.venv\Scripts\python.exe tools\validate_toolkit.py
```

第一条读取 Manifest 与状态证据并重新生成 `dashboard/capability-progress.html`；第二条检查绿/红/UNKNOWN语义、静态首屏、自包含性和快照新鲜度；第三条执行工具集整体一致性检查。页面可直接双击打开，不需要 Web 服务、Node、CDN 或模型 API。渲染成功只证明页面生成成功，不证明任何 Capability 已实现、验证、资格化或激活。
