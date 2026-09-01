# 适配器目录

状态：**DESIGNED**  
验证状态：**NOT_RUN**

适配器把外部运行环境、公司工具或托管系统映射到工具箱的公共契约。它们不拥有事实模型，也不应把某个公司的命令写进通用能力内核。

## 适配器与 Provider 的区别

| 对象 | 责任 | 例子 |
|---|---|---|
| Capability | 定义稳定输入、输出、证据与失败语义 | Code Fact |
| Provider | 用一种方法生产能力所需证据 | ripgrep、Git、clangd、图索引 |
| Adapter | 连接外部环境或公司系统 | DeepSeek Harness、公司拉取/工作区/提交脚本 |
| Outer Runtime Boundary | 对所有 Adapter/Provider 的环境访问作唯一裁决 | 公司模型 API、密钥、外发、下载与制品来源 |
| Profile | 组合能力并定义门禁 | Recovery Review |

公司 Python 拉取、工作区和提交脚本属于 source-control adapter，不属于第三方 Provider 的供应链。第三方供应链回答“这个 Provider 工具从哪里来、如何固定和验证”；公司适配器回答“这个项目工作区如何在公司环境中被创建、识别和变更”。

## 通用约束

- 只通过公共契约与能力交互，不能读取 Provider 私有缓存作为隐式接口。
- 明确区分只读动作、可逆写动作与提交/发布动作。
- 默认拒绝提交、合入、上传和外部消息。
- 每次调用记录适配器版本、配置摘要、输入快照、动作、副作用和结果。
- 适配器错误必须可见，不能转译成“没有问题”。
- 密钥、令牌和敏感配置只记录引用或脱敏标识，不能写入证据包。
- 示例配置都是设计，不代表实际安装或验证完成。
- 网络、模型 API、密钥、数据外发、运行期下载与制品来源不得在内部能力或其他 Adapter 重复定义，只引用外层运行边界。

当前设计适配器：

- [`deepseek-harness/ADAPTER.yaml`](deepseek-harness/ADAPTER.yaml)：把 Harness 的任务调用映射到能力契约。
- [`company-source-control/README.md`](company-source-control/README.md)：隔离公司多仓拉取、工作区、修订冻结和提交语义。
- [`company-runtime-boundary/README.md`](company-runtime-boundary/README.md)：唯一的公司运行环境访问策略入口。
