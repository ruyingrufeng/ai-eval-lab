# Qwen3-TTS 1.7B 本地语音引擎配置完成

> 历史配置记录：本文的 `9883` 启动方式已经失效。当前入口是手动按需启动的 `9893` MLX 服务；2026-08-31 复测结论为短文本 `runnable`、长文本内容保真未通过，详见 `docs/reports/qwen3tts_mlx_20260830/report.html`。

## 服务状态
- ✅ Edge TTS (9882) - 快速备用
- ✅ Qwen3-TTS 1.7B (9883) - 主力引擎（有感情）

## 测试结果
| 声音 | 时长 | 大小 | 耗时 |
|------|------|------|------|
| Vivian | 1.4s | 113KB | 3.9s |
| Ryan | ~5s | 11MB | 4分钟 |
| Aiden | 3.3s | 330KB | 8.8s |

## 配置 ST TTS
1. 打开 SillyTavern → Extensions → TTS
2. Provider 选 **OpenAI Compatible**
3. URL: `http://127.0.0.1:9883`
4. API Key: 任意（如 `local`）
5. Model: `qwen3-tts-1.7b`
6. 点 Refresh 加载声音列表
7. 给角色分配声音 → Apply

## 启动脚本
```bash
# 手动启动
~/voice-tools/start_qwen3_tts_17b.sh

# launchd 自动启动（已配置）
launchctl load ~/Library/LaunchAgents/com.jacky.qwen3-tts.plist
```

## 注意
- 首次启动需加载 4GB 模型到 MPS（约30秒）
- 中文长文本（>50字）可能较慢，建议分段
- 如需停止：`pkill -f qwen3_tts_17b_final.py`
