# Qwen3-TTS 本地语音引擎部署完成

## 服务状态
- ✅ Qwen3-TTS 1.7B (9883) - 主力引擎
- ✅ Edge TTS (9882) - 备用引擎
- ✅ SillyTavern (8000) - 已配置

## ST TTS 配置
- Provider: `OpenAI Compatible`
- URL: `http://127.0.0.1:9883/v1/audio/speech`
- Model: `qwen3-tts-1.7b`
- 声音映射: Vivian/Serena/Ryan/Aiden/Ono

## 性能数据
| 测试 | 耗时 | 大小 |
|------|------|------|
| Vivian "你好杰哥" | 3.9s | 113KB |
| Aiden English | 8.8s | 330KB |
| Ryan 长文 | ~4分钟 | 11MB |

## 启动方式
```bash
# 手动
~/voice-tools/start_qwen3_tts_17b.sh

# launchd（已配置）
launchctl load ~/Library/LaunchAgents/com.jacky.qwen3-tts.plist
```

## 注意
- 首次加载模型需 30-60 秒
- 中文长文本较慢（MPS 无 flash-attn）
- 建议短回复使用，长文分段
