# Report source notes

- Audience: product stakeholders.
- Decision: whether any current local model should become the default business Agent, and what to test next.
- Included evidence: 27B first run, 27B recovery, 30B 180-second gate, 35B 180-second gate.
- Chart map: `gate_elapsed_chart` compares required-file completion across the four attempts; categorical bar, one numeric measure, exact elapsed time retained in tooltips and source data.
- Quality is not reduced to one score. File completion, fact retention, normal exit, and qualitative completeness remain separate because normal exit is a hard gate.
- 27B fact retention uses the saved human/rule audit because its process summary marks the incomplete three-file bundle as an automatic failure.
- Required structure mapping: title → `title`; Executive Summary → `executive_summary`; key findings/evidence → latency/model/coverage sections; recommended next steps → `recommended_next`; further questions → `further_questions`; caveats → `caveats`.
