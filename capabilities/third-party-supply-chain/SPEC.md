# Third-party Supply Chain

状态：`DESIGNED`。

## 职责

管理代码事实、解析、索引、Memory 和审查 provider 的来源与产物生命周期：固定上游 revision、依赖闭包、可复现构建、固定 artifact、许可证/漏洞审查、部署收据和重新验证条件。它使 provider 可替换，而不污染稳定能力契约。

## 非职责

- 不选择某 provider 的事实结论，不代替 capability adapter。
- 不接受 `latest`、浮动 branch 或环境中偶然存在的包作为可复现制品身份。
- 不决定允许走哪条网络、模型端点、下载通道或制品源；这些由最外层运行边界统一裁决。
- 不把 Git commit 单独当完整供应链身份；必须处理 submodule、LFS、patchset 和依赖锁。
- 不在本规范中硬编码会过期的安装命令或仓库推荐。

## 独立入口

`qualify_provider_artifact(provider_source, policy, receipts?) -> provider_qualification`

首次环境对齐使用 [`ENVIRONMENT_ASSET_INVENTORY_TEMPLATE.md`](ENVIRONMENT_ASSET_INVENTORY_TEMPLATE.md)。该清单把 CodeGraph、Memory Provider、clangd 等源码路径、制品路径和版本要求显式化。缺失或路径有误时，能力必须给出“AI 按授权下载 / 用户自行下载 / 本次不下载并接受影响”三种策略，不得擅自下载，也不得让一个可选 Provider 阻塞所有独立检查。

## 生命周期分离

必须分别记录：

- 源码/制品生命周期：revision、patch、依赖、构建、签名、漏洞与许可证。
- 部署/索引生命周期：安装目标、配置、corpus、build profile、索引版本与时效。
- profile 绑定生命周期：哪些 profile/能力当前选择它及替换策略。

退役使用 `RETIRED/UNBOUND`，保留历史收据，不以“删除”抹去审计链。任何日期性 provider 调研放入 adapter/catalog，不进入稳定内核。

## 失败关闭

revision 浮动、artifact 无摘要、依赖不闭合、许可证未知、镜像/构建/部署任一收据缺失时为 `NOT_QUALIFIED`。曾经合格但环境/漏洞/输入 profile 变化时为 `REVALIDATION_REQUIRED`，不得继续冒充 ACTIVE。

## Side effects

资格评估默认只读并写收据；获取源码、构建和安装属于另行授权的 provider 运维动作，不由本入口隐式执行。具体访问许可只接受最外层运行边界的 Receipt。

## 验收要点

- `latest` 或仅 branch 名不能通过。
- 相同 commit 但不同 patch/submodule 得到不同 artifact 身份。
- provider 退役后历史 run 仍能定位当时制品。
- 供应链 PASS 不会被报告成分析准确性 PASS。
- 缺失工具会触发三选一对齐，且不依赖该工具的工作继续执行。
