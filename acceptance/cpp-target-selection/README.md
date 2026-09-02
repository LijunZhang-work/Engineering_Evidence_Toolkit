# 真实 C++ 纵向验收目标选择

`FINAL` 不是若干路径和摘要的自报组合。选型、Windows 工具链发现、每个候选构建计时分别需要
`CppAcceptanceReceipt`，其角色、主体、producer tool、命令、依赖、结果字段都必须匹配；同一个
无关文件不能复用为三种回执。当前记录仍为 `PROVISIONAL`，不存在这些正式回执。

本目录冻结候选集、量化口径、许可证文件摘要、commit 与尚未完成的 Windows 构建指标。它不是“挑一个明星多的仓库”，也不会把缺失的 MSVC 结果填成估计值。

当前机器测量命令：

```powershell
.\.venv\Scripts\python.exe tools\measure_cpp_candidate.py --repo <candidate-repo> --pretty
```

当前暂选 Catch2：冻结于 `devel@317ac1ed4c0bb6e6b91eafc817e05c488feffcb3`，仓内许可证为 BSL-1.0。它的产品范围约 55,322 行、103 个编译单元、161 个头文件，并具有较丰富的 CMake target 与测试结构，足以暴露目标接线、include、增量构建和报告问题，同时不接近 LLVM/Chromium 的资源规模。

该选择仍是 `PROVISIONAL / INCONCLUSIVE`。本机未发现 MSVC、Windows SDK、CMake 或 Ninja；两次 winget 后台安装和一次可见 RunAs 尝试均未越过 UAC，退出码为 1602。只有在同一台机器、同一生成器和相同 Release 配置下测完三个候选的冷构建与无操作增量构建，并对 Catch2 运行测试后，才能晋级为 `FINAL / PASS`。环境发现、每个候选的构建测量和最终选择还必须分别绑定仓内可打开、内容寻址的 Receipt；仅把标量补成 `AVAILABLE/MEASURED/PASSED` 不能晋级。

上游依据：

- [yaml-cpp 官方仓库](https://github.com/jbeder/yaml-cpp)：MIT，官方说明用 CMake 跨平台构建并支持测试。
- [Catch2 官方仓库](https://github.com/catchorg/Catch2)：BSL-1.0；仓库提供 CMake target、CTest 集成和 Windows `buildAndTest.cmd`。
- [Google Benchmark 官方仓库](https://github.com/google/benchmark)：Apache-2.0；CMake 对 MSVC 有显式分支，测试依赖 GoogleTest。

候选仓浅克隆必须位于用户选择的工具集外目录，通过 `measure_cpp_candidate.py --repo <candidate-worktree>` 显式传入，不会作为 Toolkit 源码提交。真实缺陷注入只能发生在另建的隔离副本或 worktree 中，原始候选基线保持干净。

## 已执行的真实源码静态子集

`REAL_VALIDATION.yaml` 记录了固定 Catch2 commit 上五个隔离场景的工作树 Observation、机器/专业/小白报告文件哈希、before/after Workspace 与 Target Manifest ID、Gate 与限制：少右括号、文件尾截断、缺直接 include、实现文件未接入 CMake target、外部编译错误验收夹具。记录只保存相对于运行时证据根的路径，不保存任何电脑的绝对路径。需要重新打开原始文件时，通过 `--cpp-evidence-root <external-evidence-root>` 或 `EET_CPP_EVIDENCE_ROOT` 挂载；严格复验还需增加 `--require-cpp-evidence`。外部错误明确为 `ACCEPTANCE_FIXTURE`，不能冒充用户生产证据。

该记录是 `PARTIAL_STATIC_SUBSET / qualification_effect: NONE`。只有前两项结构破坏在静态 MVP 范围内满足用例；缺 include、手工 target 清单修复和外部错误仍为 `NOT_SATISFIED / INCONCLUSIVE`。完整报告保存在仓外本地证据根，内容 ID 可识别但不具备跨机器可移植性；生成脚本的运行时 artifact hash 当时未捕获。因此“缺 include 已被编译器复验”“Catch2 构建或测试通过”“Windows 公司环境已资格化”仍是禁止结论。
