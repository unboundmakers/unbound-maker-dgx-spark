# Personality Builder：Spark 使用说明

这是一个供 Agent 调用的本地可执行 Skill，尚未注册为常驻 Agent 或接入前端按钮。旧的可玩场景没有替换。

## 路径

- Skill：`/home/spark/unbound-maker/skills/unbound-maker-personality-builder`
- 输入：`/home/spark/unbound-maker/artifacts/blue-cat-v0.1.0`
- 首个输出：`/home/spark/unbound-maker/artifacts/blue-cat-personality-v0.1.0`
- USD 入口：输出文件夹中的 `personality.usda`
- 操作模块：输出文件夹中的 `runtime/personality.py`

## 构建命令

下面使用本机已有的 USD 运行时，仅设置当前进程的环境变量，不更改 Isaac 或系统配置。
换一台机器要重新定位已有运行时，不能照抄这些缓存目录。

```sh
env \
  PYTHONPATH=/home/spark/.cache/packman/chk/usd.py311.manylinux_2_35_aarch64.stock.release/0.24.05.kit.7-gl.16400+05f48f24/lib/python \
  LD_LIBRARY_PATH=/home/spark/.cache/packman/chk/usd.py311.manylinux_2_35_aarch64.stock.release/0.24.05.kit.7-gl.16400+05f48f24/lib \
  /home/spark/IsaacSim/_build/linux-aarch64/release/python.sh \
  /home/spark/unbound-maker/skills/unbound-maker-personality-builder/scripts/personality_builder.py build \
  --asset /home/spark/unbound-maker/artifacts/blue-cat-v0.1.0 \
  --profile /home/spark/unbound-maker/skills/unbound-maker-personality-builder/examples/flyingcat.json \
  --output /home/spark/unbound-maker/artifacts/blue-cat-personality-next
```

`blue-cat-personality-next` 必须不存在。成功后 CLI 返回 JSON；同时生成 `manifest.json`。
复制作品时带上整个输出文件夹。这里的 Python 环境设置只适用于 CPU USD 检查，不用于强行替换 Isaac 的图形运行时。

## 怎么接按钮

已有角色动画控制器时，使用 `PersonalityState` 和 `compose_pose`，由原来的控制器统一写入骨骼。
按钮分别调用 `select('natural')`、`select('curious')`、`select('angry')`；转头调用 `turn(yaw, tilt)`，回正用 `center()`。
没有其他动画控制器的独立预览才使用 `PersonalityController`。

技能只负责表达，不控制行走、起飞、重力、质量、相机，也不占用任何按键。
本次验证是 CPU 的骨骼、蒙皮与文件构建检查，不能代替下一步的 Isaac 窗口目视验收。
