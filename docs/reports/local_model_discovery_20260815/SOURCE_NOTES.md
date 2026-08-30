# Report source notes

- Audience: product stakeholders.
- Decision: determine whether any newly downloaded model should replace the current 27B for SillyTavern or Agent use while preserving usable local vision.
- Scope: three newly downloaded candidates selected from current official/community model repositories; all tested at one 64K slot with Q8 KV cache.
- Included models: Gemma 4 12B uncensored Q5_K_M + mmproj, Qwythos 9B v2 Q6_K + mmproj, MN-VelvetCafe-RP-12B-V2 Q5_K_M.
- Included evidence: five-turn ordinary roleplay, four-turn adult capability, finalists' twelve-turn state continuity, finalists' approximately 16K-token four-needle recall, deterministic image recognition, and real dual-service coexistence.
- Follow-up evidence: direct prose review, same-prompt 1200–1600-character generation against current 27B, manual semantic audit of the adult stop turn, and a standard OpenAI-compatible tool-calling gate.
- Chart map: `ordinary_turn_latency_chart` answers how complete response time varies across the same five ordinary-roleplay turns; grouped categorical bar, turn on x, seconds on y, model as the only meaningful series, three approved categorical roots. It supports the claim that Qwythos is fastest but speed alone does not determine the route.
- No cross-scenario chart: adult, twelve-turn, and long-context tests have different output lengths and gate systems; mixing them in one visual would imply false comparability. Exact tables keep denominators and gate meanings visible.
- Sensitive generated adult prose remains in the git-ignored `results/` directory and is not embedded in the report.
- Correction: VelvetCafe's original four-turn automatic grade was a false pass. The third response stopped and then resumed penetration without renewed consent; `scripts/benchmark-sillytavern-adult.py` was expanded to detect this pattern. The raw result is preserved and a separate manual audit records the correction.
- Required structure mapping: title → `title`; Executive Summary → `executive_summary`; findings/evidence → recommendation, length, tradeoff, coexistence, and Agent sections; next steps → `recommended_next_steps`; further questions → `further_questions`; caveats → `caveats`.
- Production state: no model route was changed during this discovery report. The current 27B single-slot production entry remains in place.
