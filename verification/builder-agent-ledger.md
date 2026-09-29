# Builder Agent · 已完成的执行验证

日期：2026-09-29。各条记录对应其实际测试版本与环境。

- 本地协议、存储、参数边界、工具执行、取消、超时、HTTP 与产物校验：Mac / Spark 各 26 项回归通过。
- 结构化五步链路：月球 10 秒仿真通过；推力修改复用四个阶段，Runner 新运行。[报告](builder-agent/integration-structured-7dbe0811e3684f85b7b2b839bbec168c.json)
- Qwen3.6-35B-A3B：独立 Agent 集成与结构化推力修改复用通过。[记录](builder-agent/qwen36-acceptance.md)
- Qwen2.5-7B：本地真实模型链路通过，含一次 JSON 修复。[记录](builder-agent/qwen25-acceptance.md)
- 最小网页：Qwen2.5 中文需求、构建、真实截图、报告下载、参数重跑与移动布局检查通过。[记录](builder-agent/frontend-acceptance.md)
- 真实取消：启动 Isaac 后取消，检测到的剩余 Isaac 进程为空。[报告](builder-agent/cancel-3722c4ba551449db8e2c8675e888de28.json)
- 缓存与结果：资产哈希校验、四阶段复用、Runner 不复用、报告身份及失败状态检查通过。
- Ollama 0.34.4：独立 ARM64 安装，安装归档 SHA256 与官方清单一致，保留系统安装与模型缓存。

以上是团队实测记录。完整测试范围及对应环境见[验证汇总](release-20260929/README.md)。
