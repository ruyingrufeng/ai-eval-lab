# Report source notes

- Audience: product stakeholders.
- Decision: select the current local SillyTavern default and define the next validation gate.
- Included evidence: ordinary five-turn benchmark, explicit adult four-turn benchmark, corrected adult twelve-turn continuity benchmark.
- Excluded evidence: `20260814-qwen35b-long12-invalid-v1.json`, because the prompt contradicted the generated condom state.
- Chart map: `latency_chart` answers which model/scenario combinations are operationally responsive; horizontal categorical bar, mean turn seconds, one measure, sorted ascending in the dataset, blue single-root palette from the shared renderer.
- No quality-score chart: the three benchmarks use different hard gates, so combining them into one synthetic score would create false precision. Exact tables preserve the scenario-specific denominators.
- Ordinary latency uses all five turns. Adult four-turn latency uses warm turns because model loading dominates the first request. Twelve-turn continuity uses all turns because the model was already loaded.
- Sensitive generated prose is intentionally excluded from the artifact. Only reviewed metrics and qualitative conclusions are embedded.
- Required structure mapping: title → `title`; Executive Summary → `executive_summary`; key findings/evidence → route, ordinary, adult, continuity sections; recommended next steps → `recommended_route`; further questions → `further_questions`; caveats → `caveats`.
