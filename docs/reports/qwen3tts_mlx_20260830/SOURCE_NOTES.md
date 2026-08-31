# Qwen3-TTS MLX report source notes

- Audience: technical maintainers deciding whether the 9893 route can advance from `runnable` to `verified`.
- Decision rule: infrastructure success and content fidelity are separate gates; a green HTTP response cannot override repeated-content evidence.
- Chart rationale: the single RTF bar chart shows the fixed short-request overhead and the stable long-text speed plateau; exact audit values and fidelity verdicts remain in tables.
- Primary run: `python3 scripts/benchmark-qwen3tts-mlx.py`.
- ASR cross-check: `python3 scripts/validate-qwen3tts-asr.py --input-dir results/qwen3tts_mlx_20260830 --output results/qwen3tts_mlx_20260830/asr_validation.json --model <cached-base-model>` and repeat with the cached small model.
- Raw outputs remain under ignored `results/qwen3tts_mlx_20260830/`; the report artifact embeds the reviewed aggregates needed for audit.
