# 公司运行边界适配器

状态：**DESIGNED / NOT_RUN**。

这是工具集最外层的一张“门禁卡”。它是网络、模型 API、密钥、数据外发、运行期下载和制品来源策略的唯一 Canonical Owner。具体规则只写在 [`ADAPTER.yaml`](ADAPTER.yaml)，本文件不复制规则值。

内部 Capability 只声明自己是否需要模型推理、Embedding、远程服务或 Provider 制品；它不能知道公司端点、密钥名、网络路由或允许列表。DeepSeek Harness、Memory 和 Code Fact 都通过同一个边界取得带 Receipt 的 `ALLOWED / DENIED / UNCONFIGURED` 决定。

这样做有三个直接结果：

1. 更换 Memory 后端或代码检索 Provider 时，不必把公司限制再写一遍；
2. 配置好的公司模型 API 可以使用，但密钥只在运行时配置，不进入 Memory、证据包或报告；
3. 边界未配置或拒绝访问时，内部能力必须如实返回不可用，不能伪装成“没有找到”或“没有问题”。

这里不负责代码事实、记忆内容、Provider 准确性或总体 Verdict。它只决定某次环境访问是否被允许。
