# Windows Static Precheck

状态：`SCAFFOLDED / PARTIAL MVP`。`tools/windows_precheck_mvp.py` 已实现下面列出的纵向切片；
完整编译语义、正式环境等价性、生成构建展开和公司资格仍未实现。

## 当前可执行 MVP

当前脚本真实执行并保存以下事实：工作区字节摘要、内存 detector self-test、正式 Target
Manifest Schema、目标范围类型与来源资格、由 target source 与可达 quoted header 构成的分析范围、C/C++ 分隔符与
预处理条件近似、raw string、文件尾信号、带引号 include 解析、source→target 成员关系、外部错误字节
保留，以及共享同一 fact-set hash 的专业/小白/机器三视图。对应可执行反例覆盖缺右括号、
文件尾截断、缺 include、未进 target、空 target、范围外 vendor、工作区逃逸和“本地绿但存在外部错误”。

内存 detector self-test 只证明局部扫描函数能区分负样本与控制样本，不证明文件发现、
target routing、读取、Provider 调用和报告链均有效。因此 `active_negative_canary` 仍诚实为
`NOT_IMPLEMENTED`，不能满足 Strict 的资格门。Target 模板见 `contracts/target.example.yaml`。

Target Manifest 必须区分 `FULL_TARGET` 与 `BOUNDED_FILE_SET`。后者适合快速检查少量文件，
即使结构干净也不能让 F2 目标/依赖 Gate 变成 `PASS`。生产 `FULL_TARGET` 最终必须由解析后的
CMake File API/构建系统导出制品证明；当前 MVP 尚未实现这两种解析器，因此即使引用文件存在且
内容摘要匹配也保持 `UNQUALIFIED / F2 INCONCLUSIVE`。当前只有仓内自动化夹具的
`FIXTURE_DECLARATION` 可资格化 F2。手工填写完整列表仍是 `UNQUALIFIED`，避免“自己声明自己覆盖完整”。

当前预处理检查会枚举有界近似分支，但没有绑定真实宏配置，也不求解跨条件组的逻辑关系。
只在部分近似变体出现的结构问题必须标为 `POSSIBLE`，并令 F1 为 `INCONCLUSIVE`；无条件源码中的
确定结构破坏仍为 `FAIL`。

MVP 即使对干净样本也不会声称正式产品构建或 DT 通过：快速/平衡策略返回 `NO_VERDICT`；
严格策略在没有产品编译器和独立证据时最多 `INCOMPLETE`，发现明确问题时可 `REJECT`。

## 职责

在代码位于 Windows、不能或不希望运行 WSL 产品镜像与 DT 的条件下，快速但严谨地发现语法、结构、符号、部分类型、include/target 接线和明显契约问题。核心不是“跑过一个工具”，而是证明预检环境确实有资格检查声明的范围。

## 非职责与证据天花板

- 不承诺与 Linux 产品编译器、标准库、ABI、链接器、生成器或镜像宏百分之百等价。
- 不运行 DT/TT，因此不能证明 fixture、注册、运行行为、时序、算法结果或端到端信号正确。
- 不用 Windows 编译器零报错反驳外部错误；当前 MVP 只接受 `UNVERIFIED_EXTERNAL` 或明确的
  `ACCEPTANCE_FIXTURE`，不能自行认证 `USER_PROVIDED` 来源。
- 不把 clangd 能索引等同于目标可构建。

## 独立入口

`run_windows_precheck(workspace_snapshot, target_scope, windows_environment, metadata?) -> windows_precheck_report`

## 环境资格门

主体检查前必须生成资格收据，逐项记录：

1. 实际编译器/解析器及版本，与产品工具链差异。
2. 精确 target、语言标准、宏、平台分支、强制 include、PCH。
3. 头文件/生成头路径的完整性、搜索顺序和替代 stub。
4. compile commands 来源、覆盖文件数、失败解析数、索引新鲜度。
5. 当前工作区快照和 build profile。

随后必须运行端到端负向 canary：经与真实目标相同的文件发现、target routing、读取、Provider 和报告入口处理隔离负样本与控制样本，并产生类型化 Receipt。canary 不得污染仓库。当前 MVP 仅有 detector self-test；不能据此宣称已通过本资格门。

## 检查层

- 结构层：多探测器括号、EOF、符号差分和解析诊断。
- 编译语义近似层：在可还原的 compile command 下做只语法检查/静态诊断。
- 构建接线层：调用 build-dependency-audit 产物或等价目标证据。
- 业务/DT 静态层：追踪测试注册、输入期望、生产/消费契约和信号数据线；只给静态结论。

## 失败关闭

编译器不同、头路径不完整、目标未覆盖、构建产物未解析、条件编译只完成近似枚举、命令未实际执行、
诊断被过滤或退出码未知，均必须显式降级。报告只能写“合格范围内未检出”，禁止写笼统“没问题”。

## Side effects

只读代码；允许在独立临时目录建立索引和 canary。不得安装依赖、改工程文件、生成/覆盖产品构建目录或调用 WSL。

## 验收要点

- 不完整头路径的场景不会产生 PASS。
- 编译器/target 与产品不一致时，差异和天花板醒目标出。
- 已知错误 canary 未被捕获时停止主体结论资格，但保留诊断工作。
- 无 DT 条件下报告明确哪些风险只能等待目标环境验证。

