# 桌面控制台

这里是同一套桌面控制台的三个独立页面，不把所有信息挤在一个屏幕：

- `index.html` / `workset-planner.html`：选择此刻目标、调用还是建设、保障档位、时间和权限；
- `run-console.html`：只显示本次请求、当前步骤、完成条件、证据引用和人机活动；
- `capability-progress.html`：只显示全部 Capability 的长期成熟度与证据缺口。

导航栏在三个页面间切换。桌面端最低布局宽度为 1040px；本项目不把手机端适配作为当前验收范围。页面不使用 CDN、远程字体、模型 API 或第三方前端运行时。

## 为什么不再显示“52%”

规格、实现、验证、环境资格和激活是五种不同事实，不能用加权平均伪装成一个精确工程进度。成熟度页因此只显示这些可核验状态：

- `已完成`：该轴达到明确完成状态；
- `部分`：有可定位产物，但该轴尚未完成；
- `未开始`：状态明确为未开始；
- `失败/阻断`：该轴存在失败；
- `未知`：缺少足够状态或证据。

一个能力只有五个轴都完成才可显示“已激活”。`PARTIAL` 不再画成半圆，也不被换算成 50%。页面由 Manifest 和状态证据生成，不能靠手改 HTML 变绿。

## 直接浏览与共享运行状态

双击 `index.html` 可以浏览、选择并生成请求草稿；静态模式会显式标成“未验证草稿”，复制时包含完整 JSON。若要让人和 AI 读取同一份 Runtime 协调记录，在 Toolkit 根目录启动仅监听本机的服务：

```powershell
.\.venv\Scripts\python.exe .\tools\workset_control.py serve
```

然后在桌面浏览器打开终端打印的本机地址。服务把请求和运行可见性写到当前用户的外部 Runtime 根，不写 Toolkit 仓，也不写业务仓。可用 `EET_RUNTIME_ROOT` 或 `--runtime-root` 更换位置；程序拒绝 Toolkit 仓及任何其他 Git 工作树内的 Runtime，仓内没有电脑盘符硬编码。

界面提交只创建 `WorksetRequest`，不会假装 AI 已经执行。AI 通过 CLI 接单、更新步骤：

```powershell
.\.venv\Scripts\python.exe .\tools\workset_control.py inbox
.\.venv\Scripts\python.exe .\tools\workset_control.py claim
.\.venv\Scripts\python.exe .\tools\workset_control.py update --step <step-id> --status RUNNING --message "正在执行的真实动作" --expected-revision <当前 revision>
.\.venv\Scripts\python.exe .\tools\workset_control.py checkpoint --step <step-id> --summary "完成了什么" --artifact IMPLEMENTATION_ARTIFACT=repo:<相对路径>#sha256:<摘要>
.\.venv\Scripts\python.exe .\tools\workset_control.py update --step <step-id> --status COMPLETED --message "已形成绑定检查点" --evidence <上一步返回的 checkpoint_ref> --expected-revision <当前 revision>
.\.venv\Scripts\python.exe .\tools\workset_control.py status
```

`COMPLETED` 更新不能直接引用任意文件；它必须引用 `runtime:checkpoints/...` 下的 typed `WorksetStepCheckpoint`。Checkpoint 绑定 request、run、step、operation 和至少一个可打开且摘要相符的实际工件。空串、无关文件、虚构路径、摘要不符、全步骤跳过和并发旧 revision 都不能产生完成状态。运行页只是 Workset 协调投影，不拥有 Profile Runner 的实例状态，也不拥有 Claim、Gate、资格、激活或最终 Verdict 权限。

## 重新生成与验收

```powershell
.\.venv\Scripts\python.exe .\tools\render_toolkit_console.py
.\.venv\Scripts\python.exe .\tools\render_capability_dashboard.py
.\.venv\Scripts\python.exe .\tools\test_workset_control.py
.\.venv\Scripts\python.exe .\tools\test_capability_dashboard.py
.\.venv\Scripts\python.exe .\tools\validate_toolkit.py
```

先更新 Canonical Manifest、Catalog 或证据，再重新渲染。生成成功只证明页面与输入一致，不证明 Capability 已实现、验证、资格化或激活。
