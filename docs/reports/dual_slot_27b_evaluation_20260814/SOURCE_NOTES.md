# Source notes

- Reporting question: can the existing Qwen3.6-27B Fable deployment sustain one controlled business lane and one SillyTavern-style lane concurrently while preserving two 64K contexts?
- Audience: product stakeholders. Required structure maps directly to the title, Executive Summary, findings with visual evidence, recommendations, further questions, and caveats blocks.
- Comparison basis: ordinary-role historical single-run TTFT 1.689 seconds and adult historical single-run TTFT 2.725 seconds. The concurrent threshold is the larger of 3 seconds or twice each baseline.
- Chart map: `request_ttft_chart` answers how first-token latency varied across nine concurrent requests. It uses a categorical bar chart because the observations are discrete requests, not a time trend. Lane color distinguishes the three request types and the dataset retains total latency and completion tokens for inspection.
- No resource trend chart was added because 84 five-second samples would emphasize short-term noise; the decision depends on minimum free memory, swap net change, and consecutive red samples, which are clearer in the exact gate table.
- Sensitive adult response text remains only in the Git-excluded `results/` tree. The portable artifact contains latency, length, and reviewed safety conclusions only.
- The run validates two simultaneously active slots at short context. It does not validate 16K, 32K, or 64K prompt occupancy.
