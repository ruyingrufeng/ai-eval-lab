# 阶段性总结：SillyTavern 本地模型选型定案，文本主线收口

## Executive Summary

- **ST 本地模型选型正式定案。** 经过合成角色 52 轮配对 + 真实媚雪角色卡 20 轮配对，杰哥 2026-08-15 拍板：**SillyTavern 继续使用 Qwen3.6-27B Fable 单槽 64K**，Qwen3.8-27B 官方 Q4 保留为备用但不替换。
- **Qwen3.8 的 Agent 路由正式关闭。** 单步工具调用与 16K 回忆通过，但真实长程多步任务实测失败（大参数截断 + 连续 10 轮死循环重试），本地模型做完整自主 Hermes Agent 路线不推荐，Hermes 继续云端 DeepSeek。
- **模型资产清理完成。** 删除 7 个已退役模型文件约 55G（35B/30B/VelvetCafe/Qwythos/scribble-bad），8087 视觉服务补 launchd 托管，退役脚本清理 9 个。llm-models 100G → 46G，系统可用 245G。

## 目标达成情况（文本模型线）

| 事项 | 状态 | 结论 |
|---|---|---|
| ST 模型最终选型 | ✅ 定案 | Fable 胜出（文笔克制、长度纪律、速度快 1.2–2.2×） |
| Qwen3.8 能力复核 | ✅ 完成 | 适合 ST 备用、长文写作；不进 Agent 路由 |
| Qwen3.8 长程 Agent | ✅ 实测失败并定性 | 参数截断 + 无失败自适应，R3–R12 死循环 |
| 本地 Agent 路线 | ✅ 收口 | 27B 超时、30B/35B 不退出、3.8 死循环——全部不推荐 |
| 8087 视觉托管 | ✅ 修复 | launchd plist + KeepAlive，重启不再丢失 |
| 模型资产瘦身 | ✅ 完成 | 删 55G，保留项清晰，待删项（25G）杰哥确认暂不动 |

## 本阶段最重要的结论

### ST 选型：Fable vs Qwen3.8 的最终判定

真实媚雪卡 + 15 条世界书、20 轮配对（普通 15 + 成年自愿连续性 5，配对种子）：

| 维度 | Fable | Qwen3.8 | 判定 |
|---|---|---|---|
| 普通轮均长/耗时 | 195.9 字 / 37.6s | 206.7 字 / 46.7s | Fable 更快 |
| 成年轮均长/耗时 | 104.8 字 / 25.3s | 255.4 字 / 56.3s | Fable 守纪律且快 |
| 文笔/角色声音 | 克制、潜台词好 | 文学感更强、场景渲染强 | 3.8 微胜 |
| 停止/重新同意 | 退出干脆 | 处理细腻 | 3.8 亮点 |
| 完成度 | 20/20 stop | 20/20 stop | 持平 |

综合：文笔 3.8 微胜，但 ST 交互体验（速度 + 长度纪律）Fable 胜出。**生产 8086 不变。**

### Agent 路由：本地模型全线不推荐

- 27B：600s 超时 + 产物不全（08-14）
- 30B/35B：能产出但不退出工具循环（08-14）
- Qwen3.8：单步通过，长程失败——大参数生成被 max_tokens 截断，且失败后 10 轮重试完全相同坏参数，从不自适应（08-15）
- 结论：**Hermes 保持云端 DeepSeek；本地模型只服务 SillyTavern 和专用写作。**

### 模型资产：55G 清理与保留清单

- **删除**：35B+mmproj（20.9G）、30B（17G）、VelvetCafe（8.1G）、Qwythos+mmproj（7.8G）、scribble-bad（1.3G）——均有明确决策依据
- **保留**：Fable（生产）、Qwen2.5-VL-7B（8087）、Qwen3.8（ST 备用）、Gemma 4（一体化备选）、Flux dev/schnell、RealVisXL（决策要求保留）
- **待删未删**（方案 2，杰哥确认暂不动，约 25G）：JuggernautXL、Realistic Vision、ipadapter 系列、instantid+insightface、SDXL controlnet

## 下一阶段计划

1. **ST 真实长会话验证（未做）**：Fable 在新单槽 64K 配置下的长上下文、世界书和跨会话状态复测——08-14 交接遗留，仍是待办。
2. **TTS / ASR 正式统一基准（P1 遗留）**：Qwen3-TTS 与 ASR 工具已发现，首包、实时系数、长文本、可懂度、授权隔离未测。
3. **程序化视频（P2 遗留）**：HyperFrames/Remotion/FFmpeg 有历史实证，项目内固定案例未跑。
4. **可选：方案 2 模型清理**（约 25G）随时可执行，等杰哥需要时再说。

## 局限与假设

- A/B 只测了媚雪一张真实角色卡；不排除其他角色卡下 3.8 表现不同的可能，但速度劣势是物理性的。
- 长程 Agent 测试用单任务（数据整理）验证；失败模式（截断+死循环）在工具参数大的场景下触发，小参数工具链未必同样失败，但"失败不自适应"是模型行为缺陷。
- 文笔判定含主观成分；杰哥拍板基于本轮 20 轮 + 前序 52 轮证据，非逐轮投票。

## 证据入口

- 最新交接：`docs/HANDOFF_20260815_1825.md`
- 决策日志：`docs/DECISIONS.md`（今日新增 3 条：A/B 复核、Agent 失败、模型清理）
- A/B 盲选报告：`docs/reports/realcard_ab_20260815/report.html`
- 原始结果：`results/realcard_ab_20260815/`（20 轮 × 2 模型）、`results/agent_longrun_20260815/`（12 轮全记录）
- 评测脚本：`scripts/benchmark-st-realcard-paired.py`、`scripts/benchmark-qwen38-agent-longrun.py`
- 前序对照：`docs/reports/qwen36_vs_qwen38_st_20260815/report.html`（52 轮合成角色配对）
- 系统侧：`models.ini`（preset 仅剩 fable）、`com.jacky.llama-vision.plist`（8087 托管）
