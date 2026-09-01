# Signal Lineage

状态：`DESIGNED`。

## 职责

把一个信号/字段从外部输入，经 C++ 业务模块、结构体/缓存、data buffer、图元/算法到南向输出的每个阶段串成一条可核验数据线。每一站记录名字、类型、单位、增益、默认值、最小/最大值、编码、容器、生命周期、变换公式和期望/观察值。

## 非职责

- 不设计日志注入；观测落点交给 observability-planner。
- 不把静态代码推导冒充真实运行值。
- 不在协作者消费端未到齐时判生产端无用或接口错误。
- 不凭相同字段名自动连接两站。

## 独立入口

`trace_signal_lineage(signal_contract, workspace_snapshot, evidence?) -> signal_lineage`

## 数据线模型

每个 stage 至少包含：`stage_id`、模块/owner、来源位置、表示类型、单位/量纲、scale/gain/offset、范围、缺省/无效值、字节序/枚举、输入、输出、变换、条件、expected、observed、evidence、confidence。边必须说明复制、转换、聚合、限幅、延迟或丢弃条件。

可同时容纳两类值：DT 中构造/断言的值，以及业务真实环境采集的值；二者来源与天花板分开。后续可把同一机器数据渲染成 Markdown 或网页，不能以展示层重建事实。

## 失败关闭

单位/增益/边界/编码/版本任一未知时保留缺口。消费端代码 `PENDING_EXTERNAL` 时只给到交接边界，不把线路伪造闭合。动态分派、生成字段或运行配置未证实时标 `PARTIAL/UNKNOWN`。

## Side effects

只读并写线路产物；不得插桩、改业务代码、运行 DT 或写数据库。

## 验收要点

- 对给定输入可逐站展示期望变换，并能回到实现/契约证据。
- gain 或单位不一致能定位到具体边。
- 未到齐协作者代码产生明确交接点，而非死代码结论。
- DT 值和业务观测值不会混在同一“observed”字段中。

