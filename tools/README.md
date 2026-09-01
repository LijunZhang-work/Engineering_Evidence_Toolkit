# 规范自检工具

这里的工具只检查 **Engineering Evidence Toolkit 自身的结构和诚实状态**，不检查业务源码，也不等于任何 Capability 已经实现。

Windows PowerShell：

```powershell
py -3 .\tools\validate_toolkit.py
```

Linux/macOS：

```bash
python3 tools/validate_toolkit.py
```

依赖：Python 3.10+、PyYAML。建议同时安装 `jsonschema`，以启用三类 Manifest 的
Draft 2020-12 完整校验。依赖取得方式由最外层运行边界决定；脚本不会自行下载依赖。

如果缺少 `jsonschema`，脚本会明确输出 `SCHEMA_ENGINE_UNAVAILABLE`，继续执行内建的
字段、路径、ID、状态、越权和跨引用检查，并以 `PASS_WITH_LIMITATION` 标记结果。此结果
不能表述为“JSON Schema 已完整验证”；补齐依赖后必须重跑，才可能得到完整 `PASS`。

当前检查：

- 根入口、Manifest、状态文件和核心目录是否存在；
- 所有 JSON/JSON Schema 是否可解析；
- 所有 YAML 是否可解析；
- 在 `jsonschema` 可用时，根 Manifest、全部 Capability Manifest 和全部 Profile Manifest
  是否符合各自 Draft 2020-12 Schema；
- Manifest 中声明的 Capability/Profile/Adapter 路径是否真实存在；
- Capability/Profile ID 是否与目录和清单一致，Profile/Runbook 引用的 Capability ID
  是否真实登记在根 Manifest；
- Profile 是否声明禁止读取 Capability 私有状态和直接访问 Provider；
- 规格、实现、验证、启用四个状态维度是否被诚实分开；
- 是否有人把 `DESIGNED` 未验收模块虚假提升为 `ACTIVE`；
- `RULE_CATALOG.yaml` 中 Rule ID 是否重复；
- 是否把旧的三份大文档复制进新规范目录；
- 是否把真实运行产物误写进规范目录的 `runs/`；
- 能力拼图是否覆盖全部已登记 Capability、五轴权重是否为100%、是否存在伪绿色、伪红色或隐藏的 UNKNOWN；
- 能力状态源文件变化后，现有 HTML 是否已过期并需要重新渲染；
- 关闭 JavaScript 时是否仍有完整静态首屏，页面是否依赖外部 CDN 或网络资源。

检查通过只表示“规范包内部一致”，不表示 Windows 预检、Code Fact、Recovery Review、编译或 DT 已经运行。

## 能力拼图看板

在工具集根目录运行：

```bash
python tools/render_capability_dashboard.py
python tools/test_capability_dashboard.py
python tools/validate_toolkit.py
```

第一条读取 Manifest 与状态证据并重新生成 `dashboard/capability-progress.html`；第二条检查绿/红/UNKNOWN语义、静态首屏、自包含性和快照新鲜度；第三条执行工具集整体一致性检查。页面可直接双击打开，不需要 Web 服务、Node、CDN 或模型 API。渲染成功只证明页面生成成功，不证明任何 Capability 已实现、验证、资格化或激活。
