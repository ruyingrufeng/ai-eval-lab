#!/usr/bin/env python3
"""补跑缺的 seed，并捡回 ComfyUI output 里已生成但未归档的 blind 图。

缺：
- RealVisXL: seed 123/456/789/2026（4 张）
- Flux: 全部 10 张（1/2/3/7/11/42/123/456/789/2026）

策略：
1. 先扫 /Users/jacky/ComfyUI/output/blind_*.png 里缺的 seed，捡回项目目录
2. 再跑剩下的 seed（RealVisXL 4 + Flux 10）
"""
import json
import re
import subprocess
import time
import uuid
import shutil
from pathlib import Path
import sys

sys.path.insert(0, '/Users/jacky/Documents/ChatGPT/内容工厂管理/scripts')
import importlib.util
spec = importlib.util.spec_from_file_location('rbe',
    '/Users/jacky/Documents/ChatGPT/内容工厂管理/scripts/run-blind-eval.py')
m = importlib.util.module_from_spec(spec); spec.loader.exec_module(m)

API = "http://127.0.0.1:8188"
ROOT = Path("/Users/jacky/Documents/ChatGPT/内容工厂管理/results/aesthetic/20260812-blind")
RAW_OUT = Path("/Users/jacky/ComfyUI/output")
ALL_SEEDS = [1, 2, 3, 7, 11, 42, 123, 456, 789, 2026]


def collect_existing():
    """扫 ComfyUI output 里所有 blind_*.png，按模型/seed 分组，拷到项目目录。"""
    picked = {"realvisxl": [], "flux": []}
    for f in RAW_OUT.glob("blind_*.png"):
        name = f.name
        m_rv = re.match(r"blind_realvisxl_seed(\d+)_\d{5}_\.png", name)
        m_fl = re.match(r"blind_flux_seed(\d+)_\d{5}_\.png", name)
        if m_rv:
            seed = int(m_rv.group(1))
            dst = ROOT / "realvisxl" / f"seed_{seed:04d}.png"
            if not dst.exists():
                shutil.copy2(f, dst)
                picked["realvisxl"].append((seed, str(dst)))
        elif m_fl:
            seed = int(m_fl.group(1))
            dst = ROOT / "flux" / f"seed_{seed:04d}.png"
            if not dst.exists():
                shutil.copy2(f, dst)
                picked["flux"].append((seed, str(dst)))
    return picked


def missing():
    miss = {"realvisxl": [], "flux": []}
    for s in ALL_SEEDS:
        if not (ROOT / "realvisxl" / f"seed_{s:04d}.png").exists():
            miss["realvisxl"].append(s)
        if not (ROOT / "flux" / f"seed_{s:04d}.png").exists():
            miss["flux"].append(s)
    return miss


def main():
    print("== step 1: collect existing ==", flush=True)
    picked = collect_existing()
    for k, v in picked.items():
        print(f"  {k}: picked {len(v)} -> {v}", flush=True)

    miss = missing()
    print(f"\n== step 2: missing ==", flush=True)
    print(f"  realvisxl: {miss['realvisxl']}", flush=True)
    print(f"  flux: {miss['flux']}", flush=True)

    if not miss["realvisxl"] and not miss["flux"]:
        print("nothing to do", flush=True)
        return

    # 先等 ComfyUI 当前 pending 跑完（防止撞车）
    print("\n== step 3: wait ComfyUI queue drain ==", flush=True)
    while True:
        r = subprocess.run(
            ["curl", "-fsS", f"{API}/queue"],
            capture_output=True, text=True, timeout=5
        )
        if r.returncode == 0:
            d = json.loads(r.stdout)
            if not d.get("queue_running") and not d.get("queue_pending"):
                print("  queue empty", flush=True)
                break
            print(f"  running={len(d['queue_running'])} pending={len(d['queue_pending'])}, wait 5s...", flush=True)
        time.sleep(5)

    # 跑缺的
    print("\n== step 4: submit missing ==", flush=True)
    results = []
    for model_key, seeds in miss.items():
        builder = m.build_realvisxl_workflow if model_key == "realvisxl" else m.build_flux_workflow
        timeout_sec = 900 if model_key == "flux" else 600
        for seed in seeds:
            client_id = f"fill-{model_key}-{seed}-{uuid.uuid4().hex[:6]}"
            wf = builder(seed)
            try:
                pid = m.submit(wf, client_id)
                print(f"  submitted {model_key} seed={seed} -> {pid[:8]}", flush=True)
                t0 = time.time()
                hist = m.wait_done(pid, timeout_sec=timeout_sec)
                elapsed = time.time() - t0
                copied = []
                for node_out in hist.get("outputs", {}).values():
                    if "images" in node_out:
                        for img in node_out["images"]:
                            fname = img.get("filename", "")
                            src = RAW_OUT / fname
                            if src.exists():
                                dst = ROOT / model_key / f"seed_{seed:04d}.png"
                                shutil.copy2(src, dst)
                                copied.append(str(dst))
                rec = {"model": model_key, "seed": seed,
                       "elapsed_sec": round(elapsed, 2),
                       "outputs": copied, "status": "ok" if copied else "no_output"}
                print(f"  done {model_key} seed={seed} {elapsed:.1f}s", flush=True)
            except Exception as e:
                rec = {"model": model_key, "seed": seed, "status": "error", "error": str(e)}
                print(f"  ERROR {model_key} seed={seed}: {e}", flush=True)
            results.append(rec)
            time.sleep(1)

    # 写入补跑结果
    fill_path = ROOT / "fill_report.json"
    with open(fill_path, "w") as f:
        json.dump(results, f, indent=2, ensure_ascii=False)

    print(f"\n== step 5: final status ==", flush=True)
    final_miss = missing()
    print(f"  realvisxl missing: {final_miss['realvisxl']}", flush=True)
    print(f"  flux missing: {final_miss['flux']}", flush=True)
    print(f"  total in project: realvisxl={len(list((ROOT/'realvisxl').glob('*.png')))} flux={len(list((ROOT/'flux').glob('*.png')))}", flush=True)


if __name__ == "__main__":
    main()
