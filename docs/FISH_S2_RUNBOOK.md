# Fish S2 本机验证与报告复现

本轮补测针对单模型进程长期驻留与三角色演绎，继续使用已隔离的 Python/MLX 和既有模型。不修改全局 Python，不更改默认模型或共享服务。

## 命令入口

在本项目目录执行。新实验必须使用新编号，启动器拒绝覆盖已运行任务。

```bash
FISH_PY="/Users/jacky/Documents/Codex/2026-09-03/referenced-chatgpt-conversation-this-is-an/outputs/fish-s2-local/.venv/bin/python"
FISH_RUN="fish_s2_persistent_$(date +%Y%m%d_%H%M%S)"
"$FISH_PY" scripts/fish-s2-persistent.py prepare "$FISH_RUN"
caffeinate -i "$FISH_PY" scripts/fish-s2-persistent.py run "$FISH_RUN"
# 仅在 status.json 为 fish_done 后执行：Fish 进程已退出，ASR 才加载。
"$FISH_PY" scripts/fish-s2-asr-batch.py "$FISH_RUN"
"$FISH_PY" scripts/analyze-fish-persistent.py "$FISH_RUN"
"$FISH_PY" scripts/build-fish-s2-followup-report.py --run-id "$FISH_RUN"
"$FISH_PY" scripts/build-fish-listening.py "$FISH_RUN"
```

核对 `results/<run>/status.json`、`progress.json`、`resources.jsonl`、`worker-result.json` 和 `asr-status.json`。启动终端应保留到执行结束。监控器只停止自己启动的进程组，不卸载其他模型；外部模型重新加载时本轮停止，并保留失败证据。

## 工作与验收范围

- 一次 Fish 模型加载、三次参考编码；先各角色预热一次。
- 三角色 × 普通/兴奋/悲伤 × 两个随机种子，共 18 个演绎样本；参考音频均为原实验合成资产。
- 同一角色/文本/参考/种子的锚点在预热后开始、累计生成约 15 分钟、至少 30 分钟时重复。
- 持续时长只累计实际生成，排除预热和空等。补测短文使用冻结的旧 T1 合成片段，最多 120 个生成任务。
- 正常退出必须同时满足预期任务、尝试记录、进程退出码、有效音频、哈希与 token 上限检查。
- CER 保留控制标签清洗规则、编辑距离分子和参考字符分母。自动筛查不等于听感验收；尾句差异、重复及长度异常需要复核。
- 本轮未覆盖服务并发、真人克隆相似度、小说自动分角色/情绪导演、整本书无人审校生产。维持 runnable，不自动进入推荐栈。

## 原 120 段报告修正

保留原始事件和 WAV，仅重新计算摘要并生成报告：

```bash
"$FISH_PY" scripts/fish-s2-followup.py analyze --run-id fish_s2_followup_20260903_142148
"$FISH_PY" scripts/build-fish-s2-followup-report.py --run-id fish_s2_followup_20260903_142148
"$FISH_PY" scripts/test_fish_s2_evidence.py
```

旧执行器保留历史兼容性，但长期驻留实验必须使用新的 persistent 入口。报告从 summary → artifact → HTML 统一生成；禁止只改 HTML 或手填通过结果。测试素材与逐段 WAV 留在 Git 排除的 results 或外部 experiments，试听包输出到 Codex outputs。

## 回归检查

`test_fish_s2_evidence.py` 使用微型假音频，覆盖完整运行、缺任务、生成前失败、坏/缺哈希、静音、非零/缺退出码、空矩阵、中止、缺结束事件、重复尝试/生成、token 截断、丢失音频、坏日志和时长不符。每个场景同时检查共享审计函数与实际分析入口，共 34 项，不需要加载模型。

## 人工试听

`build-fish-listening.py` 生成本地 HTML，包含可直接播放的完整章节与分组短音频。默认隐藏参数，听完再展开查看；评分不预填。评分仅在点击导出后保存为 CSV，页面不上传，也不自动保存输入。原轮 A 声音的定性反馈不当作本轮评分。
