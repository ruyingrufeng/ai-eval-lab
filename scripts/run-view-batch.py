#!/usr/bin/env python3
"""数字人夜跑脚本 3：多视角/多表情（5 视角 × 5 seed，Flux IP-Adapter）。

参考脸：flux/seed_0007.png
视角：front / side / three_quarter / back / closeup
"""
import argparse, json, shutil, subprocess, sys, time, uuid, importlib.util
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
from build_ipadapter_workflow import build_flux_ipadapter_workflow
from avatar_prompts import VIEW_TESTS, VIEW_NEGATIVE

API = "http://127.0.0.1:8188"
SEEDS = [1, 42, 123, 456, 2026]
DEFAULT_REF = "/Users/jacky/Documents/ChatGPT/内容工厂管理/results/aesthetic/20260812-blind/flux/seed_0007.png"
ROOT = Path("/Users/jacky/Documents/ChatGPT/内容工厂管理/results/aesthetic/20260812-view")
RAW_OUT = Path("/Users/jacky/ComfyUI/output")


def _check_memory():
    r = subprocess.run(["memory_pressure", "-Q"], capture_output=True, text=True, timeout=5)
    for line in r.stdout.splitlines():
        if "System-wide memory free percentage" in line:
            return float(line.split(":")[1].strip().rstrip("%"))
    return -1.0


def _comfy_health():
    r = subprocess.run(["curl", "-fsS", "--max-time", "3", f"{API}/system_stats"],
                       capture_output=True, timeout=5)
    return r.returncode == 0


def _submit(wf, client_id, max_retry=2):
    payload = json.dumps({"prompt": wf, "client_id": client_id})
    last_err = "unknown"
    for attempt in range(max_retry + 1):
        r = subprocess.run(["curl", "-fsS", "-X", "POST", f"{API}/prompt",
                            "-H", "Content-Type: application/json", "-d", payload],
                           capture_output=True, text=True, timeout=15)
        if r.returncode == 0:
            return json.loads(r.stdout)["prompt_id"]
        last_err = r.stderr or "no stderr"
        if attempt < max_retry:
            time.sleep(3)
    raise RuntimeError(f"submit failed: {last_err}")


def _wait(prompt_id, timeout_sec=1800):
    deadline = time.time() + timeout_sec
    while time.time() < deadline:
        r = subprocess.run(["curl", "-fsS", f"{API}/history/{prompt_id}"],
                           capture_output=True, text=True, timeout=10)
        if r.returncode == 0:
            hist = json.loads(r.stdout)
            if prompt_id in hist:
                return hist[prompt_id]
        time.sleep(3)
    raise TimeoutError(prompt_id)


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--dry-run", action="store_true")
    parser.add_argument("--reference", default=DEFAULT_REF)
    args = parser.parse_args()

    print("=== 多视角盲评（Flux IP-Adapter）===", flush=True)
    if _check_memory() < 40:
        print("  ❌ 内存不足", flush=True); sys.exit(1)
    if not _comfy_health():
        print("  ❌ ComfyUI 不在线", flush=True); sys.exit(1)
    if not Path(args.reference).exists():
        print(f"  ❌ 参考图不存在", flush=True); sys.exit(1)
    print(f"  ✅ ready, ref={Path(args.reference).name}", flush=True)
    if args.dry_run:
        sys.exit(0)

    results = []
    for view_key, vt in VIEW_TESTS.items():
        (ROOT / view_key).mkdir(parents=True, exist_ok=True)
        print(f"\n--- {vt['name']} ---", flush=True)
        for seed in SEEDS:
            dst = ROOT / view_key / f"seed_{seed:04d}.png"
            if dst.exists():
                print(f"  seed {seed:>4}  skip", flush=True)
                continue
            client_id = f"vw-{view_key}-{seed}-{uuid.uuid4().hex[:6]}"
            try:
                wf = build_flux_ipadapter_workflow(
                    args.reference, seed, ipadapter_weight=0.85,
                )
                # 替换 positive / negative
                for nid, n in wf.items():
                    if n["class_type"] == "CLIPTextEncode":
                        text = n["inputs"].get("text", "")
                        if "professional editorial" in text or "modern red armchair" in text:
                            n["inputs"]["text"] = vt["positive"]
                        elif text == "":
                            n["inputs"]["text"] = VIEW_NEGATIVE
                pid = _submit(wf, client_id)
                t0 = time.time()
                hist = _wait(pid, timeout_sec=1800)
                elapsed = time.time() - t0
                copied = []
                for node_out in hist.get("outputs", {}).values():
                    if "images" in node_out:
                        for img in node_out["images"]:
                            src = RAW_OUT / img.get("filename", "")
                            if src.exists():
                                shutil.copy2(src, dst)
                                copied.append(str(dst))
                rec = {"view": view_key, "seed": seed,
                       "elapsed_sec": round(elapsed, 2),
                       "outputs": copied,
                       "status": "ok" if copied else "no_output"}
                print(f"  seed {seed:>4}  done {elapsed:6.1f}s  copied={len(copied)}", flush=True)
            except Exception as e:
                rec = {"view": view_key, "seed": seed,
                       "status": "error", "error": str(e)}
                print(f"  seed {seed:>4}  ERROR: {e}", flush=True)
            results.append(rec)
            time.sleep(1)

    report_path = ROOT / "view_report.json"
    with open(report_path, "w") as f:
        json.dump(results, f, indent=2, ensure_ascii=False)
    ok = sum(1 for r in results if r["status"] == "ok")
    print(f"\n=== 完成 {ok}/{len(results)} ok ===", flush=True)


if __name__ == "__main__":
    main()
