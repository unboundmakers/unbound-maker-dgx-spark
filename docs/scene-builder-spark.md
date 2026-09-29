# Scene Builder：Spark 使用说明

## 已部署路径

- Skill：`/home/spark/unbound-maker/skills/unbound-maker-scene-builder`
- 只读模板素材根目录：`/home/spark/unbound-maker-meadow-v0.3`
- 示例角色：`/home/spark/unbound-maker/artifacts/blue-cat-personality-v0.1.0`
- 草地输出：`/home/spark/unbound-maker/artifacts/scene-meadow-v0.1.0/scene.usda`
- 太阳系输出：`/home/spark/unbound-maker/artifacts/scene-space-v0.1.0/scene.usda`
- 月球输出：`/home/spark/unbound-maker/artifacts/scene-moon-v0.1.0/scene.usda`

这是三个独立的静态场景包，不是已经接好按键的播放器。复制整个产物目录后，不需要继续引用旧模板目录。月球的宇航员仍需要 Isaac 自带 OmniPBR/OmniGlass 材质模块。

## 再生成一次

使用新的输出目录，不能覆盖上面的已完成版本。更换 `examples/moon.json` 为 meadow.json 或 space.json 即可选择其他模板。

```sh
env \
  PYTHONPATH=/home/spark/.cache/packman/chk/usd.py311.manylinux_2_35_aarch64.stock.release/0.24.05.kit.7-gl.16400+05f48f24/lib/python \
  LD_LIBRARY_PATH=/home/spark/.cache/packman/chk/usd.py311.manylinux_2_35_aarch64.stock.release/0.24.05.kit.7-gl.16400+05f48f24/lib \
  /home/spark/IsaacSim/_build/linux-aarch64/release/python.sh \
  /home/spark/unbound-maker/skills/unbound-maker-scene-builder/scripts/scene_builder.py build \
  --request /home/spark/unbound-maker/skills/unbound-maker-scene-builder/examples/moon.json \
  --assets /home/spark/unbound-maker-meadow-v0.3 \
  --character /home/spark/unbound-maker/artifacts/blue-cat-personality-v0.1.0 \
  --output /home/spark/unbound-maker/artifacts/scene-moon-next
```

这些运行时路径已在当前 Spark 检查；其他机器需重新定位。环境变量只作用于本次 CPU 构建，不要写到全局配置或强行用于 Isaac 图形会话。

## 前端和 Agent 可以传什么

- scene_id：meadow / space / moon。
- mode：前两者为 story，月球为 experiment；不匹配就报错。
- spawn_id：第一版只开放 start，避免任意坐标落到石头或地面内部。
- heading_degrees：-180 到 180 度。

质量、推力、飞行计时、模式切换按钮和相机跟随仍属于 Simulation Runner。当前场景写入默认重力，不会自动运行物理模拟或生成角色刚体。

## 检查与边界

Mac/Spark 均完成三模板构建及 CPU 测试。Skill 压缩包约 26 KiB，不包含第三方大素材。
独立输出磁盘大小约为草地 37 MB、太阳系 16 MB、月球 148 MB；不能把这些数值当成 GPU 占用。
月球的两种标准 MDL 文件已在当前 Isaac 安装中找到；本轮未启动渲染，未验证着色器编译及实际画面。
旧场景没有被修改。本轮没有全局安装 Skill、启动 Agent、上传 GitHub 或开放网络服务。
