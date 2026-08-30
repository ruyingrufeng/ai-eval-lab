# 图片 C1、资源与审美联合复测

测试时间：2026-08-12 11:52–12:14 +08:00。记录时间：2026-08-12 12:16 +08:00。

## 结论

- RealVisXL 与 Flux Q4 的 C1 都是“同时提交、队列串行”，没有图片 GPU 并行；
- RealVisXL 两张总 wall time 109.612 秒，Flux 两张 757.215 秒；
- 两条 C1 均完成且 swap 未增长，但有 pageout；Flux 第二张比第一张慢 23.8%；
- 27B LLM 单任务加载已把 memory pressure 可用比例从 77% 压到最低 8%，swap 增加约 1566 MiB，因此图片+27B 的 X1 共存测试按停止条件取消；
- RealVisXL 新增两张的技术成功率为 2/2，但按用户审美与技术初评，“可直接使用率”为 0/2；Flux 提示遵循与身材协调更好，但人脸和穿搭仍偏普通，需要正式匿名 10-seed 盲评。

## C1 队列结果

| 模型 | 请求1执行 | 请求2等待 | 请求2执行 | 总 wall time | 吞吐 |
|---|---:|---:|---:|---:|---:|
| RealVisXL V5 | 56.051 s | 56.203 s | 53.403 s | 109.612 s | 1.0948 张/分钟 |
| Flux.1-dev Q4 | 338.292 s | 338.455 s | 418.758 s | 757.215 s | 0.1585 张/分钟 |

两个服务都能快速接收第二个请求，但第二个请求直到第一个完成才开始执行。C1 可用于可靠排队，不提升单机 GPU 并行吞吐。

## 系统资源

### RealVisXL C1

- 80 个样本，2 秒间隔；
- memory pressure free：最低 54%，起止 77%；
- swap：6632.12 MiB，增量 0；
- pageout 增量：77；
- ComfyUI RSS 观测峰值约 3730720 KiB；
- macOS 未记录 thermal/performance warning。

### Flux Q4 C1

- 386 个样本，2 秒间隔；
- memory pressure free：最低 52%，起止 81%/82%；
- swap：减少 24 MiB，无测试导致增长；
- pageout 增量：769；
- ComfyUI RSS 观测峰值约 6634912 KiB；
- macOS 未记录 thermal/performance warning。

RSS 仍只作辅助；系统 memory pressure、swap 和 pageout 是统一内存判断主证据。

## 27B LLM 单任务与 X1 停止判定

模型：`qwen3.6-27b-fable`，路由报告模型大小约 13.1 GiB，当前上下文为 64K、parallel 2。

- 请求端到端：23.745 秒；
- 生成：103 tokens，约 6.79 tok/s；
- memory pressure free：77% → 最低 8%；
- swap：+1566.19 MiB，并接近当时上限；
- pageout：+151；
- 派生模型进程 RSS 约 21.2 GiB；
- 因触发严重内存压力/快速 swap 增长，未启动 RealVisXL，X1 判定为 `blocked_by_resource_preflight`。

正确卸载方式是路由器 `POST /models/unload`，而不是直接向派生子进程发信号。API 卸载 1 秒内完成，memory pressure 恢复到 81%；8086 路由保持健康。

## 审美初评

本轮知道模型名称，不属于正式盲评，只用于缺陷归类。

### RealVisXL 两张

1. 第一张丢失绿色连体服和黄色笔记本，把颜色分配到红上衣、黑裤、绿椅和黄花盆；人物脸部、穿搭和构图类似普通图库照，缺少时尚感和记忆点。
2. 第二张提示遵循较好，但黄色笔记本比例异常；人物造型偏成熟，脸部与服装风格仍偏传统图库样片。

共同判断：身材基本协调、无严重解剖错误，但颜值、服装搭配和商业成片感没有达到用户标准；本轮可直接使用率 0/2。

### Flux 两张

1. 两张均保留绿色连体服、红椅、黄色笔记本、右侧植物、站姿和全身；
2. 身材比例与重心总体自然，服装结构连贯；
3. 人脸偏通用模板、细节较柔；穿搭只达到基础协调，缺少饰品、层次和设计亮点；
4. 第二张光影和画面秩序更好，但整体仍像普通 AI 商业样片。

共同判断：在当前样本中明显优于 RealVisXL，但尚不能仅凭 2 张宣布审美通过。

## 原始证据

- RealVisXL：`results/performance/realvisxl-c1-20260812-1152/`；
- Flux：`results/performance/flux-c1-20260812-1201/`；
- LLM：`results/performance/llm-c0-20260812/`；
- 运行器：`scripts/benchmark-comfy-queue.py`、`scripts/benchmark-llm-request.py`；
- 资源工具：`scripts/sample-macos-resources.sh`、`scripts/summarize-resource-jsonl.py`。

## 后续测试

1. RealVisXL 与 Flux 各补齐 10 个 seed，匿名编号后做正式审美盲评；
2. 测试更明确的时尚造型提示、服装参考或服装 LoRA，评估能否提高每张合格图成本；
3. X1 改用较轻的 7B–14B 文本模型或降低 27B 上下文/parallel 后再测；
4. 不再测试当前 27B 64K×2 与扩散模型共存；
5. C2 对当前单 GPU 串行服务价值低，先不执行。
