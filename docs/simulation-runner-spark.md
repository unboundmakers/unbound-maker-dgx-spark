# Simulation Runner on Spark

版本：0.1.0 开发版。仅部署到项目目录，没有全局安装、常驻服务或公开上传。

## 位置

- Mac 源码：项目根目录下的 `skills/unbound-maker-simulation-runner`。
- Spark Skill：`/home/spark/unbound-maker/skills/unbound-maker-simulation-runner`
- Spark 场景：`/home/spark/unbound-maker/artifacts/optimized-{meadow,space,moon}-v0.1.0`
- 已验证运行环境：`/home/spark/IsaacSim/_build/linux-aarch64/release/python.sh`，Isaac Sim 5.1。

## 最小调用

以下在 Spark 终端运行。输出目录必须未存在；失败重试也应换一个新目录。

```sh
cd /home/spark/unbound-maker
python3 skills/unbound-maker-simulation-runner/scripts/simulation_runner.py capabilities
python3 skills/unbound-maker-simulation-runner/scripts/simulation_runner.py prepare \
  --input artifacts/optimized-moon-v0.1.0 \
  --request skills/unbound-maker-simulation-runner/examples/smoke.json \
  --output artifacts/my-moon-test-001
python3 skills/unbound-maker-simulation-runner/scripts/simulation_runner.py launch \
  --job artifacts/my-moon-test-001 \
  --isaac-python /home/spark/IsaacSim/_build/linux-aarch64/release/python.sh \
  --timeout-seconds 240
```

启动前检查 GPU 温度和其他正在运行的工作，不并行开多个仿真。
默认只执行 10 秒模拟时间，包含启动的墙钟时间更长，结束后自动退出。
不要把 CPU USD 检查用的库路径全局写入 Isaac 环境；launcher 会移除这些进程级覆盖。

另一个终端查询或停止：

```sh
python3 skills/unbound-maker-simulation-runner/scripts/simulation_runner.py status --job artifacts/my-moon-test-001
python3 skills/unbound-maker-simulation-runner/scripts/simulation_runner.py stop --job artifacts/my-moon-test-001
```

停止仅针对本任务。不要使用 killall/pkill 去清理所有 Kit 或 Python 进程。
launcher 是前台监督进程，不是脱离终端的服务；后续由 Agent 管理其生命周期。

## 故事与实验

- meadow / space：故事预设，物理参数只读。
- moon：实验；environment 选 earth / moon / zero，质量 0.5..10 kg，推力 0..50 N，时长 5/10/20 秒。
- 推力不大于重量时返回 warning，允许实验，不自动增大推力。
- 参数修改后创建新任务；当前不在窗口里热切换场景或环境。

将 request 换为 `examples/interactive.json` 可准备 60 秒交互窗口，但要有 Spark 桌面显示环境。
SSH 连通不代表能在 Mac 显示远端窗口；尚未封装网页串流。
方向键移动，A 起飞，太空 Z 下降/Space 刹车，R 重置，C 切换相机，Esc 退出。
表情、转头用窗口按钮；月球实验到时后停止接收移动输入，R 可重新开始，重力继续作用。
真人键盘焦点和按钮点击仍需单独验收。

## 验收

同时检查 `launch-report.json` 与 `run-report.json`，不可只看退出码为 0。
查看 `preview.png` 和 `trajectory.json`；轨迹每行是时间、XYZ、速度 XYZ、离地距离。
哈希清单和日志用于复查，不等于签名或官方认证。

运行模型是胶囊刚体 + 力控制 + 视觉骨骼动画；包含教学用阻尼，不是完整月面真空动力学、机器人训练或 Sim2Real。
场景素材不包含在 Skill zip 中，运行前必须准备完整独立场景包。
