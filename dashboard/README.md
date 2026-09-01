# 能力拼图进度看板

这是一个零服务、零前端依赖的静态看板。双击 `capability-progress.html` 即可查看；AI 或开发者在工具集根目录运行下面的命令即可重新渲染：

```bash
python tools/render_capability_dashboard.py
python tools/test_capability_dashboard.py
python tools/validate_toolkit.py
```

给 AI 的最短指令可以是：

> 先依据Capability状态与可定位证据更新相应Manifest；运行`python tools/render_capability_dashboard.py`；再运行`python tools/validate_toolkit.py`。如果校验不通过，不得把页面当作当前事实，也不得手工把卡片改绿。

不要直接编辑生成后的百分比。需要改变进度时，应先更新对应 `capabilities/<id>/CAPABILITY.yaml` 的状态维度并附证据；公司环境资格等全局事实只能由其权威状态或 Receipt 提供。

## 进度不是 AI 主观估计

总体进度由五个互不替代的证据轴计算：

| 证据轴 | 权重 | 100% 的含义 |
|---|---:|---|
| 规格 | 20% | 独立 Capability Manifest 与规格已形成 |
| 实现 | 35% | 存在可执行实现，而不是只有文档 |
| 验证 | 30% | 强制正向/负向用例通过且有 Receipt |
| 环境资格 | 10% | 在目标公司环境与真实项目范围完成资格验证 |
| 激活 | 5% | 已按 Release Gate 明确激活 |

例如“规格完成、其余未开始”的能力是 20%，不是 100%。只有五个轴都满足才显示绿色 100%；五个轴都为零才显示红色 0%。1–99% 显示为琥珀色；关键状态缺证据时显示灰色和 `≥x%` 下限，不把未知伪装成精确数字。

阶段枚举到分数的映射在渲染脚本中固定并显示在页面详情中。脚本优先读取每个 `CAPABILITY.yaml` 的 `status_dimensions`；旧 Manifest 缺少某一轴时，只能使用 `CURRENT_STATE.yaml` 中明确的全局否定证据，不能猜测局部完成度。

## 页面能力

- 一眼统计：绿色 100%、进行中、红色 0%、状态未知；
- 搜索与筛选 Capability；
- 点击能力块查看五轴得分、证据来源、当前局限和下一步；
- 页面内嵌本次快照，不依赖服务器、网络、CDN 或 API Key；
- JavaScript 被禁用时仍能显示完整静态首屏；启用后提供搜索、筛选和详情交互；
- 手机和桌面均可打开。

## 诚实边界

这个看板展示的是规范中已有状态证据，不替代实现、测试、公司环境资格或激活 Receipt。重新渲染成功只说明页面生成成功，不说明任何 Capability 已通过。
