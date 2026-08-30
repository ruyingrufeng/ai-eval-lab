# 技术架构

## 原则

- Apple Silicon 原生优先：先测 MLX / Metal，再测通用后端。
- 后端与模型解耦：同一模型尽量能通过统一 API 被替换。
- 环境隔离：每类工具使用独立虚拟环境，避免 ComfyUI、音频和语言模型依赖互相污染。
- 模型与代码分离：权重放在仓库外的统一模型目录；仓库只保存模型 ID、哈希和配置。
- 结论基于实测：文档兼容只标记为 `candidate`，通过本机测试后才能标记为 `verified`。

## 建议分层

| 层 | 首选 | 备选 | 说明 |
|---|---|---|---|
| 文本原生后端 | MLX / mlx-lm | llama.cpp | MLX 适合本机；GGUF 生态由 llama.cpp 补齐 |
| 文本服务 | mlx-lm server | llama-server | 统一验证 OpenAI 风格接口 |
| 图像控制面 | ComfyUI | 原生 Diffusers 脚本 | 工作流图与 API 便于复现 |
| 图像生成模型 | Flux.1-dev Q4 GGUF | RealVisXL V5（保留非默认） | Flux 为生产默认；RealVisXL 模型和脚本只作回退、对照与历史复现 |
| ASR | mlx-whisper | whisper.cpp | 中文准确率、时间戳与实时率实测 |
| TTS/语音 | mlx-audio | Kokoro MLX | 声音克隆必须有授权测试资产 |
| 视频 | ComfyUI 视频节点 | 独立参考实现 | 32 GB 无风扇机器先测低分辨率短片 |
| 数字人 | 待验证 | 待验证 | CUDA 偏重项目不得仅凭“可安装”入选 |
| 媒体处理 | FFmpeg | — | 已安装，作为统一转码与探测工具 |

## 资源约束

32 GB 统一内存需要同时容纳系统、模型、KV cache 和运行时。首轮文本模型以 7B–14B 的 4-bit/5-bit 量化为主；图像先测轻量或量化版本。大型视频模型即使能够启动，也可能因速度、热降频或内存压力不具备生产可用性，因此必须单独设置通过阈值。
