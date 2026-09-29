# Asset Builder on Spark

当前开发包：0.1.0-dev.2。只修正了测试隔离方式并补充验证记录；资产构建代码仍为 0.1.0。

## 已验证环境

- 主机：DGX Spark，Linux aarch64。
- Python：Isaac 自带 3.11.13。
- OpenUSD：0.24.5，来自现有 packman 缓存。

- 不额外安装 USD wheel，不修改系统或 Isaac 环境，不打开渲染窗口。

固定 Skill 目录：`/home/spark/unbound-maker/skills/unbound-maker-asset-builder`。
样例输出：`/home/spark/unbound-maker/artifacts/blue-cat-v0.1.0`。
这是可从命令行或上层 Agent 调用的 Skill，不是已经接入 OpenClaw/Codex 的常驻 Agent 服务。

## 运行

以下是本轮探测确认的本机路径；在其他机器上重新检查，不能直接假设路径相同。
使用子 shell 的环境变量，退出后不会影响现有 Isaac 会话。

```sh
(
  export PYTHONPATH=/home/spark/.cache/packman/chk/usd.py311.manylinux_2_35_aarch64.stock.release/0.24.05.kit.7-gl.16400+05f48f24/lib/python
  export LD_LIBRARY_PATH=/home/spark/.cache/packman/chk/usd.py311.manylinux_2_35_aarch64.stock.release/0.24.05.kit.7-gl.16400+05f48f24/lib
  /home/spark/IsaacSim/_build/linux-aarch64/release/python.sh \
    /home/spark/unbound-maker/skills/unbound-maker-asset-builder/scripts/asset_builder.py capabilities
)
```

构建新版本时，同样在该子 shell 中调用：

```sh
/home/spark/IsaacSim/_build/linux-aarch64/release/python.sh \
  /home/spark/unbound-maker/skills/unbound-maker-asset-builder/scripts/asset_builder.py build \
  --request /home/spark/unbound-maker/skills/unbound-maker-asset-builder/examples/blue-cat.json \
  --output /home/spark/unbound-maker/artifacts/blue-cat-v2
```

选择尚不存在的输出目录；旧目录不会被覆盖。参考 `asset.usda`，复制时保留整个输出文件夹。

在同一子 shell 中运行测试：

```sh
/home/spark/IsaacSim/_build/linux-aarch64/release/python.sh \
  -m unittest discover \
  -s /home/spark/unbound-maker/skills/unbound-maker-asset-builder/tests -v
```

## 验证边界

本轮检查了请求校验、USD 文件生成、颜色/缩放、77 个网格与 14 个骨骼关节、绑定、依赖、搬迁和不覆盖旧文件。
未测试实时渲染、物理运动或完整前端 Agent 流程。正式安全扫描、Agent A/B 评测和团队签名仍未进行。
