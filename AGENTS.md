# 内容工厂管理 — 项目规则

本仓库是"本地内容工具与模型实验室"：只负责本地内容生产基础设施（工具/模型调研、安装、评测、决策记录），不生产或保存具体内容。

## 目录结构

```text
docs/        范围、架构、测试与验收规范、交接文档、阶段总结
registry/    候选工具与模型登记表（YAML）
benchmarks/  测试用例定义（不含生产内容）
scripts/     安装、探测、基准、报告生成脚本
results/     本机测试结果（默认 gitignore）
```

## 关键规范

- **评测四关卡**：`discovered → installable → runnable → verified`，只有 verified 进推荐栈。
- **报告格式**：正式评测以 `docs/reports/<id>/report.html` 自包含 HTML 为主报告（含 artifact.json）；Markdown 只作源材料/附件。
- **决策记录**：工具/模型选型结论必须写入 `docs/DECISIONS.md`（追加，不覆盖）。
- **交接纪律**：每个阶段结束写 `docs/HANDOFF_YYYYMMDD_HHMM.md`，更新 README 的交接指针。
- **敏感资产**：成人尺度测试只用合成/授权成年人资产，原文留在 Git 排除目录，不嵌入 HTML。
- **机器基线**：MacBook Air M5 / 32GB 统一内存——进程 RSS ≠ 系统内存，必须看 memory pressure/swap。

## 当前生产路由（2026-08-30 核验）

- 文本统一入口：8086 = llama-server（models-preset 单模型按需加载，谁调用加载谁），三路分工：
  - Qwen3.6-27B-Fable（IQ3_M，64K 单槽）→ SillyTavern 专用
  - Qwen3.8-27B-Ridge（3.7bpw，80K）→ Hermes `jianguo` 本地档；Hermes WebUI 直接运行于 8787
  - dsh 当前配置默认仍为 Qwen3.8-27B-Ridge；GLM-4.7-Flash（Q4_K_M，64K 硬上限）已于 2026-08-31 完成真实 dsh 评测，但任务仅 2/3、约 28K 槽位上下文失败，状态为 `runnable_not_verified`，不作为推荐默认
  - dsh 云端可切：Agnes / MiniMax-M3 / DeepSeek V4
- 语音：9893 = Qwen3-TTS-1.7B CustomVoice MLX（手动按需启动，2026-08-30 正在做长文本分段复测）；旧 9883 launchd 配置已失效，不再作为当前入口；GPT-SoVITS / CosyVoice 实验进程在 ~/Documents/doubao/tts-bench
- 视觉：8087 = Qwen2.5-VL-7B NSFW-Caption-V3（plist/脚本就绪，按需启动）
- 图像：8188 = ComfyUI + Flux dev/schnell Q4_K_S 双档（含 flux-ip-adapter），RealVisXL 仅回退对照
- 已退役：Gemma 4 12B（2026-08-28 删文件）、Qwen3-30B、Qwen3.6-35B

## 约定

- 路径含空格/中文时 shell 命令必须双引号包裹（本项目路径就是典型）。
- 改共享资源（CSS/JS/图片）立即加 cache buster（?v=）。
- 声明"已落盘/已上传"前必须 bind verify（ls/wc/head/cat/curl HEAD）。
- 批量移动/删除用户数据前：du 量化 + sample 验证 + 先 cp 后删。
