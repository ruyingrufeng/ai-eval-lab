# 本地内容工具与模型实验室

本仓库只负责本地内容生产基础设施，不负责生产或保存具体内容。

它的职责是：

- 调研并登记候选工具、模型、许可证和硬件要求；
- 安装、升级、回滚和隔离运行环境；
- 对文本、图像、语音、视频、小说辅助与数字人链路做可重复测试；
- 保存基准结果、测试样本定义和选型结论；
- 向外部内容生产项目提供稳定的本地 API、工作流及模型清单。

成人尺度是一个“能力与边界测试维度”，不是本仓库的生产内容。测试资产必须是合成资产或有明确授权的成年人资产；禁止未成年人、年龄不明、非自愿内容和未经授权的真人身份/声音复刻。

## 当前机器基线

- MacBook Air，Apple M5（10 核 CPU / 10 核 GPU）
- 32 GB 统一内存
- macOS 26.5
- 工作盘可用空间约 242 GiB（2026-08-12）
- 已发现：Git、Python 3、Node.js、npm、FFmpeg
- 未发现：Docker、Ollama

运行基线探测：

```bash
./scripts/probe-host.sh
```

结果写入 `results/host/`，该目录默认不提交。

## 当前生产路由（2026-08-30 核验）

- 文本统一入口为 `127.0.0.1:8086` 的 llama-server，单模型按需加载：`qwen3.6-27b-fable` 供 SillyTavern，`qwen3.8-27b-ridge` 供 Hermes `jianguo`，也是当前 dsh 通用配置默认；本地 `glm4.7-flash` 因 Agent 有效上下文不足，已从活动路由移除并删除权重。
- Hermes root、awei、blogger 默认使用智谱云端 `glm-4.7-flash`（200K 上下文、16K 最大输出），容量不足时依次回退 Agnes 2.5 Flash、DeepSeek V4 Flash；Hermes WebUI 运行于 `127.0.0.1:8787`。
- 语音当前实验入口为 `127.0.0.1:9893` 的 Qwen3-TTS-1.7B CustomVoice MLX，手动按需启动；2026-08-31 复测确认服务稳定但长文内容保真失败，状态保持 `runnable`，旧 `9883` plist 不再作为有效入口。
- 视觉 `8087` 与 ComfyUI `8188` 都按需启动，不要求与大型文本模型常驻并行。

当前运行态与下一阶段见 [docs/HANDOFF_20260831_2345.md](docs/HANDOFF_20260831_2345.md)。

安装并验证 MLX 文本后端：

```bash
./scripts/setup-mlx-lm.sh
./scripts/benchmark-mlx-lm.sh MODEL_ID
```

模型 ID 必须先登记到 `registry/candidates.yaml`；脚本的输出写入 `results/text/`。

## 目录

```text
docs/               范围、架构、测试与验收规范
registry/           候选工具与模型登记表
benchmarks/         测试用例定义（不含生产内容）
scripts/            安装、探测和基准脚本
results/            本机测试结果（默认忽略）
```

## 第一阶段路线

1. 冻结硬件与软件基线。
2. 验证 MLX、llama.cpp 两种文本推理后端。
3. 用统一测试集对 7B–14B 量级中文模型做质量、速度、内存和稳定性比较。
4. 验证 ComfyUI 在 Apple Silicon 上的安装与 API，并测试轻量图像模型。
5. 验证 MLX Whisper / MLX Audio 的 ASR、TTS 与授权语音链路。
6. 视频与数字人只在前述链路稳定后试装；独立记录耗时、峰值内存和可用性。

详细标准见 [docs/TESTING.md](docs/TESTING.md)，候选清单见 [registry/candidates.yaml](registry/candidates.yaml)。

本机已有工具和模型的只读盘点见 [docs/LOCAL_INVENTORY.md](docs/LOCAL_INVENTORY.md)，机器可读清单见 [registry/installed.yaml](registry/installed.yaml)。

本机真实内容生产项目中沉淀的工具用法、对照实验和问题复盘见 [docs/PROJECT_EVIDENCE.md](docs/PROJECT_EVIDENCE.md)，机器可读结论见 [registry/project_evidence.yaml](registry/project_evidence.yaml)。

RealVisXL V5 与 Flux.1-dev Q4 的 2026-08-12 中性统一基准复测见 [docs/IMAGE_RETEST_20260812.md](docs/IMAGE_RETEST_20260812.md)。

针对文章、图片、视频、小说和数字人资产的分类型选型见 [docs/CONTENT_TYPE_SELECTION.md](docs/CONTENT_TYPE_SELECTION.md)，机器可读能力矩阵见 [registry/content_type_matrix.yaml](registry/content_type_matrix.yaml)。

对应的分类型验收指标见 [benchmarks/content_type_test_plan.yaml](benchmarks/content_type_test_plan.yaml)。

语言模型按三条真实业务 Agent 工作流评测：内容增长闭环、研究到决策闭环、访谈到洞察闭环。代码与数据计算作为执行工具，PPT、网页和报告作为交付形式，不再拆成大量零散场景，也不计算笼统总分。计划见 [docs/AGENT_BUSINESS_EVALUATION_PLAN_20260814.md](docs/AGENT_BUSINESS_EVALUATION_PLAN_20260814.md)，基准矩阵见 [benchmarks/agent_scenarios.yaml](benchmarks/agent_scenarios.yaml)。此前三道技术沙盒题只作为 [Agent 工具链冒烟](docs/AGENT_LLM_EVALUATION_20260814.md)。

首批一小时“内容增长闭环”的固定资料、阶段和验收项见 [benchmarks/agent_business_first_batch.yaml](benchmarks/agent_business_first_batch.yaml)。

内容增长闭环 Agent 首测已止损：27B首次与恢复均600秒超时且产物不完整；30B/35B虽在180秒内生成全部文件，但没有正常退出。完整自主管理的本地 Hermes 路线不进入推荐；Hermes继续使用云端模型。27B双64K并发结果只作为历史评测证据。见 [双槽专项HTML](docs/reports/dual_slot_27b_evaluation_20260814/report.html) 与 [业务Agent总报告](docs/reports/business_agent_evaluation_20260814/report.html)。

35B单槽短任务虽然快，但进程RSS约21.2GiB，用户实盘确认无法再可靠加载7B视觉模型，不适合Hermes长上下文和多轮工具调用。当前本地文本路由只保留27B单槽64K给SillyTavern；30B、35B均不进入Hermes。历史性能对照见 [35B/27B受控业务对照](docs/reports/controlled_business_model_comparison_20260814/report.html)。

2026-08-15新增官方Qwen3.8-27B Q4实测并完成与Fable的52轮复核：64K加载、16K回忆、自带视觉与标准工具调用通过；复核证明它能稳定产出千字以上内容，普通/成人短轮还明显长于Fable，因此撤回“不适合SillyTavern”的过早表述。当前更准确的定位是“适合ST但暂不替换Fable”：Fable文笔、角色声音、长度纪律和速度更好，3.8更长且规则修正有亮点，但波动、戏剧化补设定和完整耗时更高。报告见`docs/reports/qwen36_vs_qwen38_st_20260815/report.html`，原始结果见`results/qwen36_vs_qwen38_st_20260815/`。

业务Agent正式HTML报告见 [docs/reports/business_agent_evaluation_20260814/report.html](docs/reports/business_agent_evaluation_20260814/report.html)。

SillyTavern 五轮中性成年角色基线已完成：35B调参档质量最好，但受32GB内存限制退出实际路由；30B退出。当前实际本地配置为27B单槽64K，仅供SillyTavern；它此前普通角色质量未过门槛，仍需按新单槽配置复测长上下文、世界书和跨会话状态。见 [docs/SILLYTAVERN_MODEL_EVALUATION_20260814.md](docs/SILLYTAVERN_MODEL_EVALUATION_20260814.md)。

SillyTavern 直白成人内容专项也已完成：在虚构、明确成年、双方自愿的四轮具体性行为测试中，35B调参档综合最好；27B更直白但慢且存在节奏矛盾，30B Abliterated 自动降尺度而失败。敏感原文只留在被 Git 排除的本地结果目录。见 [docs/SILLYTAVERN_ADULT_EXPLICIT_EVALUATION_20260814.md](docs/SILLYTAVERN_ADULT_EXPLICIT_EVALUATION_20260814.md)。

35B成人12轮连续性续测显示：关键状态和同意控制通过，但长度控制及一项局部动作指令失败；末轮只有约1,800 tokens，16K/32K仍待正式验证。见 [docs/SILLYTAVERN_ADULT_CONTINUITY_EVALUATION_20260814.md](docs/SILLYTAVERN_ADULT_CONTINUITY_EVALUATION_20260814.md)。

以上三轮SillyTavern测试的统一HTML主报告见 [docs/reports/sillytavern_evaluation_20260814/report.html](docs/reports/sillytavern_evaluation_20260814/report.html)。从2026-08-14起，后续正式评测默认输出自包含HTML；Markdown只作为源材料或方法附件。

2026-08-15已从当前模型仓库新下载并实测三套适合32GB机器的候选。人工复核与同题长篇补测后，没有一套足以替换当前27B：VelvetCafe虽能与7B视觉共存，但出现停止后自行恢复、长篇提前收尾和Agent伪造执行；Gemma 4仅保留一体化多模态备选；Qwythos退出默认。完整修正版报告见 [docs/reports/local_model_discovery_20260815/report.html](docs/reports/local_model_discovery_20260815/report.html)。

性能、统一内存资源采样、队列并发和跨服务共存测试规范见 [docs/PERFORMANCE_CONCURRENCY.md](docs/PERFORMANCE_CONCURRENCY.md)。

人物图片的人脸颜值与自然度、身材比例、服装搭配和商业成片感评测见 [docs/IMAGE_AESTHETIC_EVALUATION.md](docs/IMAGE_AESTHETIC_EVALUATION.md)。

并行等级和当前性能证据见 [benchmarks/performance_matrix.yaml](benchmarks/performance_matrix.yaml)；系统资源采样工具为 [scripts/sample-macos-resources.sh](scripts/sample-macos-resources.sh)。

本轮 C1、27B 资源预检和审美联合结果见 [docs/PERFORMANCE_AESTHETIC_RETEST_20260812.md](docs/PERFORMANCE_AESTHETIC_RETEST_20260812.md)，接替入口见 [docs/HANDOFF_20260812_1216.md](docs/HANDOFF_20260812_1216.md)。

当前图片生产采用 Flux 双档工作流：默认 `fast` 使用 FLUX.1-schnell Q4、4 步；显式 `quality` 使用 FLUX.1-dev Q4、20 步。复杂物件和最终成片默认走 `quality`。RealVisXL 已退出默认工作流，但模型文件、工作流构建器和历史评测脚本继续保留，用于故障回退、对照测试和结果复现。精确指定身份不属于这套通用本地 Flux 默认链。完整决策见 [docs/DECISIONS.md](docs/DECISIONS.md)。

默认生成入口：

```bash
# 快速档（默认）
python scripts/run-flux.py "your prompt" --output /absolute/path/fast.png

# 精修档
python scripts/run-flux.py "your prompt" --mode quality --output /absolute/path/quality.png
```

Flux 全身像默认使用强化构图提示词；OpenPose ControlNet 已安装并验证，但只作为精确姿态/站位控制的可选模块，不进入默认生成链。首轮 6 图评测见 `results/aesthetic/20260813-flux-fullbody-methods/report.html`。

最新任务交接见 [docs/HANDOFF_20260831_2345.md](docs/HANDOFF_20260831_2345.md)：本地 GLM-4.7-Flash 已退出活动路由，约 17GB 权重与专用 preset 已移入废纸篓；8086 仅保留 Fable 与 Ridge，dsh 默认为 Ridge。历史评测报告继续保留。Qwen3.8 dsh Agent v8 历史终局保留在 [docs/HANDOFF_20260818_2145.md](docs/HANDOFF_20260818_2145.md)。

阶段目标回顾与下一阶段计划见 [docs/PHASE_SUMMARY_20260814.md](docs/PHASE_SUMMARY_20260814.md)。

锁脸专项已完成并止损：高质量正脸/3/4/侧脸母版有效，但 Flux IP-Adapter 无法兼顾指定身份与全身；普通 Flux 底图 + InSwapper 在全身小脸上视觉 0/3。精确身份改走训练型角色 LoRA 或在线身份编辑。最终报告见 `docs/FLUX_TWO_STAGE_IDENTITY_EVALUATION_20260814.md`。

工具和模型不是一次性选型：持续发现、周检、月度深度复核和触发式更新规则见 [docs/CONTINUOUS_DISCOVERY.md](docs/CONTINUOUS_DISCOVERY.md)，检查历史登记在 [registry/discovery_log.yaml](registry/discovery_log.yaml)。

iCloud 共享记忆库对工具历史、交接结论及当前实盘冲突的审计见 [docs/SHARED_MEMORY_AUDIT.md](docs/SHARED_MEMORY_AUDIT.md)，带原记录时间、最近核验时间和入库时间的机器索引见 [registry/shared_memory_evidence.yaml](registry/shared_memory_evidence.yaml)。
