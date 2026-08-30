# Source notes

- Reporting question: which production route should own the externally orchestrated business workflow after the 27B dual-slot test passed?
- Audience: product stakeholders. Required structure maps to the title, Executive Summary, comparison scope, findings with visual evidence, routing recommendation, further questions, and caveats.
- Chart map: `step_latency_chart` compares each of the three identical business steps across the two planned production routes. Grouped categorical bars are used because the question is a discrete route comparison, not a time trend. Two palette roots distinguish the routes; tooltips retain TTFT, output tokens, and validation status.
- The 11.1x figure is an observed production-route ratio: 27B ran under dual-slot concurrent load and 35B ran single-slot exclusive. It must not be presented as a controlled pure-model speed ratio.
- Quality checks combine deterministic coverage gates and a manual review of the saved non-sensitive business outputs. One case is insufficient for a general model-quality ranking.
- No separate resource chart was added because the 35B run produced only eight five-second samples. Exact minimum memory and swap changes remain in the source summaries and narrative caveat.
