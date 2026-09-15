# AI Eval Lab

> Local, reproducible, systematic AI model & tool evaluation lab.

**AI Eval Lab** is a methodology, script collection, and benchmark suite for building local AI content production infrastructure on Apple Silicon Macs. It doesn't produce content — it answers the question: **on my machine, which model is fastest, most accurate, and most reliable?**

## Why?

Model benchmarks are everywhere, but:
- Most are tested on NVIDIA GPUs — Apple Silicon data is scarce
- Benchmark scores don't reflect real-world business scenarios
- No unified testing methodology, results aren't comparable
- After testing dozens of models, you still don't know which one to use

AI Eval Lab evaluates using **real business closed-loops** — not "how many tokens/s can this model do," but "can it complete an entire content production task, what's the quality, how long does it take, and how much memory does it eat?"

## What it does

- 🧪 **Text model evaluation**: quality, speed, memory, long context, Agent tool use, roleplay
- 🎨 **Image model evaluation**: Flux / SDXL speed comparison, aesthetic evaluation, identity consistency
- 🎙️ **Speech pipeline evaluation**: TTS quality/speed comparison, ASR accuracy, multi-voice cloning
- 🎬 **Video & digital human**: end-to-end pipeline validation (feasibility-first on low-power machines)
- 📊 **Performance matrix**: concurrency levels, memory footprint, thermal throttling, multi-service coexistence
- 🔄 **Continuous discovery**: new models auto-enter the evaluation pool, selections are periodically rechecked

## Project Structure

```
ai-eval-lab/
├── docs/                # Architecture, testing specs, decisions, reports
│   ├── ARCHITECTURE.md      # Architecture & layering principles
│   ├── TESTING.md           # Testing methodology & acceptance criteria
│   ├── DECISIONS.md         # Key selection decision records
│   ├── CONTINUOUS_DISCOVERY.md  # Continuous discovery & review mechanism
│   └── reports/             # Formal evaluation reports (self-contained HTML)
├── registry/            # Model & tool registry (machine-readable)
│   ├── candidates.yaml      # Candidate list & statuses
│   ├── content_type_matrix.yaml  # Content-type capability matrix
│   └── discovery_log.yaml   # Continuous discovery log
├── benchmarks/          # Test case definitions (no production content)
│   ├── agent_scenarios.yaml   # Agent business scenarios
│   ├── performance_matrix.yaml  # Performance & concurrency matrix
│   └── text/  image/  tts/   # Per-modality test sets
├── scripts/             # Install, probe, and benchmark scripts
│   ├── probe-host.sh        # Host baseline probe
│   ├── setup-mlx-lm.sh      # MLX environment setup
│   ├── benchmark-*.py       # Various benchmark runners
│   └── build-*-report.py    # Report generators
└── results/             # Local test results (gitignored by default)
```

## Quick Start

### 1. Probe your machine baseline

```bash
./scripts/probe-host.sh
```

Results are written to `results/host/`, confirming your hardware, OS, and installed tool baseline.

### 2. Run a text model benchmark

```bash
# Set up MLX environment first
./scripts/setup-mlx-lm.sh

# Run benchmark for a specific model
./scripts/benchmark-mlx-lm.sh MODEL_ID
```

### 3. Run Flux image speed test

```bash
python scripts/benchmark-flux-speed.py --model flux-1-schnell-q4
```

### 4. Browse existing reports

All formal evaluation reports live in `docs/reports/` as self-contained HTML files — open directly in your browser.

Representative completed evaluations:
- [Business Agent Evaluation (text)](docs/reports/business_agent_evaluation_20260814/report.html)
- [TTS & ASR Benchmark (speech)](docs/reports/tts_asr_bench_20260816/report.html)
- [Fish Speech S2 Pro Voice Cloning](docs/reports/fish_s2_pro_mlx_20260903/report.html)

## Core Philosophy

### 1. Conclusions must be实测-based
Documentation claims don't count — running it does. Every model/tool has a status:
`candidate` → `installable` → `runnable` → `verified`

### 2. Evaluate with real business scenarios
No more "three technical questions decide everything" paper benchmarks. We test:
- Content growth closed-loop (topic → writing → formatting → publishing)
- Research-to-decision closed-loop (search → analysis → recommendation → report)
- Interview-to-insight closed-loop (transcribe → summarize → cluster → insights)

### 3. Environment isolation
Each tool category gets its own virtual environment, avoiding dependency pollution. Model weights live outside the repo — only IDs and configs are tracked.

### 4. Continuous discovery, periodic review
Selection isn't a one-time thing. New models enter the evaluation pool automatically. Selected models get rechecked periodically — outdated ones get retired.

## Hardware Reference Baseline

Initial validation of this project was done on:
- **MacBook Air M5** (10-core CPU / 10-core GPU)
- **32 GB** unified memory
- **macOS 26+**

You can run the same tests on your own machine to get your personalized selection conclusions.

## Documentation Index

| Topic | Document |
|-------|----------|
| Architecture | [docs/ARCHITECTURE.md](docs/ARCHITECTURE.md) |
| Testing Methodology | [docs/TESTING.md](docs/TESTING.md) |
| Decision Records | [docs/DECISIONS.md](docs/DECISIONS.md) |
| Continuous Discovery | [docs/CONTINUOUS_DISCOVERY.md](docs/CONTINUOUS_DISCOVERY.md) |
| Performance & Concurrency | [docs/PERFORMANCE_CONCURRENCY.md](docs/PERFORMANCE_CONCURRENCY.md) |
| Content-type Selection Guide | [docs/CONTENT_TYPE_SELECTION.md](docs/CONTENT_TYPE_SELECTION.md) |
| Agent Business Eval Plan | [docs/AGENT_BUSINESS_EVALUATION_PLAN_20260814.md](docs/AGENT_BUSINESS_EVALUATION_PLAN_20260814.md) |
| Image Aesthetic Eval Standards | [docs/IMAGE_AESTHETIC_EVALUATION.md](docs/IMAGE_AESTHETIC_EVALUATION.md) |

## Roadmap

- [x] Phase 1: Freeze baseline + text/image/speech pipeline validation
- [x] Phase 2: Business Agent closed-loop evaluation + continuous discovery
- [ ] Phase 3: Video & digital human pipeline stabilization
- [ ] Phase 4: Cross-machine result comparison & leaderboard

## License

MIT License — use freely, just keep the copyright notice.

---

If this project helps you, a Star ⭐ is appreciated. Contributions of test results from your own machine are also welcome.
