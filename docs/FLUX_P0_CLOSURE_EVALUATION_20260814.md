# Flux P0 图片链路封闭评测（2026-08-14）

## 【结论】

P0 图片链路通过，可作为默认本地图片工作流：`fast` 与 `quality` CLI 均端到端成功，Schnell 连续 10 张无崩溃、无 OOM，候选图视觉合格率 90%。

推荐流程为：

1. `fast`（FLUX.1-schnell Q4，4 步）批量生成候选；
2. 人工或规则筛选构图；
3. 最终人像使用 `quality`（FLUX.1-dev Q4，20 步）；
4. 如需继承候选人物或构图，必须把候选图作为参考图/结构控制输入，不能只复用 seed。

RealVisXL 继续从默认工作流移除，但保留模型文件与脚本。OpenPose ControlNet 不是“能否生成全身像”的必需依赖；本轮 10/10 均完整生成全身构图。只有在严格指定姿态或多人肢体关系时再启用。

## 测试配置

- 平台：Apple Silicon，32 GB 统一内存，MPS
- ComfyUI：默认 RAM pressure cache、默认 sub-quadratic attention、预览关闭
- 分辨率：768×1024
- Schnell：`flux1-schnell-Q4_K_S.gguf`，4 步，Euler / simple，CFG 1.0
- Dev：`flux1-dev-Q4_K_S.gguf`，20 步，Euler / simple，CFG 1.0
- 资源采样：10 秒一次，共 136 个样本

## 结果

| 指标 | 结果 | 判定 |
|---|---:|---|
| fast CLI 端到端 | 成功 | 通过 |
| quality CLI 端到端 | 成功 | 通过 |
| Schnell 连续生成 | 10/10 成功 | 通过 |
| Schnell 候选图合格率 | 9/10（90%） | 通过（门槛 80%） |
| Schnell 平均耗时 | 79.44 秒/张 | 可用 |
| Schnell p50 / p95 | 75.41 / 105.63 秒 | 长批次存在降速 |
| Dev 单张耗时 | 420.20 秒 | 仅用于最终图 |
| 严重内存压力 / OOM | 未出现 | 通过 |
| swap 变化 | -48 MiB | 无增长 |
| 同 seed 跨模型继承构图 | 仅粗粒度相似 | 不可靠 |

Schnell 单张耗时依次为：64.42、51.28、53.29、55.30、72.39、78.44、103.52、104.55、105.58、105.67 秒。前 5 张平均 59.34 秒，后 5 张平均 99.55 秒，后半程慢 67.8%。资源没有同步恶化，因此更可能是持续负载下的计算/温度波动，而不是内存泄漏。

资源最低空闲内存为 46%，结束时为 82%；swap 从 12,095.38 MiB 降至 12,047.38 MiB；ComfyUI RSS 峰值约 6,328.8 MiB。测试期间没有触发停止条件。

## 视觉验收

合格标准：完整全身、脸部无明显崩坏、手脚无明显畸形、构图可作为候选继续处理。910010 因鞋履缺失且脚部呈现异常判为不合格，其余 9 张作为候选可用。

候选样例：

![Schnell seed 910001](/Users/jacky/Documents/ChatGPT/内容工厂管理/results/performance/flux-p0-closure-20260814/fast/seed_910001.png)

不合格样例：

![Schnell seed 910010](/Users/jacky/Documents/ChatGPT/内容工厂管理/results/performance/flux-p0-closure-20260814/fast/seed_910010.png)

Schnell 的脸仍普遍偏光滑、理想化，适合筛选方向，不应被解读为最终人像质量已达标。Dev 的质感更好，但单张仍无法解决身份一致性；最终人像应继续使用参考图约束。

## 同 seed 候选→Dev 验证

Schnell 与 Dev 均使用 seed `910001`、同提示词、同分辨率。Dev 保留了“正面、居中、全身、浅色影棚”等粗粒度结构，但人物身份、发型、服装和细节构图均改变。

![Schnell seed 910001](/Users/jacky/Documents/ChatGPT/内容工厂管理/results/performance/flux-p0-closure-20260814/fast/seed_910001.png)

![Dev seed 910001](/Users/jacky/Documents/ChatGPT/内容工厂管理/results/performance/flux-p0-closure-20260814/quality/seed_910001.png)

结论：同 seed 只能作为可复现实验参数，不能作为跨模型的构图或身份传递机制。

## 【风险】

- 长批次后半程速度下降约 67.8%，容量规划不能只用首张或热身后的最快值。
- Schnell 候选脸偏 AI 化；人像最终成片仍需 Dev 和参考图约束。
- OpenPose 只能约束姿态，不解决脸部身份漂移。
- Dev 单张约 7 分钟，不适合用于大规模盲抽候选。

## 【方案】

- 默认 `fast` 用于候选与普通配图，默认容量按 p95 约 106 秒/张估算。
- `quality` 只对已筛选候选使用，预算按 7–8 分钟/张。
- 跨模型重做不再宣传“复用 seed 保构图”；改用参考图、IP-Adapter 或结构控制。
- 连续任务建议分批 5 张，并在批次间留出冷却/资源释放窗口；该建议仍需下一轮 A/B 验证。

## 【下一步】

下一项只验证一个高价值问题：候选图作为参考输入，是否能让 Dev 在提升质感的同时保留人物/构图。建议做 3 组对照（纯同 seed、参考图约束、参考图 + 姿态约束），预计 35–50 分钟。若参考图约束已经足够，则不把 OpenPose ControlNet 加入默认依赖。

机器可读数据见 `results/performance/flux-p0-closure-20260814/summary.json`，完整资源曲线见 `results/performance/flux-p0-closure-20260814/resources.jsonl`。
