# 架构决策日志

本日志记录“为什么这样拆”，避免后续建设重新滑回单体文档或大Controller。这里的 `ACCEPTED` 表示规范决策已接受，不表示实现完成。

## D-001：交付形态是工具集，不是单体工作流

- 状态：`ACCEPTED`
- 决策：Code Fact、Windows Precheck、Dependency Audit、Change Safety、Signal Lineage 等均为可独立调用能力；Recovery Review只是可选 Profile。
- 原因：日常查代码、局部预检、依赖核查或观测规划不应被迫运行完整 Review。
- 约束：Profile不能拥有或复制事实算法。

## D-002：静态规范与动态运行实例分离

- 状态：`ACCEPTED`
- 决策：版本化规范保存在能力、契约、Profile和适配器目录；每次运行的状态、证据和报告只进入 `runs/<run_id>/`。
- 原因：示例和真实状态混放会制造假 `ACTIVE`、假 `PASS` 和陈旧证据。

## D-003：规范迁移、实现、验证、资格和激活是五条状态轴

- 状态：`ACCEPTED`
- 决策：不能用一个“已完成”覆盖五种含义。
- 原因：本次最严重风险之一就是把“文档写了/命令跑了”当作“检查有效/代码正确”。

## D-004：Evidence Kernel采用正交字段

- 状态：`ACCEPTED`
- 决策：证据至少分为推导方法、断言来源、Authority、Verification状态；不再用单一等级混合。
- 原因：源码解析、测试断言、注释和AI推断不能只靠一个线性级别比较。

## D-005：Provider只通过Capability Contract接入

- 状态：`ACCEPTED`
- 决策：CodeGraph、Codebase-Memory、clangd、scip-clang等是适配器候选，核心规则不得依赖其名字。
- 原因：保证可替换、Provider-Off/Swap/Removal以及模型升级后的退让。

## D-006：Provider状态按三条生命周期拆分

- 状态：`ACCEPTED`
- 决策：artifact、deployment/index、profile-binding分别管理；状态绑定corpus、build profile、snapshot和有效期。
- 原因：全局 `ACTIVE` 无法证明它对当前仓和当前字节有效。

## D-007：CFA Post保持Campaign身份

- 状态：`ACCEPTED`
- 决策：N0–N7、真实多仓复核、clangd Intake、Joern/Kythe等进入Roadmap，不进入当前能力清单。
- 原因：计划不能冒充实现或验证结果。

## D-008：旧文档保留但退出未来运行入口

- 状态：`ACCEPTED`
- 决策：不删除、不改写、不移动三份历史来源；新工具集激活后只作历史证据。
- 原因：保留迁移审计与原始证据链，同时避免两个真相入口。

## D-009：建设确认不授权业务源码修改

- 状态：`ACCEPTED`
- 决策：精确语句“确认并锁定工具集建设基线，开始自主建设”仅授权在工具集范围内建设。
- 原因：用户需要Agent离席自主建设，但权限不能被扩大解释。
- 后续：能力/Profile通过Release Gate后仍需单独激活。

## D-010：先建设负向Canary，再接受PASS

- 状态：`ACCEPTED`
- 决策：结构截断、假成功预检、陈旧索引、用户错误冲突是首批强制Canary。
- 原因：只有证明检查能可靠失败，才有资格解释“没有发现错误”。

## D-011：Windows Precheck不是产品编译替代品

- 状态：`ACCEPTED`
- 决策：Windows层负责尽早发现结构、目标、include、宏、生成依赖和DT契约风险，并明确环境资格与结论上限。
- 原因：编译器、镜像、系统头、宏和生成步骤不同，不可能保证100%等价。

## D-012：未知消费者是一等事实

- 状态：`ACCEPTED`
- 决策：多人协作、未上库消费者和交接样本缺失进入 Collaboration Snapshot；不得因消费端未出现而推断生产端错误。
- 原因：多开发者并行时全仓当前状态不一定包含完整端到端实现。

## D-013：Signal Lineage与Observability Planner独立

- 状态：`ACCEPTED`
- 决策：Signal Lineage负责静态轨迹；Observability Planner负责DT与业务侧观测方案；两者可被Review或测试准备Profile组合。
- 原因：它们在普通调试、测试设计和交接审查中也有独立价值。

## D-014：业务侧观测复用模块既有机制

- 状态：`ACCEPTED`
- 决策：不得强迫所有模块统一刷日志；应尊重其日志、数据库、采样、CSV导出和毫秒任务约束，用correlation字段串联。
- 原因：观测本身不能制造性能问题或刷屏。

## D-015：长期自主运行采用诊断阶梯，不采用随意冻结

- 状态：`ACCEPTED`
- 决策：工具失败后先定位、重试安全路径、寻找替代证据、合并同根因并继续无写入任务；只有真实人类决策才等待用户。
- 原因：离席模式必须有产出，也不能生成无法阅读的大量冻结项。

## D-016：修复以Design Fit而非最少行数为目标

- 状态：`ACCEPTED`
- 决策：必须说明根因、不变量、责任归属、既有设计和方案比较；同时禁止贴膏药与过度设计。
- 原因：通过一个测试不等于修复符合产品架构。

## D-017：双版本报告共享同一证据图

- 状态：`ACCEPTED`
- 决策：专业版与小白版只改变表达，不重新计算事实或Verdict。
- 原因：防止两个报告产生不一致结论。

## D-018：薄编排器后置且可替换

- 状态：`ACCEPTED`
- 决策：只有独立能力契约稳定后才可建设可选 dispatcher/gate engine；它不保存能力内部语义。
- 原因：避免先造平台再迫使所有能力适配平台。

## D-019：Memory 是独立、非权威、可纠错的能力

- 状态：`ACCEPTED`
- 决策：Memory 使用明确触发的人可读 Canonical Page；召回只生成线索，当前证据可使旧记录 `WRONG / STALE / SUPERSEDED`，更正保留历史链。
- 原因：单纯聊天总结会失忆；单纯检索式记忆又可能在结论被反证后继续误导推理。
- 约束：Memory 不进入 Evidence Authority，不自动摄取全部聊天，不直接支撑 Gate PASS。

## D-020：公司环境访问只有一个最外层策略所有者

- 状态：`ACCEPTED`
- 决策：网络、模型 API、密钥、数据外发、运行期下载和制品来源只由 `company-runtime-boundary` 裁决。Capability 和其他 Adapter 仅声明需求并消费 Receipt。
- 原因：把同一限制散落在 Code Fact、Harness、Memory 和供应链中会产生漂移、重复和互相矛盾。

## D-021：首次运行先对齐工具源码与制品路径

- 状态：`ACCEPTED`
- 决策：用户提供或确认 Markdown 环境清单；AI 检查 CodeGraph、Memory、clangd 等路径、Revision、制品和遗漏。缺失时给出“AI下载、用户下载、本次不下载并接受影响”三策。
- 原因：路径存在不等于工具可用，缺一个可选 Provider 也不应全局冻结。下载是有副作用动作，必须在对齐时锁定授权、路径和影响。

## D-022：能力进度由证据轴计算，不由 AI 主观填写

- 状态：`ACCEPTED`
- 决策：能力拼图使用规格20%、实现35%、验证30%、环境资格10%、激活5%五轴；状态枚举映射为阶段得分。100%绿色只在五轴全部完成时出现，0%红色只在五轴均为零时出现，未知状态单独显示灰色与进度下限。
- 原因：把“文档写完”显示成“能力100%”会重新制造假完成；未知也不能为了图表整齐被算成零或通过。
- 约束：HTML是派生视图，状态源仍是Manifest、Current State和Receipt。

## D-023：能力看板采用静态首屏加原生 JavaScript 增强

- 状态：`ACCEPTED`
- 决策：看板是单个HTML文件，不依赖前端框架、Web服务、CDN、模型API或运行时网络；生成器预先写入完整卡片和首个详情，JavaScript只增强搜索、筛选和点击详情。
- 原因：双击即可看、关闭JavaScript仍有内容，且AI只需运行一个Python命令便能重渲染。
- 约束：HTML不是状态写入入口；源事实摘要变化后校验器必须拒绝过期页面。看板自身测试通过不得升级任何Capability状态。

## 待决事项

以下事项需要在实施或真实环境接入时以证据裁定：

1. 公司 Python 多仓脚本的真实名称、参数、manifest格式和权限边界。
2. Windows可用的真实编译器、compile database来源、头文件/宏镜像程度。
3. CodeGraph及其他Provider当前批准制品、部署方式和增量刷新能力。
4. clangd在真实多仓中的工程前置条件和资格结果。
5. DT框架、业务模块日志/数据库机制和可接受的观测开销。
6. 新规则目录中旧ID别名的最终人工裁定，尤其 `RR-UR-005`。

这些待决事项不得由Agent凭经验补齐；缺证据时必须保持 `UNKNOWN` 或限定结论。
