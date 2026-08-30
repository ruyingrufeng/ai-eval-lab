# 本机 AI 工具与模型盘点

盘点时间：2026-08-12。方式：只读检查应用、命令、进程、监听端口、常见模型目录、权重文件和本地健康接口；未启动模型、未生成内容。

## 摘要

| 能力 | 当前主栈 | 状态 |
|---|---|---|
| 文本 / 多模态推理 | llama.cpp 9830 | 已安装，两个服务健康 |
| MLX 文本推理 | mlx-lm 0.31.3 | 已安装，GPU 计算通过；存量模型待接入测试 |
| 图像生成 | 源码版 ComfyUI + SDXL / FLUX | 已安装，当前未运行；最近日志有兼容问题 |
| TTS / 声音克隆 | Qwen3-TTS 1.7B | 服务健康，MPS；权重当前按需未加载 |
| ASR | faster-whisper / OpenAI Whisper | 包与 base 权重已发现，未验证 |
| 交互前端 | SillyTavern / Hermes / Open WebUI | 已安装；SillyTavern、Hermes WebUI 正在运行 |
| 数字人辅助 | VRoid Studio、InstantID/IPAdapter/换脸组件 | 只确认安装或模型存在，未形成已验证数字人链路 |

已识别的 AI 相关资产约 170 GiB；该数值包含工具环境和部分 Hugging Face 缓存，且不排除少量缓存文件在目录间重复。

## 正在运行的本地服务

| 地址 | 服务 | 状态 |
|---|---|---|
| `127.0.0.1:8086` | llama-server 多模型路由 | `/health` 正常；模型按需加载，当前均为 unloaded |
| `127.0.0.1:8087` | Qwen2.5-VL 7B 图像理解 | `/health` 正常；多模态模型已加载 |
| `127.0.0.1:9881` | Qwen3-TTS 本地服务 | `/health` 正常；MPS；CustomVoice 和 Base 当前未加载 |
| `127.0.0.1:8000` | SillyTavern | 进程运行 |
| `127.0.0.1:8787` | Hermes WebUI | 进程运行 |
| `127.0.0.1:8765` | 本地静态 HTTP 服务 | 运行中，具体归属待确认 |
| `127.0.0.1:19825` | Node 服务 | 运行中，具体归属待确认 |

## 文本与视觉语言模型

### GGUF：`~/llm-models`，当前目录约 100 GiB

| 模型 | 量化/用途 | 文件大小 |
|---|---|---:|
| Qwen3.6 35B-A3B Uncensored Heretic | Q4_K_M，文本 MoE | 19.8 GiB |
| Qwen3 30B-A3B Abliterated | Q4_K_M，文本 MoE | 17.3 GiB |
| Qwen3.6 27B Fable Fusion | IQ3_M，文本 | 13.1 GiB |
| Qwen2.5-VL 7B NSFW Caption V3 | Q5_K_M，多模态 | 5.1 GiB |
| Qwen2.5-VL mmproj | F16，视觉投影 | 1.3 GiB |
| Qwen3.6 35B mmproj | F16 | 858 MiB |
| Gemma 4 12B uncensored | Q5_K_M，文本/图像/音频 | 8.0 GiB |
| Gemma 4 12B mmproj | BF16，多模态投影 | 167 MiB |
| Qwythos 9B v2 | Q6_K，文本/图像 | 6.9 GiB |
| Qwythos 9B v2 mmproj | BF16，多模态投影 | 879 MiB |
| MN-VelvetCafe-RP-12B-V2 | Q5_K_M，SillyTavern角色扮演 | 8.1 GiB |
| Qwen3.8 27B 官方版 | Q4_K_M，文本/图像/视频，Agent候选 | 18.97 GB |
| Qwen3.8 27B mmproj | Q8_0，多模态投影 | 629 MB |

`llama-server` 配置已登记 Qwen3 30B、Qwen3.6 27B 和 Qwen3.6 35B。2026-08-15起，27B生产配置改为单槽65536上下文，只供SillyTavern使用；Hermes继续使用云端模型。原双槽131072配置仅保留为历史评测证据。

2026-08-15新增三套外部候选实测。VelvetCafe 12B V2虽能在64K长历史后与现有7B视觉共存，合计RSS约21.2GiB、系统可用内存约14%、swap无新增，但人工复核发现停止后自行恢复，长篇同题只写579字且文风弱于27B，Agent工具调用也失败，因此不替换当前27B。Gemma 4 12B仅保留为自带视觉的一体化备用；Qwythos 9B退出默认。

同日新增官方Qwen3.8-27B Q4_K_M与Q8视觉投影。它在本机单槽64K成功加载，16K回忆4/4、视觉识别通过，三步标准工具调用完整通过；但同题长篇只写854中文字，普通角色立场门禁失败，因此只列为本地Agent/一体化多模态研究候选，不进入SillyTavern生产路由。测试结果位于`results/qwen38_20260815/`。

### MLX：约 28.7 GiB

| 模型 | 架构 | 量化 | 文件夹大小 |
|---|---|---|---:|
| Cydonia 24B v3.1 | Mistral | 4-bit | 12 GiB |
| Josiefied Qwen3 14B Abliterated v3 | Qwen3 | 4-bit | 8.6 GiB |
| EVA Qwen2.5 14B v0.2 | Qwen2 | 4-bit | 7.8 GiB |

三套模型均有完整 `config.json` 和分片权重；尚未通过本项目的统一生成基准。

## 图像工具与模型

### ComfyUI

- 路径：`~/ComfyUI`
- Git：`v0.31.0-11-g34744cd-dirty`，commit `34744cd`（2026-08-10）
- 模型目录：约 59 GiB
- 自定义节点：约 597 MiB
- 输出：约 264 MiB
- 当前没有监听 8188，视为未运行。

主要生成模型：

| 模型 | 大小 |
|---|---:|
| JuggernautXL v9 | 6.6 GiB |
| RealVisXL v5 | 6.5 GiB |
| FLUX.1-dev Q4_K_S GGUF | 6.3 GiB |
| Realistic Vision v5.1 | 2.0 GiB |
| SDPose Wholebody | 1.8 GiB |

已发现控制与身份组件：ControlNet OpenPose/Scribble、InstantID、IPAdapter SD1.5/SDXL/FLUX、FaceID、InsightFace、InSwapper、人物/面部/手部检测、RMBG 1.4、4x-UltraSharp，以及多套本地 LoRA。

已启用自定义节点包括 ComfyUI-GGUF、IPAdapter Flux、IPAdapter Plus、InstantID、Impact Pack、ControlNet Aux。AppleSilicon FP8 节点和两个备份节点被明确禁用。

最近日志存在两类待处理问题：

1. 代理指向 `127.0.0.1:7892` 但无法连接，导致 SigLIP 配置下载/缓存解析失败；
2. FLUX IPAdapter 节点与当前 ComfyUI 对象接口不兼容：`DoubleStreamBlock` 缺少 `flipped_img_txt`。

### 桌面应用记录

Homebrew 留有 Comfy Desktop 1.0.28 和 Draw Things 1.20260518.2 的安装记录，但对应 Cask 目录为 0B，且 `/Applications` 与 `~/Applications` 未找到应用包。因此记录为“安装记录残留 / 当前不可确认可用”，不计入已验证工具。

## 语音与音频

### Qwen3-TTS

- 工具目录：`~/voice-tools`，合计约 13 GiB；
- 服务：FastAPI，MPS，监听 `127.0.0.1:9881`；
- 包：`qwen-tts 0.1.1`、PyTorch 2.12.1、Transformers 4.57.3；
- CustomVoice 1.7B 权重约 4.2 GiB；
- Base 1.7B 声音克隆权重约 4.2 GiB；
- 服务提供预设音色和参考音频克隆端点；克隆功能必须只使用有明确授权的成年人声音资产。

目录内还发现 Edge TTS、ChatTTS 脚本/样音、CosyVoice 源码与脚本、Fish Speech 源码，但未发现足以证明这些链路已经可运行的健康服务或完整权重。

### ASR

- `faster-whisper 1.2.1` 已安装；
- `openai-whisper 20250625` 已安装；
- Hugging Face 缓存中有 Systran faster-whisper-base，约 141 MiB；
- 尚未做中文 CER、实时系数和时间戳验证。

## 前端与编排

- SillyTavern：`1.18.0-dirty`，约 762 MiB，当前运行；
- Hermes Agent：`0.18.2`，`~/.hermes` 约 7.5 GiB；Hermes WebUI 当前运行；
- Open WebUI：`0.9.6`，安装在 `~/voice-tools/open-webui-venv`，当前未发现运行进程；
- VRoid Studio：应用存在，可作为角色建模工具，但尚未与生成链路联调。

## 未发现

- Ollama；
- Docker / Podman 命令；
- LM Studio；
- 当前可确认存在的 Comfy Desktop / Draw Things 应用包；
- 可直接判定为完整可运行的视频生成模型；
- 已验证的 MuseTalk、LivePortrait 或 Wav2Lip 数字人口型链路。

## 下一轮验证优先级

1. 继续搜索12B–24B SillyTavern候选；每个候选先过1200–1600字长篇、人工文风盲评和撤回同意整段审计，再考虑下载更多量化。
2. Qwen3.8-27B进入本地Agent下一轮，跑Hermes真实长程任务和多轮工具异常恢复；在此之前不替换云端Agent。
3. 用同一文本测试集跑三套 MLX 模型，与 GGUF 后端横向比较。
4. 修复 ComfyUI 的代理配置和 FLUX IPAdapter 节点兼容性后，分别验证 SDXL、FLUX、InstantID。
5. 对 Qwen3-TTS 的预设音色和授权克隆样本测试首包延迟、实时系数与长文本稳定性。
6. 验证 faster-whisper-base 中文转写；再决定是否需要更大 ASR 模型。
7. 盘点视频与数字人缺口后再选模型，避免在当前 32 GB 无风扇设备上盲目下载大型视频权重。
