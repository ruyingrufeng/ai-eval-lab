#!/usr/bin/env python3
"""Flux-only 极简补跑：单进程串行，submit 后等 history，捡图。"""
import sys, json, time, uuid, shutil, subprocess
from pathlib import Path

sys.path.insert(0, '/Users/jacky/Documents/ChatGPT/内容工厂管理/scripts')
import importlib.util
spec = importlib.util.spec_from_file_location('rbe',
    '/Users/jacky/Documents/ChatGPT/内容工厂管理/scripts/run-blind-eval.py')
m = importlib.util.module_from_spec(spec); spec.loader.exec_module(m)

API = "http://127.0.0.1:8188"
ROOT = Path("/Users/jacky/Documents/ChatGPT/内容工厂管理/results/aesthetic/20260812-blind/flux")
RAW_OUT = Path("/Users/jacky/ComfyUI/output")
SEEDS = [1, 2, 3, 7, 11, 42, 123, 456, 789, 2026]


def is_already_done():
    have = {int(p.stem.split('_')[1]) for p in ROOT.glob("seed_*.png")}
    missing = [s for s in SEEDS if s not in have]
    return missing


def main():
    miss = is_already_done()
    print(f"existing: {set(SEEDS) - set(miss)}; missing: {miss}", flush=True)
    if not miss:
        print("nothing to do", flush=True)
        return

    # 等 ComfyUI 当前队列空
    print("wait ComfyUI queue empty...", flush=True)
    while True:
        try:
            r = subprocess.run(["curl", "-fsS", f"{API}/queue"],
                               capture_output=True, text=True, timeout=5)
            if r.returncode == 0:
                d = json.loads(r.stdout)
                if not d.get("queue_running") and not d.get("queue_pending"):
                    print("  queue empty", flush=True)
                    break
                print(f"  running={len(d['queue_running'])} pending={len(d['queue_pending'])} wait 10s...", flush=True)
        except Exception as e:
            print(f"  poll err: {e}", flush=True)
        time.sleep(10)

    # 重新算 missing（之前 ComfyUI 跑的可能已生成但未拷）
    miss = is_already_done()
    print(f"after wait: missing={miss}", flush=True)
    if not miss:
        print("nothing to do after wait", flush=True)
        return

    out = []
    for seed in miss:
        wf = m.build_flux_workflow(seed)
        client_id = f"flux-fill-{seed}-{uuid.uuid4().hex[:6]}"
        try:
            print(f"submit flux seed={seed}...", flush=True)
            pid = m.submit(wf, client_id)
            print(f"  pid={pid[:8]}", flush=True)
            t0 = time.time()
            hist = m.wait_done(pid, timeout_sec=900)
            elapsed = time.time() - t0
            copied = []
            for node_out in hist.get("outputs", {}).values():
                if "images" in node_out:
                    for img in node_out["images"]:
                        fname = img.get("filename", "")
                        src = RAW_OUT / fname
                        if src.exists():
                            dst = ROOT / f"seed_{seed:04d}.png"
                            shutil.copy2(src, dst)
                            copied.append(str(dst))
            rec = {"seed": seed, "elapsed_sec": round(elapsed, 2),
                   "outputs": copied, "status": "ok" if copied else "no_output"}
            print(f"  done seed={seed} {elapsed:.1f}s copied={len(copied)}", flush=True)
        except Exception as e:
            rec = {"seed": seed, "status": "error", "error": str(e)}
            print(f"  ERROR seed={seed}: {e}", flush=True)
        out.append(rec)
        time.sleep(1)

    fill_path = ROOT.parent / "flux_fill_report.json"
    with open(fill_path, "w") as f:
        json.dump(out, f, indent=2, ensure_ascii=False)
    miss2 = is_already_done()
    print(f"\nfinal: missing={miss2}; total in flux dir: {len(list(ROOT.glob('*.png')))}", flush=True)


if __name__ == "__main__":
    main()
