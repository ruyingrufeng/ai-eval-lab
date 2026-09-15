# AI Eval Lab

> 本地化、可复现、体系化的 AI 模型与工具评测实验室。

**AI Eval Lab** 是一套在 Apple Silicon Mac 上构建本地 AI 内容生产基础设施的方法论、脚本和基准测试集合。它不生产具体内容，而是帮你回答：**在我的机器上，哪个模型最快、最准、最稳？**

## 为什么需要这个？

网上的模型评测满天飞，但：
- 大多是在 NVIDIA GPU 上测的，Apple Silicon 数据极少
- 跑分和真实业务场景是两回事
- 没有统一的测试方法，结果不可比
- 测了一堆，最后不知道该用哪个

AI Eval Lab 用**真实业务闭环**做评测——不是"这个模型能跑多少 token/s"，而是"它能不能完整跑完一个内容生产任务、质量如何、要花多久、吃多少内存"。

## 它能做什么

- 🧪 **文本模型评测**：质量、速度、内存、长上下文、Agent 工具调用、角色扮演
- 🎨 **图像模型评测**：Flux / SDXL 速度对比、审美评估、身份一致性测试
- 🎙️ **语音链路评测**：TTS 音质/速度对比、ASR 准确率、多角色声音克隆
- 🎬 **视频与数字人**：端到端管线验证（低算力机器优先测可行性）
- 📊 **性能矩阵**：并发等级、内存占用、热降频、多服务共存
- 🔄 **持续发现**：新模型自动纳入评测池，定期复核选型结论

## 项目结构

```
ai-eval-lab/
├── docs/                # 架构、测试规范、决策记录、评测报告
│   ├── ARCHITECTURE.md      # 技术架构与分层原则
│   ├── TESTING.md           # 测试方法论与验收标准
│   ├── DECISIONS.md         # 关键选型决策记录
│   ├── CONTINUOUS_DISCOVERY.md  # 持续发现与复核机制
│   └── reports/             # 历次正式评测报告（HTML）
├── registry/            # 模型与工具注册表（机器可读）
│   ├── candidates.yaml      # 候选清单与状态
│   ├── content_type_matrix.yaml  # 分内容类型能力矩阵
│   └── discovery_log.yaml   # 持续发现日志
├── benchmarks/          # 测试用例定义（不含生产内容）
│   ├── agent_scenarios.yaml   # Agent 业务场景
│   ├── performance_matrix.yaml  # 性能并发矩阵
│   └── text/  image/  tts/   # 各模态测试集
├── scripts/             # 安装、探测、基准测试脚本
│   ├── probe-host.sh        # 机器基线探测
│   ├── setup-mlx-lm.sh      # MLX 环境搭建
│   ├── benchmark-*.py       # 各类基准测试
│   └── build-*-report.py    # 报告生成器
└── results/             # 本机测试结果（默认忽略，不提交）
```

## 快速开始

### 1. 探测你的机器基线

```bash
./scripts/probe-host.sh
```

结果写入 `results/host/`，帮你确认硬件、系统、已装工具的基线状态。

### 2. 跑一个文本模型基准

```bash
# 先搭建 MLX 环境
./scripts/setup-mlx-lm.sh

# 跑指定模型的基准
./scripts/benchmark-mlx-lm.sh MODEL_ID
```

### 3. 跑 Flux 图像速度测试

```bash
python scripts/benchmark-flux-speed.py --model flux-1-schnell-q4
```

### 4. 查看已有报告

所有正式评测报告在 `docs/reports/` 目录下，均为自包含 HTML，直接浏览器打开即可。

已完成的代表性评测：
- [业务 Agent 评测（文本）](docs/reports/business_agent_evaluation_20260814/report.html)
- [TTS 中英文基准（语音）](docs/reports/tts_asr_bench_20260816/report.html)
- [Fish Speech S2 Pro 声音克隆](docs/reports/fish_s2_pro_mlx_20260903/report.html)

## 核心理念

### 1. 结论必须基于实测
文档里说支持的不算，跑通了才算。每个模型/工具都有状态：
`candidate` → `installable` → `runnable` → `verified`

### 2. 用真实业务场景评测
不做"三道技术题定胜负"的纸面评测。我们测的是：
- 内容增长闭环（选题 → 写作 → 排版 → 发布）
- 研究到决策闭环（检索 → 分析 → 建议 → 报告）
- 访谈到洞察闭环（转录 → 摘要 → 聚类 → 洞察）

### 3. 环境隔离
每类工具独立虚拟环境，避免依赖互相污染。模型权重放在仓库外，只存 ID 和配置。

### 4. 持续发现，定期复核
选型不是一次性的。新模型出来就纳入评测，已选模型定期复核，过时就淘汰。

## 硬件参考基线

本项目的初始验证基于以下配置：
- **MacBook Air M5**（10 核 CPU / 10 核 GPU）
- **32 GB** 统一内存
- **macOS 26+**

你可以在自己的机器上跑同样的测试，得到你的专属选型结论。

## 文档索引

| 主题 | 文档 |
|------|------|
| 技术架构 | [docs/ARCHITECTURE.md](docs/ARCHITECTURE.md) |
| 测试方法论 | [docs/TESTING.md](docs/TESTING.md) |
| 选型决策记录 | [docs/DECISIONS.md](docs/DECISIONS.md) |
| 持续发现机制 | [docs/CONTINUOUS_DISCOVERY.md](docs/CONTINUOUS_DISCOVERY.md) |
| 性能与并发 | [docs/PERFORMANCE_CONCURRENCY.md](docs/PERFORMANCE_CONCURRENCY.md) |
| 分类型选型指南 | [docs/CONTENT_TYPE_SELECTION.md](docs/CONTENT_TYPE_SELECTION.md) |
| Agent 业务评测计划 | [docs/AGENT_BUSINESS_EVALUATION_PLAN_20260814.md](docs/AGENT_BUSINESS_EVALUATION_PLAN_20260814.md) |
| 图像审美评测标准 | [docs/IMAGE_AESTHETIC_EVALUATION.md](docs/IMAGE_AESTHETIC_EVALUATION.md) |

## 路线图

- [x] 第一阶段：冻结基线 + 文本/图像/语音链路验证
- [x] 第二阶段：业务 Agent 闭环评测 + 持续发现机制
- [ ] 第三阶段：视频与数字人管线稳定化
- [ ] 第四阶段：跨机器结果对比与排行榜

## 许可证

MIT License — 随便用，保留版权声明就行。

---

如果这个项目对你有帮助，欢迎 Star ⭐，也欢迎提交你自己机器上的测试结果。
