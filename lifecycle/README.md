# 工具集生命周期

这里管理 **Engineering Evidence Toolkit 自身** 的盘点、计划、应用、体检、修复和卸载，不管理业务仓代码，也不替代 Capability 的业务证据检查。

当前真实状态：

| 操作 | 状态 | 说明 |
|---|---|---|
| `inventory` | `NOT_IMPLEMENTED` | 尚无跨 Harness 的完整安装盘点器 |
| `plan` | `NOT_IMPLEMENTED` | 已定义 Install Plan 契约，尚无生成器 |
| `apply` | `NOT_IMPLEMENTED` | 不得声称工具集可自动安装 |
| `doctor` | `IMPLEMENTED` | 只读检查当前规范包、看板和可选 Schema 引擎 |
| `repair` | `NOT_IMPLEMENTED` | 不得自动覆盖漂移或用户修改文件 |
| `uninstall` | `NOT_IMPLEMENTED` | 尚无 ownership-checked 卸载器 |

运行只读体检：

```powershell
py -3 .\tools\toolkit_doctor.py
py -3 .\tools\toolkit_doctor.py --json
```

```bash
python3 tools/toolkit_doctor.py
python3 tools/toolkit_doctor.py --json
```

`HEALTHY` 或 `LIMITED` 只表示当前工具集规范包的已实现自检通过。它不表示任何 Capability 已实现，也不表示业务代码、Windows 预检、编译或 DT 通过。

后续安装器必须先生成符合 `contracts/install-plan.schema.json` 的只读计划，取得仅限工具集生命周期范围的确认，再写入符合 `contracts/install-state.schema.json` 的 ownership state。修复和卸载只能处理状态中明确登记且摘要满足前置条件的文件；用户修改过或无法证明归属的文件必须保留并报告。
