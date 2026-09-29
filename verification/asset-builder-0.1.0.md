# Asset Builder 0.1.0 开发验证记录

日期：2026-09-29。状态：开发包已实现；完整 Skill 验证和公开发布尚未完成。

## 已实现

- 独立 Skill 目录及可执行 Python CLI，无模型服务或网络依赖。
- 输入模板、身体主色、整体缩放；不支持的字段明确拒绝。
- 输出 OpenUSD 引用层、完整模板副本、规范化请求、来源、结构检查和 manifest。
- 77 个 Mesh、14 个骨骼关节及绑定保留；颜色从 sRGB 转换为线性值。
- 不修改原有草地/月球/太阳系场景，不覆盖旧作品，不启动 GPU 场景。
- 打包 Skill Card、6 个 Agent 评测任务、使用示例和测试代码。评测任务尚未交给真实 Agent 跑 A/B。

## 本机证据

环境：macOS，Python 3.12.14，usd-core 25.5.1 / OpenUSD 0.25.5，PyYAML 6.0.3。
测试环境独立位于 /private/tmp/unbound-asset-builder-py312，未更改原场景的 Python 环境。

Skill Creator quick_validate.py：通过。它只验证 Skill 基本结构，不证明安全或有效性。

完整新项目测试命令：

```sh
env PXR_WORK_THREAD_LIMIT=1 python -m unittest discover -s skills/unbound-maker-asset-builder/tests -v
```

14 项测试，包含多个参数子用例；最终单轮输出见 `asset-builder-mac-tests.txt`。
本项目是独立新目录，以上命令覆盖其全部测试；未修改旧场景代码，未在本轮宣称旧 Isaac 回归通过。

测试覆盖：非法字段/JSON/重复键、非有限值和超大整数、依赖缺失、真实 USD 构建、骨骼和材质绑定、主色转换、保留其他颜色、缩放对世界包围盒的影响、搬迁后依赖解析、文件哈希、旧目录/符号链接保护、模板不变与篡改检测。

样例文件：`artifacts/blue-cat-v0.1.0/asset.usda`。请求主色 #2867D7、缩放 1.5；构建成功并通过 USD 结构检查。

开发包：`dist/unbound-maker-asset-builder-0.1.0-dev.zip`，约 823 KiB。解压到独立临时目录后，14 项测试与 Skill 格式检查均通过。
压缩包 SHA256：`e2ba6059c42c1dc45faa326e47273160ff3589e98d0f1cbac3a29b383cfdbf14`。这是校验和，不是发布者签名。

Spark 适配后的当前开发包：`dist/unbound-maker-asset-builder-0.1.0-dev.2.zip`。
SHA256：`72fbc3f5e4c94917bc82c84aa8891de500138046f6aa23128382bbf28560f2ee`。
首版归档保留；第二版修正测试隔离并更新文档，资产构建代码未改。

## 稳定性观察与未关闭风险

默认并行环境的一次完整复测出现 `Invalid prim name ''`、USDC empty path 报错；`test_scale_changes_world_bounds` 失败，`test_source_is_unchanged` 发生读取异常。文件 SHA256 仍与原始模板相同。
随后独立读取正常，默认环境连续 10 轮完整测试通过；设置 PXR_WORK_THREAD_LIMIT=1 后连续 20 轮完整测试通过。
这还不足以断言根因已修复。Mac 暂用单线程进程级配置进行开发测试；不修改系统全局环境，不将其强制应用到 Spark 的 Isaac 进程。
另外，Mac wheel 输出 ARCH_CACHE_LINE_SIZE 警告。上述现象仍需在实际 Spark USD 版本上复核。

[OpenUSD 历史问题 #2662](https://github.com/PixarAnimationStudios/OpenUSD/issues/2662) 有相似的 Apple ARM 间歇性重组错误，但其版本不同，不能据此认定是本次根因。

## Spark 与发布状态

- 重连成功：DGX Spark，Linux aarch64；现有 Python 3.11.13 / USD 0.24.5。未安装依赖，未修改 Isaac 环境。
- 首轮 13 项通过，缺依赖测试失败：-S 没有隔离继承的 PYTHONPATH。将测试子进程改为 -I -S 后，14 项全部通过；没有修改资产构建代码。
- 默认线程配置下追加 5 轮复测：70 项测试，0 失败、0 错误、0 跳过。日志为 `asset-builder-spark-tests.txt` 与 `asset-builder-spark-repeat.json`。
- Spark 实际生成蓝色 1.5 倍角色，构建清单为 `asset-builder-spark-build.json`。文件内容哈希与 Mac 对应样例一致，manifest 中 USD 运行版本按各机器实际记录。
- 固定部署与最后一次验收路径另见 `../docs/asset-builder-spark.md`。未做 Isaac 渲染检查，没有打开 GPU 场景。
- 已部署至 `/home/spark/unbound-maker/skills/unbound-maker-asset-builder`，逐项比对 12 个包内文件，0 差异，证据为 `asset-builder-spark-package-check.json`。
- 固定目录最终再跑 14 项测试全部通过，日志为 `asset-builder-spark-installed-tests.txt`。
- 固定输出 `/home/spark/unbound-maker/artifacts/blue-cat-v0.1.0/asset.usda` 已生成；清单为 `asset-builder-spark-installed-build.json`。未接入常驻 Agent 的自动发现配置。
- 不含刚体/碰撞/质量/物理关节，因此不能宣称完整 SimReady。
- 未运行 SkillSpector/SkillEvaluator，没有团队签名，没有推送 GitHub，没有安装进全局 Codex skill 目录。
- 没有可用独立代码审查 Agent，本轮完成的是作者自查，不冒充独立审查。
- 代码公开许可证与角色公开再分发署名待确认。原资产来源记录在模板登记文件中。

## 下一阶段

Asset Builder 开发包通过实际 Spark 文件构建测试后，继续其余 Skill 的封装与接入。
正式扫描、Agent 正向/负向及有无 Skill 对照评测仍独立进行。通过后才冻结正式发布包与团队签名，最后上传。
