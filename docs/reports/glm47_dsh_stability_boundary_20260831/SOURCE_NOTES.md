# GLM/dsh 稳定性与上下文边界报告来源

- 五轮稳定性原始结果：`results/glm47_dsh_stability_20260831/round_1/` 至 `round_5/`。
- 20K 压力门禁：`results/glm47_dsh_stability_20260831/context_20000/result.json`。
- 20K 服务端证据：`results/glm47_dsh_stability_20260831/context_20000/context_20000/llama-log-delta.txt`。
- 15K 已验证对照：`results/glm47_dsh_retest_20260831/formal_v2/result.json`。
- 评测定义：`benchmarks/glm47_dsh_formal_20260831.yaml`。
- 评测器：`scripts/benchmark-glm47-dsh.py`。

五轮共 15 次真实文件任务，全部正常退出并通过精确值、外部 schema、会话绑定和 8086 请求门禁。20K 目标实际提示为 20,586 tokens、槽位达到 21,472 tokens，耗时 327.718 秒后只输出三个反引号，进程返回 1，内容保持、裸 JSON 与 schema 均失败。报告中的 swap 与空闲内存来自系统级采样，不以进程 RSS 代替统一内存结论。
