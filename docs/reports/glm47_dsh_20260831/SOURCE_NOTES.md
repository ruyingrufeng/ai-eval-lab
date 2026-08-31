# GLM-4.7 dsh report source notes

- Audience: technical maintainers deciding whether GLM-4.7 can become the verified dsh default.
- Chart map: one latency bar chart compares all five formal cases; fields are case label and wall-clock seconds, with result, binding, and max slot tokens in tooltips. It supports the claim that even successful cases are minute-scale.
- Deterministic gate: model-written files are graded externally against values declared in `benchmarks/glm47_dsh_formal_20260831.yaml`.
- Binding gate: every formal case requires both dsh session `request/context` and llama-server request logs; preset names and `--dump-config` are insufficient.
- Context accounting: use maximum llama-server `release ... n_tokens`; session usage may split cached and newly processed tokens after retry.
- Resource boundary: runs were serial; memory pressure and swap were captured for every case. No RSS-only capacity claim is used.
- Raw evidence remains under ignored `results/glm47_dsh_20260831/`; the artifact embeds the reviewed aggregates.
