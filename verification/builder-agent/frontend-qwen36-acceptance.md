# Qwen3.6 网页联调验收

2026-09-29，Chrome 经 SSH 隧道连接 DGX Spark。模型为本地 Ollama 0.34.4 的 `qwen3.6:35b-a3b-spark128`，Q4_K_M，`num_batch=128`。

1. 网页提交蓝色飞行猫、月球、2kg、7N、10 秒需求。模型完成五阶段构建，Isaac 真实运行，页面返回截图并下载报告，11/11 项检查通过。
2. 网页将推力改为 11N，复用前四阶段、重新运行 Runner，返回新截图与报告，11/11 项检查通过。此次参数修改走结构化路径。
3. 首次任务五阶段均未命中构建缓存，使用既有角色及场景模板；全程未替换为 Qwen2.5。本轮未出现 CUDA 错误。
4. 鉴权拒绝、截图加载、报告下载、390px 窄屏布局检查通过，浏览器未捕获异常为零。

任务：`61727ea6e9044c8cacbaa44981651706` → `4b9374ecd34e400281cc4628b74ecbaa`。

[网页验收结果](frontend-qwen36-result.json) · [7N 运行报告](frontend-qwen36-7n-report.json) · [11N 运行报告](frontend-qwen36-11n-report.json)
