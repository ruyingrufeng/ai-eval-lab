# 本机内容生产项目实证汇总

盘点时间：2026-08-12。范围：只读检查本机内容项目的 README、交接记录、复盘、技术栈、工作流脚本、错误日志与验收结果。未读取密钥/Cookie，未运行生成任务，未评价或收录具体成品内容。

## 证据采用规则

项目记录中存在路线反复与旧结论冲突。本文按以下优先级判断：

1. 有可复现脚本、固定输入、原始指标和对照实验；
2. 较新的复盘或交接记录；
3. 实际代码中的调用方式；
4. README 或计划性技术栈描述；
5. 仅凭视觉模型描述或主观印象的结论。

因此，“曾经跑通”不自动等于“当前推荐”，“文件存在”也不等于“生产级”。

## 已检查的生产项目

| 项目 | 类型 | 记录成熟度 | 可提取价值 |
|---|---|---|---|
| `~/Documents/MeiXue` | 虚拟角色、图像一致性 | 很高 | ComfyUI API、Flux/SDXL、身份/身体验收、MPS 问题 |
| `~/Documents/Rabynia` | 虚拟角色、批量姿势图 | 很高 | 多路线对照、相似度校准、失败归档、下载排障 |
| `~/Documents/HuLiLi` | 数字人形象探索 | 中高 | Flux IPAdapter、发型变更对身份的影响、参考图决策 |
| `~/Documents/BaiLing` | SillyTavern/数字伴侣与云端实验 | 很高但历史冲突多 | 云端/本地切换、角色卡、VRM、视频边界与付费护栏 |
| `~/Documents/制作演示视频` | 报告/宣传/口播视频 | 高 | HyperFrames、Remotion、Edge TTS、字幕、预检与渲染 |
| `~/Documents/欧洲小城故事集` | 小说式自媒体文章 | 中高 | 选题—细纲—多轮审稿—发布包的版本化流水线 |
| `~/voice-tools` | TTS/ASR 工具集 | 高 | Qwen3-TTS 本地服务、MPS/CPU 路由、并发与懒加载 |

## 图像生产：实际使用方式

### ComfyUI 不是主要靠手工点界面

三个角色项目中至少 61 个 Python 脚本直接调用 `http://127.0.0.1:8188`。常见模式是：

```text
Python 构造 API workflow 图
  → POST /prompt，传 client_id
  → 轮询 /history/{prompt_id}
  → 从 ComfyUI/output 复制结果到项目目录
  → 同时保存 workflow JSON、seed、参数和验收结果
```

这套模式比只保存 ComfyUI UI 工作流更适合批量测试、回归和结果追踪。现有脚本覆盖 CheckpointLoader、GGUF UNet、DualCLIP、KSampler、ControlNet、InstantID、IPAdapter、Flux IPAdapter、RMBG 和 InsightFace 等组件。

### 已验证的正面结论

- Apple MPS 上 Flux.1-dev Q4 GGUF 可以完成全身构图；对“完整人物、圆脸、头到脚”等自然语言约束的理解在现有项目中优于 RealVisXL/SDXL。
- SDXL 的半身 img2img 使用保持比例的 center crop、denoise 0.4，曾得到约 0.66–0.74 的人脸 embedding 相似度；直接拉伸和更高 denoise 会明显漂移。
- “身份像素固定 + 只扩展下方区域”的 outpaint 路线比纯提示词、LoRA、InstantID 或 FaceID 更稳定地保持指定脸部像素。
- InsightFace antelopev2 适合做身份回归指标；全身小脸应先裁剪并放大再提 embedding。
- 固定 seed、保存 API workflow、复制产物到项目目录、失败进入 reject/archive，是已经形成的有效工程习惯。

### 已证明不能直接进入推荐栈的路线

- IPAdapter FaceID 在当前 MPS/全身小脸场景中多次落在 0.09–0.26，相似度不足；某些高权重设置还会使构图只剩半身或风格崩坏。
- InstantID 可以锁住部分脸部，但常把全身构图拉近；不能据此认定为全身身份方案。
- Flux IPAdapter 已能运行，但多个角色项目的人眼和 embedding 验收均显示锁脸不足，约 0.2–0.3；它是可运行组件，不是已验证身份控制方案。
- JuggernautXL v9 在一次 MPS 测试中从约 5 秒/步恶化到约 350 秒/步，应先排查运行状态和兼容性，不适合作默认模型。
- AppleSilicon-FP8 节点与 ControlNet/部分模型出现维度兼容问题，当前已禁用。
- InSwapper 文档存在冲突：早期记录称效果好，较新的母版自换对照得到接近 0 的异常相似度。按证据优先级，当前判定为本机实现损坏/不可用，必须重新做自换基线后才能恢复。

### 关键方法论

- 局部指标通过不等于整体人物通过。脸部 ROI 可接近像素一致，但头身比、颈肩解剖、服装结构仍可能明显失败。
- “9 头身”“腰臀尺寸”等文字只提供方向，不能替代姿态、轮廓、深度或像素级几何约束。
- 身体结构已经错误时，反复局部重绘会把一个缺陷变成接缝、色差、双下巴或贴片感；应淘汰底图重新生成。
- 身份参考必须裁掉无关强特征。例如参考图的高领会持续泄漏成项圈，负面提示词无法可靠消除。
- 自动验收至少应覆盖完整构图、肢体、头身比、肩腰臀比例、异常接缝、脸部相似度；最终仍需整图人工验收。

## ComfyUI 与模型下载的高频问题

| 问题 | 项目证据 | 建议处理 |
|---|---|---|
| Python 包装错环境 | insightface 曾装入 Homebrew Python，而 ComfyUI 用自己的 `.venv` | 所有节点依赖必须用 `~/ComfyUI/.venv/bin/python` 安装和检查 |
| 代理残留 | `127.0.0.1:7892` 无服务，导致 SigLIP/HF 配置加载失败 | 启动前记录并验证代理；本地权重完整时设离线模式 |
| 假权重/坏下载 | 曾出现仅 15 字节、内容为 `Entry not found` 的模型 | 下载后检查大小、哈希/文件头和非零块；坏文件移入 quarantine |
| aria2 空洞预分配 | 看似文件很大，实际数据未下载完整 | 检查非零比例和 `.aria2` 状态，不只看逻辑文件大小 |
| Hugging Face 文件名猜错 | 量化名或仓库路径并不存在 | 下载前先查 API/模型文件清单，不凭记忆拼 URL |
| GitHub/代理不可达 | 自定义节点拉取失败 | 记录镜像来源和 commit；恢复网络后校验上游一致性 |
| 自定义节点接口漂移 | Flux IPAdapter 报 `DoubleStreamBlock` 缺少属性 | 锁定 ComfyUI 与节点 commit，建立最小工作流回归 |
| MPS 精度/兼容差异 | InstantID/IPAdapter 曾需 fp32 修补 | 节点升级后重新跑基线，不沿用旧结论 |
| 统一内存竞争 | 32 GB 同时运行 LLM 与 Flux 余量低 | 大型生成串行执行；生成前卸载 llama-server 活跃模型 |

## 文本与小说/文章生产

“欧洲小城故事集”形成了结构化文本流水线：

```text
3–5 个选题提案
  → 完整细纲（没有细纲不写正文）
  → 正文 v1
  → Gemini 第一轮审稿
  → 审稿意见取舍
  → v2/v3
  → Gemini 第二轮审稿
  → 定稿检查
  → 统一发布包和归档
```

值得转入模型测试框架的能力点：

- 同系列前 4 篇差异检测；
- 长文角色、物件和叙事者视角一致性；
- 去 AI 味：避免金句化、过度对称、工具人、线索过顺和总结式结尾；
- 审稿模型只做“刀片”，不能直接控制栏目方向；审稿意见必须经过取舍；
- 每个版本记录状态、日期、修改目标和下一步动作。

需要注意：该项目依赖 Gemini Web App 的专用笔记本完成两轮审稿，不是完全本地链路。未来评测本地模型时，应分别测试“创作模型”和“批判性审稿模型”，避免同一模型自我确认。

## 视频生产

### 已使用的两条路线

1. **HyperFrames**：报告、数据解说和宣传视频。项目锁定 CLI 版本，使用 `preview → check → render`，要求所有定时元素带时间/轨道属性，GSAP 时间线暂停并登记，避免随机数和网络依赖。
2. **Remotion 4.0.484**：横竖版 PPT 卡片式口播，React 代码驱动画面，Edge TTS 旁白，FFprobe 获取音频时长，Remotion 输出 MP4。

### 已形成的可靠流程

```text
Brief（平台/比例/时长）
  → Script（每页一个结论）
  → Storyboard
  → 主视觉/头像/图标/BGM 素材清单
  → 分段 TTS
  → ffprobe 生成时长 manifest
  → 字幕 manifest
  → 横竖版预检
  → lint/check
  → render
  → 分辨率、帧率、时长、声音和溢出验收
```

项目实测证明：自然语速下一个目标 70–90 秒的视频最终达到 152.6 秒。正确处理是缩短脚本，不是用异常高速 TTS 强压时长。每页时长可用“旁白时长 + 约 0.4 秒”作为初始值。

HyperFrames 项目把 CLI 精确锁到 0.7.21、0.7.22 或 0.7.69，说明可复现渲染依赖版本固定；升级必须运行新版 upgrade/check 后再改锁定版本。

## 语音与 ASR

### Qwen3-TTS 本地服务的实际设计

- FastAPI 提供 OpenAI 风格 `/v1/audio/speech` 和 `/v1/audio/clone`；
- 权重放在本地 Hugging Face cache，启动时设置 `HF_HUB_OFFLINE=1`；
- CustomVoice 1.7B 在 MPS 上按需懒加载；
- Base/VoiceClone 在 MPS 上有 hang 记录，因此代码强制转 CPU；
- MPS 生成不安全并发，服务用 `asyncio.Lock` 串行请求并在忙时返回 429；
- `max_new_tokens=512` 防止失控生成长期占用 MPS；
- WAV 经 FFmpeg 转 MP3，临时文件在请求结束后清理。

这些规避措施应进入正式 TTS 压测：首个请求加载时间、热请求实时系数、429 行为、异常后的后续可用性、长文本上限和 CPU 克隆耗时。

### Edge TTS

视频项目大量使用 `zh-CN-YunjianNeural` 分段生成旁白。优点是简单稳定、可出字幕；限制是依赖微软在线服务、存在并发/IP 限制、长文本断句不稳，而且项目记录提醒其商业使用条件需要复核。因此 Edge TTS 应标记为在线辅助工具，不属于“完全本地模型”。

### 其他语音候选

CosyVoice、Fish Speech、ChatTTS 都有源码或脚本，但当前记录不足以证明完整可用。CosyVoice 测试脚本还存在明显代码问题：将 `prompt_wav` 初始化为 `None` 后直接传给 `os.path.exists`，未达到可靠冒烟测试标准。

## 数字人和交互

- SillyTavern 已用于角色卡、头像、表情、问候语和 character book；本地 llama-server 是主要文本后端。
- VRoid Studio/VRM + Blender 被用于可测量的 3D 身材和姿态骨架，再计划进入 ComfyUI 写实化。这条路线有几何可控性优势，但尚未完成端到端验证。
- 云端 Agnes 图像/视频项目留下较完整参数和护栏记录，但它不是本地生产栈；且真人式数字人视频曾连续失败，纯文生视频脸漂，图生视频相对更稳。
- 当前没有经过本机验证的 MuseTalk、LivePortrait 或 Wav2Lip 口型链路。不能把 TTS、VRM 和静态图工具的存在合并推断为“数字人已经可生产”。

## 对本项目选型的直接影响

### 可晋级为“已有实证”

- llama.cpp 本地服务与 SillyTavern 链路；
- ComfyUI API 式工作流执行；
- FLUX.1-dev Q4 在 MPS 上的基础图像生成；
- RealVisXL/SDXL 基础生成与低 denoise img2img；
- antelopev2 身份测量（作为辅助指标）；
- Qwen3-TTS CustomVoice 服务框架；
- HyperFrames 与 Remotion 渲染；
- Edge TTS 分段旁白（在线工具）。

### 保持“可运行但未通过任务验收”

- Flux IPAdapter 锁脸；
- InstantID/FaceID 全身身份控制；
- LoRA 长期角色一致性；
- Qwen3-TTS 声音克隆；
- faster-whisper 中文 ASR；
- VRM/Blender → 写实角色；
- Open WebUI/Hermes 作为生产编排层。

### 当前应标记失败或阻塞

- 本机 InSwapper 当前副本；
- AppleSilicon-FP8 插件组合；
- 当前 FLUX IPAdapter 节点版本组合；
- 纯提示词精确控制人体几何；
- 本地视频生成与口型数字人链路。

## 下一步测试应复用的现有资产

1. 复用角色项目的固定参考图、seed、workflow JSON 和 reject 样本，建立图像回归测试；敏感资产留在原项目，不复制进本仓库。
2. 把 `accept_face.py` 的裁脸放大与 embedding 逻辑抽象成通用 QA，但新增整体人体/构图指标。
3. 用现有三套 MLX 和三套 GGUF 模型执行故事选题、细纲、长文一致性、审稿与 JSON 测试。
4. 复用视频项目的 audio/subtitle manifest 和验收清单验证 TTS 与渲染链路。
5. 为所有工作流增加工具版本、模型哈希、运行时峰值内存和原始错误记录，避免只留下结果图。
