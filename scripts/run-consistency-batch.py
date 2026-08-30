#!/usr/bin/env python3
"""数字人夜跑脚本 1：人物一致性盲评（IP-Adapter 锁脸）。

策略：
  - 同一参考脸，10 seed 测稳定性
  - 默认只跑 Flux 10 张；RealVisXL 仅在显式传入 --include-realvisxl 时运行
  - RealVisXL: 25 steps, dpmpp_2m_sde/karras, cfg 6.5
  - Flux: 20 steps, euler/simple, cfg 1.0（rectified flow）
  - IP-Adapter 权重 0.85（高锁脸）

使用方法：
  python3 run-consistency-batch.py [--dry-run] [--include-realvisxl]
"""
import argparse
import json
import shutil
import subprocess
import sys
import time
import uuid
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
from build_ipadapter_workflow import build_realvisxl_ipadapter_workflow, build_flux_ipadapter_workflow

API = "http://127.0.0.1:8188"
SEEDS = [1, 2, 3, 7, 11, 42, 123, 456, 789, 2026]
DEFAULT_REF = "/Users/jacky/Documents/ChatGPT/内容工厂管理/results/aesthetic/20260812-blind/flux/seed_0007.png"
ROOT = Path("/Users/jacky/Documents/ChatGPT/内容工厂管理/results/aesthetic/20260812-ipadapter")
RAW_OUT = Path("/Users/jacky/ComfyUI/output")


def check_memory_free_pct() -> float:
    r = subprocess.run(["memory_pressure", "-Q"], capture_output=True, text=True, timeout=5)
    for line in r.stdout.splitlines():
        if "System-wide memory free percentage" in line:
            return float(line.split(":")[1].strip().rstrip("%"))
    return -1.0


def comfy_health() -> bool:
    r = subprocess.run(["curl", "-fsS", "--max-time", "3", f"{API}/system_stats"],
                       capture_output=True, timeout=5)
    return r.returncode == 0


def submit(wf: dict, client_id: str, max_retry: int = 2) -> str:
    payload = json.dumps({"prompt": wf, "client_id": client_id})
    last_err = "unknown"
    for attempt in range(max_retry + 1):
        r = subprocess.run(
            ["curl", "-fsS", "-X", "POST", f"{API}/prompt",
             "-H", "Content-Type: application/json", "-d", payload],
            capture_output=True, text=True, timeout=15,
        )
        if r.returncode == 0:
            return json.loads(r.stdout)["prompt_id"]
        last_err = r.stderr or "no stderr"
        if attempt < max_retry:
            print(f"  retry {attempt+1}/{max_retry}...", flush=True)
            time.sleep(3)
    raise RuntimeError(f"submit failed after {max_retry+1} attempts: {last_err}")


def wait_done(prompt_id: str, timeout_sec: int = 1800) -> dict:
    deadline = time.time() + timeout_sec
    while time.time() < deadline:
        r = subprocess.run(["curl", "-fsS", f"{API}/history/{prompt_id}"],
                           capture_output=True, text=True, timeout=10)
        if r.returncode == 0:
            hist = json.loads(r.stdout)
            if prompt_id in hist:
                return hist[prompt_id]
        time.sleep(3)
    raise TimeoutError(f"timeout {prompt_id}")


def collect_outputs(history: dict, model_key: str, seed: int) -> list:
    copied = []
    target_dir = ROOT / model_key
    target_dir.mkdir(parents=True, exist_ok=True)
    for node_out in history.get("outputs", {}).values():
        if "images" in node_out:
            for img in node_out["images"]:
                fname = img.get("filename", "")
                src = RAW_OUT / fname
                if src.exists():
                    dst = target_dir / f"seed_{seed:04d}.png"
                    shutil.copy2(src, dst)
                    copied.append(str(dst))
    return copied


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--dry-run", action="store_true")
    parser.add_argument("--reference", default=DEFAULT_REF)
    parser.add_argument("--include-realvisxl", action="store_true",
                        help="显式启用已退出默认生产路线的 RealVisXL 对照组")
    parser.add_argument("--skip-flux", action="store_true")
    args = parser.parse_args()

    print("=== 一致性盲评（IP-Adapter 锁脸）===", flush=True)
    free_pct = check_memory_free_pct()
    print(f"  memory free: {free_pct}%", flush=True)
    if free_pct < 40:
        print("  ❌ 内存不足（<40%），拒绝启动。", flush=True)
        sys.exit(1)
    if not comfy_health():
        print("  ❌ ComfyUI 8188 不在线，请先启。", flush=True)
        sys.exit(1)
    if not Path(args.reference).exists():
        print(f"  ❌ 参考图不存在: {args.reference}", flush=True)
        sys.exit(1)
    print(f"  ✅ ComfyUI online, ref={Path(args.reference).name}", flush=True)

    if args.dry_run:
        print("  DRY RUN.", flush=True)
        sys.exit(0)

    (ROOT / "flux").mkdir(parents=True, exist_ok=True)
    if args.include_realvisxl:
        (ROOT / "realvisxl").mkdir(parents=True, exist_ok=True)

    results = []
    models = []
    if args.include_realvisxl:
        models.append("realvisxl")
    if not args.skip_flux:
        models.append("flux")

    for model_key in models:
        print(f"\n=== {model_key} ===", flush=True)
        builder = (build_realvisxl_ipadapter_workflow if model_key == "realvisxl"
                   else build_flux_ipadapter_workflow)
        timeout = 1800 if model_key == "flux" else 600

        for seed in SEEDS:
            dst = ROOT / model_key / f"seed_{seed:04d}.png"
            if dst.exists():
                print(f"  seed {seed:>4}  skip (exists)", flush=True)
                continue
            client_id = f"cons-{model_key}-{seed}-{uuid.uuid4().hex[:6]}"
            try:
                wf = builder(args.reference, seed, ipadapter_weight=0.85)
                pid = submit(wf, client_id)
                t0 = time.time()
                hist = wait_done(pid, timeout_sec=timeout)
                elapsed = time.time() - t0
                copied = collect_outputs(hist, model_key, seed)
                rec = {"model": model_key, "seed": seed,
                       "elapsed_sec": round(elapsed, 2),
                       "outputs": copied,
                       "status": "ok" if copied else "no_output"}
                print(f"  seed {seed:>4}  done {elapsed:6.1f}s  copied={len(copied)}", flush=True)
            except Exception as e:
                rec = {"model": model_key, "seed": seed,
                       "status": "error", "error": str(e)}
                print(f"  seed {seed:>4}  ERROR: {e}", flush=True)
            results.append(rec)
            time.sleep(1)

    report_path = ROOT / "consistency_report.json"
    with open(report_path, "w") as f:
        json.dump(results, f, indent=2, ensure_ascii=False)
    ok = sum(1 for r in results if r["status"] == "ok")
    print(f"\n=== 完成 ===", flush=True)
    print(f"  {ok}/{len(results)} ok", flush=True)
    print(f"  report: {report_path}", flush=True)


if __name__ == "__main__":
    main()
