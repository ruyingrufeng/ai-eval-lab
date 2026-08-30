# Flux 全身底图 + 本地换脸两阶段评测（2026-08-14）

## 【结论】

“普通 Flux 全身底图 + 本地 InSwapper 128 身份替换”未通过，当前本地通用参考图身份链应停止。

- 普通 Flux 底图完整全身 2/2，但视觉可用仅 1/2；seed 31415 整体严重虚焦。
- 正脸母版换脸相似度只有 0.1075、0.1186，远低于 0.35。
- 3/4 母版匹配 3/4 底图后，相似度仍只有 0.0774。
- 三个换脸输出均出现明显五官拉伸、表情异常或脸部拼接感，视觉通过 0/3。
- 可用底图 seed 27182 在换脸前对三母版平均相似度 0.1442；角度匹配换脸后反而降至 0.1294。

InSwapper 可以快速执行，但不适合当前 768×1024 全身小脸场景。

## 底图结果

| Seed | 耗时 | 全身 | 视觉质量 | 备注 |
|---:|---:|---|---|---|
| 31415 | 294.70 秒 | 通过 | 失败 | 全图虚焦，Laplacian 方差 2.79 |
| 27182 | 372.06 秒 | 通过 | 通过 | 清晰、完整全身，Laplacian 方差 82.22 |

Seed 31415 底图：

![Base 31415](/Users/jacky/Documents/ChatGPT/内容工厂管理/results/performance/flux-two-stage-identity-20260814/base/seed_31415.png)

Seed 27182 底图：

![Base 27182](/Users/jacky/Documents/ChatGPT/内容工厂管理/results/performance/flux-two-stage-identity-20260814/base/seed_27182.png)

## 换脸结果

| 目标 | 身份参考 | 对参考相似度 | 三母版平均 | 视觉 |
|---|---|---:|---:|---|
| 31415 | 正脸 | 0.1075 | 0.0726 | 失败 |
| 27182 | 正脸 | 0.1186 | 0.0692 | 失败 |
| 27182 | 3/4 角度匹配 | 0.0774 | 0.1294 | 失败 |

正脸换脸 seed 27182：

![Frontal swap 27182](/Users/jacky/Documents/ChatGPT/内容工厂管理/results/performance/flux-two-stage-identity-20260814/swapped/seed_27182.png)

角度匹配换脸 seed 27182：

![Angle-matched swap 27182](/Users/jacky/Documents/ChatGPT/内容工厂管理/results/performance/flux-two-stage-identity-20260814/swapped_angle_matched/seed_27182.png)

## 【风险】

- 768×1024 全身图中人脸太小，InSwapper 128 的有效细节不足。
- 单独放大脸再换回去已在历史测试中验证过，未形成稳定改善，不应重复投入。
- 身份相似度和视觉质量同时失败；不能因脚本运行成功而标记为可用。
- 资源不是瓶颈：本轮最低空闲内存 58%，swap 净下降 88 MiB。失败来自方法能力边界。

## 【方案】

- 本地 Flux 继续负责普通图片、全身构图、候选和高质量通用成片。
- Flux IP-Adapter 只用于“相近角色”或肖像，不宣称同一身份。
- InSwapper 128 不用于全身小脸。
- 精确指定身份改用训练型角色 LoRA，或直接交给已能稳定处理身份编辑的在线模型。
- 三张高质量母版保留，作为未来 LoRA/在线编辑的统一验收集。

## 【下一步】

图片主线至此冻结。按照阶段计划，下一项应转入 P1：现有本地文章/小说模型统一基准，或 Qwen3-TTS 正式速度与稳定性基准；不再继续扩展本地通用锁脸实验。

机器记录：`results/performance/flux-two-stage-identity-20260814/evaluation_report.json`。
