# Scene Optimizer on Spark

项目内 Skill 路径：`/home/spark/unbound-maker/skills/unbound-maker-scene-optimizer`。
这是可被 Builder Agent 调用的 CLI，不是常驻 Agent，也没有替换全局安装的 Skill。

## 用法

已有 OpenUSD Python 环境下执行：

```sh
python /home/spark/unbound-maker/skills/unbound-maker-scene-optimizer/scripts/scene_optimizer.py optimize \
  --input /home/spark/unbound-maker/artifacts/scene-meadow-v0.1.0 \
  --request /home/spark/unbound-maker/skills/unbound-maker-scene-optimizer/examples/preserve.json \
  --output /home/spark/unbound-maker/artifacts/meadow-reviewed-v0.1.0
```

默认 `preserve` 只检查并保持原貌。允许远处视觉降档时，改用 `examples/preview.json`。
每次选择新的输出目录，不覆盖前一次结果。打开输出的 `optimized.usda`，复制时必须带上整个目录。
`optimization-report.json` 列出前后计数、实际改动和未测项目，`manifest.json` 记录完整文件校验值。

## 本轮 CPU 环境

Spark 已有 Python 3.11.13 / USD 0.24.5。调用现有 Python 时使用进程级环境：

```sh
env \
  PYTHONPATH=/home/spark/.cache/packman/chk/usd.py311.manylinux_2_35_aarch64.stock.release/0.24.05.kit.7-gl.16400+05f48f24/lib/python \
  LD_LIBRARY_PATH=/home/spark/.cache/packman/chk/usd.py311.manylinux_2_35_aarch64.stock.release/0.24.05.kit.7-gl.16400+05f48f24/lib \
  /home/spark/IsaacSim/_build/linux-aarch64/release/python.sh \
  /home/spark/unbound-maker/skills/unbound-maker-scene-optimizer/scripts/scene_optimizer.py capabilities
```

实际优化时，把上面最后的 `capabilities` 换成 `optimize` 及相应参数。
这些库路径只用于当前主机的 CPU USD 工具，不应写入系统配置或照搬到图形 Isaac 进程。
无需安装依赖或启动 GPU。若设备升级导致路径改变，应重新检查现有运行时。

## 和下一步的衔接

Simulation Runner 读取输出配置，保留同一套角色路径，依据 `base_package` 查找角色运行时。
它需要负责：可玩窗口、角色动力学、移动/起飞、动态 LOD、靠近物体恢复细节、实际接触与帧率测试。
Scene Optimizer 不承诺这些工作已经完成。

本轮开发验证不是 NVIDIA 官方 Verified、数字签名或完整 SkillSpector 安全审核。
所有素材仍保留原有来源与许可记录；没有公开上传。
