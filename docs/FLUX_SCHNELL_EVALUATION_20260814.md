# FLUX.1-schnell 速度与画质横评（2026-08-14）

## 结论

FLUX.1-schnell Q4_K_S 的 4 步平均耗时为 89.59 秒，FLUX.1-dev Q4_K_S 的 20 步平均耗时为 391.27 秒，Schnell 平均快 4.37 倍。Schnell 三个场景均生成成功，质量达到候选图和普通配图可用水平，但人像肤质自然度、复杂物件计数仍不如 Dev。

因此不做单一模型替换，建立两档工作流：

- 快速档：Schnell 4 步，用于构图探索、批量候选和普通环境配图。
- 精修档：Dev 20 步，用于最终人像、身份一致性、复杂物件约束和高质量成片。

## 计时

| 场景 | Dev 20 步 | Schnell 4 步 | Schnell 提速 |
|---|---:|---:|---:|
| 全身编辑人像 | 350.87 秒 | 79.43 秒 | 4.42× |
| 近景人脸 | 396.26 秒 | 99.53 秒 | 3.98× |
| 复杂宽景 | 426.67 秒 | 89.80 秒 | 4.75× |
| 平均 | 391.27 秒 | 89.59 秒 | 4.37× |

## 画质判断

- 全身编辑人像：Schnell 人物完整清晰，但多生成了一本打开的笔记本；Dev 对单本物件约束更准确。
- 近景人脸：Schnell 五官锐利，但皮肤更光滑、模型感略强；Dev 的肤质和光影更自然。
- 复杂宽景：两者都完成玻璃车站、蓝色列车、黄色外套、红色行李等约束，Schnell 的构图表现不落下风。

## 推荐参数

- Schnell：`flux1-schnell-Q4_K_S.gguf`，4 步，CFG 1.0，Euler，simple。
- Dev：`flux1-dev-Q4_K_S.gguf`，20 步，CFG 1.0，Euler，simple。
- ComfyUI：默认 RAM pressure cache、默认 sub-quadratic attention、关闭预览。

## 默认脚本

普通生成统一使用 `scripts/run-flux.py`：

```bash
# fast 是默认值
python scripts/run-flux.py "your prompt" --output /absolute/path/fast.png

# 最终成片
python scripts/run-flux.py "your prompt" --mode quality --output /absolute/path/quality.png
```

脚本也支持 `--dry-run` 输出工作流 JSON，不连接 ComfyUI；身份/IP-Adapter 构建器默认固定使用 `quality`。

## 证据

- 可视化报告：`results/performance/flux-schnell-eval-20260814/report.html`
- 原始计时和环境记录：`results/performance/flux-schnell-eval-20260814/report.json`
- 工作流和复跑脚本：`scripts/run-flux-schnell-eval.py`
- 模型：`/Users/jacky/ComfyUI/models/diffusion_models/flux1-schnell-Q4_K_S.gguf`
- 模型 SHA-256：`4fd16477b3a5296d0cf722c4b92a9fd7f30d09ac7495826e4465d8de9c9fd973`

## 许可与来源

该 GGUF 是 city96 对 Black Forest Labs FLUX.1-schnell 的直接转换，模型页标注 Apache-2.0。Black Forest Labs 官方模型卡说明 Schnell 是 1–4 步蒸馏模型。
