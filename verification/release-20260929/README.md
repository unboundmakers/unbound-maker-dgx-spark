# 团队验证记录 · 2026-09-29

范围：五个自研 Skill、Builder Agent 与最小网页的对应版本。本文记录已执行的检查与证据，不使用 NVIDIA 官方认证标识。

## 模块回归

| 模块 | Mac | Spark |
| --- | --- | --- |
| Asset Builder | 14 通过 | 14 通过 |
| Personality Builder | 16 通过 | 16 通过 |
| Scene Builder | 10 通过 | 10 通过 |
| Scene Optimizer | 13 通过 | 13 通过 |
| Simulation Runner | 13 通过 | 13 通过 |
| Builder Agent | 26 通过 | 26 通过 |

每个平台独立执行 92 项。Mac 使用 Python 3.12 / USD 25.5.1 和单 USD 工作线程；Spark 使用已配置的 CPU USD 环境。模块回归数量不等于真实模型调用数量。

原始汇总：[Mac](mac-cpu-report.json) · [Spark](spark-cpu-report.json)。42 个运行和测试文件在本轮比对时 SHA256 一致。结论对应报告记录的源码版本。

## 真实运行

- Qwen3.6-35B-A3B：`spark128` 网页端到端通过；蓝色角色、月球、2kg、7N、10 秒；网页修改为 11N 后复用前四阶段并启动新 Runner。两次均返回真实截图和报告，各 11 项检查通过。[证据](../builder-agent/frontend-qwen36-acceptance.md)
- Qwen2.5-7B：最小网页提交、进度、实际截图、报告下载、推力重跑、鉴权拒绝和移动端布局检查通过。[证据](../builder-agent/frontend-acceptance.md)
- 取消与清理：真实 Isaac 作业启动后取消，检测到的剩余 Isaac 进程为空。[证据](../builder-agent/cancel-3722c4ba551449db8e2c8675e888de28.json)
- Personality：默认隐藏尖牙、手动生气时显示、重置恢复；独立头部层级、已有身体帧及单一骨骼写入者检查通过。
- Runner：退出码为零但缺报告时判失败；任务本地停止、超时清理、地球/月球重力配置、动态 LOD 保留碰撞结构检查通过。

## 说明题与物理边界复核

以本地 Qwen3.6 进行有限说明题测试，模型不具备执行工具，因此这些回答只作为说明与边界检查。

已复核的回答包括：默认自然、手动选择生气、拒绝从儿童绘画推断情绪；保留外观的优化使用 preserve 审计；6kg 在地球上约重 58.86N，11N 推力不足；不能只凭退出码零确认成功；脚本化运行不能替代所有真人按键和所有岩石接触检查。

使用相同权重与 `num_batch=128` 后 Runner 六题均返回。接口返回和逐项正确是不同口径，不将六次返回统一标成六项行为通过。[Runner 原始回答](runner-batch128.json)

## 源码扫描与分发检查

Bandit 1.8.6 检查 4,143 行 Python，0 高、8 中、22 低、0 扫描错误。提示均经人工复核，原始报告见 [bandit.json](bandit.json)。

8 个中等级提示位于测试代码：非法路径测试、本机 HTTP 测试和禁止绑定外部地址的断言。生产路径的 4 个低等级提示涉及固定参数的 subprocess 导入和执行；运行限定为本机单用户受控环境。扫描结果不等于全面安全认证。

公开源码候选的常见密钥初筛与资产排除检查通过。角色原模型、场景原资产、权重、运行数据与令牌不随源码发布。[分发清单](../../docs/asset-distribution.md)

登记与文档包含 Skill 名称、版本、能力范围、输入输出、来源、依赖、使用说明及许可证。
