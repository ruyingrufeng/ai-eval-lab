# 来源与复现说明

- 主报告：`report.html`，由同目录 `artifact.json` 生成；指标表和结论不另维护一份手写数据。
- 生成入口：`python3 scripts/build-fish-s2-report.py`，使用通用 `scripts/render-evaluation-record.py` 封装。
- 原始证据：`results/fish_s2_pro_mlx_20260903/`（Git 排除）。复制时已逐文件 SHA-256 对照源目录，见 `archive-manifest.json`。
- 源部署：`/Users/jacky/Documents/Codex/2026-09-03/referenced-chatgpt-conversation-this-is-an/outputs/fish-s2-local`。
- 部署发生于本任务前一阶段；本阶段只归档已有证据与用户试听反馈，没有重新跑推理或修改服务配置。
- 用户反馈为 2026-09-03 当前任务消息“效果还不错。”，时间精度为日。该反馈是整体试听认可，不虚构评分或声纹认证。
- HTML / artifact 不嵌入测试台词、音频或参考声音。权重、虚拟环境与声音资产继续留在外部部署目录。
- 四关卡状态为 `runnable`。与项目 `docs/TESTING.md` 对照，长篇稳定性、并发/共存对照、完整资源采样与声音相似度评测仍有缺口。
- 当前报告是短句试用决策记录；不把主观认可、无崩溃或 ASR 单次回检等同于完整 `verified`。
- 归档检查：22 份复制证据 SHA-256 通过；YAML/JSON 可解析；HTML 内嵌 artifact 与外部 JSON 一致，无远程资源依赖。Browser 的本地 file URL 安全策略拒绝导航，未绕过；桌面/窄屏视觉检查未完成。
