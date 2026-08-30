# Flux 速度优化评测（2026-08-13）

## 范围

本轮只评测本机 FLUX.1-dev Q4_K_S 的推理速度，不扩展产品图、复杂场景、局部编辑和文字排版能力。测试固定提示词、种子、Euler/simple 采样器，并在 Apple M5 / 32 GB、ComfyUI 0.31.0、PyTorch 2.14 nightly、MPS 环境执行。

## 结果

| 配置 | 耗时 | 相对基线 | 质量判断 |
|---|---:|---:|---|
| 20 步，768×1024，默认 attention | 350.87 秒 | 基线 | 可交付 |
| 12 步，768×1024 | 251.29 秒 | 快 28.4% | 明显发虚 |
| 8 步，768×1024 | 174.49 秒 | 快 50.3% | 不可交付 |
| 12 步，640×896 | 228.97 秒 | 比同为 12 步快 8.9% | 单张偶然清晰，构图改变 |
| 20 步，split attention | 471.77 秒 | 慢 34.5% | 无质量收益 |

## 决策

1. 生产默认保持 20 步、768×1024、默认 sub-quadratic attention。
2. 8 步可作为构图草稿档，但不得用于成片或模型质量评测。
3. 不启用 `--use-split-cross-attention`。
4. ComfyUI 使用默认 RAM pressure cache；不再把 `--cache-none` 放入常规启动命令。
5. FLUX.1-dev 继续减步不是有效方向。下一轮应评测原生少步蒸馏模型 FLUX.1-schnell（1–4 步），并与当前 20 步基线做速度、提示遵循和人像细节横评。

## 证据路径

- 可视化报告：`results/performance/flux-speed-20260813/report.html`
- 默认 attention 原始计时：`results/performance/flux-speed-default-20260813/report.json`
- split attention 原始计时：`results/performance/flux-speed-split-20260813/report.json`
- 可复跑脚本：`scripts/benchmark-flux-speed.py`

## 研究依据

- ComfyUI 官方在 macOS 使用 MPS 后端，本机也已确认 MPS 可用。
- ComfyUI 官方 Flux 示例将 Schnell 定义为蒸馏 4 步模型，适合下一轮低步数横评。
- Black Forest Labs 官方说明 FLUX.1-schnell 可在 1–4 步生成，且为 Apache 2.0；这比强行压低 FLUX.1-dev 步数更符合模型设计。
- MFLUX 是 Apple Silicon 原生 MLX 实现，可作为后续“更换推理后端”候选，但属于新后端验证，不应和本轮 ComfyUI 参数调优混为一项。
