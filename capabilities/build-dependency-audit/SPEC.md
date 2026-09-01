# Build and Dependency Audit

状态：`DESIGNED`。

## 职责

证明代码究竟是否进入目标，并审计 C/C++ 常见传递依赖问题。覆盖 source→target 成员关系、直接/间接 include、include 搜索顺序、宏与 feature flag、生成头、预编译头、编译选项、链接库/符号、条件平台分支，以及 DT/TT 的用例发现与注册链。

## 非职责

- 不把 IDE 能跳转或某文件存在当作“已编译”。
- 不把另一个 target/编译器的成功当目标 target 成功。
- 不默认传递 include 稳定；未直接声明的依赖必须显式报告。
- 默认不运行构建或 DT，除非有单独的执行 provider 并在收据中声明。

## 独立入口

`audit_build_wiring(workspace_snapshot, target_questions, build_metadata?) -> build_dependency_report`

## 必查维度

| 维度 | 所需证据 |
|---|---|
| 源文件接入 | 构建脚本展开后属于哪个 target、条件和平台 |
| Include | 实际解析到的文件、`-I/-isystem` 顺序、直接与传递来源 |
| 宏/配置 | target 级定义、生成配置、条件编译选择 |
| 生成物 | 生成规则、输入、产物路径、时效和依赖边 |
| 链接 | 对象/库进入顺序、符号定义与引用、平台库 |
| DT/TT | 测试源码进入测试 target、注册宏、发现列表、fixture/data 依赖 |

输出必须区分“源码存在”“被某 target 引用”“在指定 profile 展开后进入”“由指定编译器处理”四种状态。

## 失败关闭

缺 compile database、构建展开信息、目标选择或宏配置时不得输出 `WIRED`。零诊断不等于目标被检查；必须先证明命令确实覆盖到文件/测试。传递 include 只在当前图可见时也要标记脆弱性。

## Side effects

只读构建元数据与代码；可在 run 目录生成解析后的图和收据。不得改 build 文件、生成物或缓存。

## 验收要点

- 一个未加入 target 的 `.cpp` 即使语法正确，也被识别为未接线。
- 移除偶然的传递 include 后，审计能定位直接依赖缺失。
- DT 文件存在但未注册/未发现时不能判已覆盖。
- 报告绑定精确 target、编译器、宏、头路径和快照。

