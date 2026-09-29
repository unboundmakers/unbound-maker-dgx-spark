# 第三方来源与分发边界

本文件列出当前实现的依赖和场景来源。它不是对所有资产作出的许可保证，也不把第三方内容重新授权。核对日期：2026-09-29。

## 随源码提供的内容

本次准备发布的是自研 Agent / Skill 源码、配置接口、文档和验证摘要。模型权重、Isaac Sim / Kit 安装包、第三方场景源模型和贴图不包含在源码包内。场景 catalog 仅登记依赖路径、哈希和使用参数。

## 场景素材

| 来源 | 当前用途及记录 | 处理方式 |
| --- | --- | --- |
| [Poly Haven](https://polyhaven.com/license) | `meadow_2k.exr`；此前提供的 `qwantani_night_puresky_2k.exr` 夜空素材 | Poly Haven 资产按 CC0 提供；本次不打包 EXR。获取入口：[Meadow](https://polyhaven.com/a/meadow)、[Qwantani Night PureSky](https://polyhaven.com/a/qwantani_night_puresky)。保留来源便于追溯。 |
| [NASA Science](https://science.nasa.gov/solar-system/) / [NASA SVS 4720](https://svs.gsfc.nasa.gov/4720/) / [NASA SVS 14959](https://svs.gsfc.nasa.gov/14959/) | 行星和月球的源图及衍生贴图。具体记录在场景包 `assets/space/nasa/provenance.json`、`assets/moon/provenance.json` | 遵守 [NASA 媒体使用说明](https://www.nasa.gov/nasa-brand-center/images-and-media/)，逐项保留原始署名、第三方权利提示。不能将 NASA 托管的全部素材一律标成 CC0。源码包不含源图。 |
| [NVIDIA Omniverse 示例内容](https://docs.omniverse.nvidia.com/composer/latest/prod_content/mount-content.html#astronaut) | 宇航员及其贴图、两种草模型、碎石贴图改编。记录包括 `assets/astronaut-textures/provenance.json`、`overrides.json` 和 `assets/GRAVEL-SOURCE.md` | 适用具体下载资源随附条款；不把 NVIDIA 代码许可证套用于素材。原文件、衍生贴图均暂不再分发。移除服装标识不改变源素材权利。 |
| 团队月球车和着陆器 | `assets/lunar-vehicles-v1/README.md` 和资产包记录 | 未在本轮逐项核对来源与公开再分发权限，暂不随源码包分发。 |
| 飞行猫原创角色 | `skills/unbound-maker-asset-builder/assets/template.json` 记录模板身份 | 已确认项目展示；不开放角色源文件复用，见 [授权范围](LICENSING.md)。 |

第三方素材的具体下载、修改和校验记录随本地场景包保存。源码中的 catalog 是索引，不包含完整的逐项授权证据；未来提供场景下载包前仍要补齐该检查。

## 运行依赖

| 依赖 | 来源 | 说明 |
| --- | --- | --- |
| Isaac Sim / PhysX / Omniverse Kit | [Isaac Sim](https://github.com/isaac-sim/IsaacSim)、[NVIDIA 文档](https://docs.isaacsim.omniverse.nvidia.com/) | 用户单独安装，遵守所安装版本及其组件的条款；仓库源码许可不替代 Kit 和附带素材条款。 |
| OpenUSD / pxr | [OpenUSD](https://github.com/PixarAnimationStudios/OpenUSD) | 单独安装，保留上游许可证和 notices。 |
| Ollama | [Ollama](https://github.com/ollama/ollama) | 本地推理运行时单独安装，不随源码包分发。 |
| Qwen 模型 | [Qwen](https://huggingface.co/Qwen) | 权重单独下载，按具体模型的 model card 和许可证使用。本版已分别实测 `qwen2.5:7b` 网页链路和 `qwen3.6:35b-a3b` 独立 Agent 链路；均不随源码分发权重。 |
| 团队前期项目 | [DGX-AI-GO](https://github.com/charinkers/DGX-AI-GO) | 教育定位及前端规划参考。本版尚未合并其代码；未来复制代码前需核对上游许可并保留声明。 |

仅引用来源或参与相关比赛，不意味着得到机构背书或 NVIDIA 官方认证。
