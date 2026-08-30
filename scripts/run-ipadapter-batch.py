#!/usr/bin/env python3
"""IP-Adapter 锁脸批量跑图（夜间无人值守版）。

策略：
  - 启动前检查内存（避免与 27B 撞车）
  - 失败重试 2 次
  - 全程打进度日志到 /tmp/ipadapter_batch.log
  - 完成后写 fill_report.json + 自动归档到项目目录

使用方法：
  python3 run-ipadapter-batch.py [--dry-run] [--include-realvisxl]

默认只运行 Flux；RealVisXL 保留但必须显式启用。
"""
import argparse
import json
import subprocess
import sys
import time
import uuid
import shutil
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
from build_ipadapter_workflow import build_realvisxl_ipadapter_workflow, build_flux_ipadapter_workflow

API = "http://127.0.0.1:8188"
SEEDS = [1, 2, 3, 7, 11, 42, 123, 456, 789, 2026]
DEFAULT_REF_IMAGE = "/Users/jacky/Documents/ChatGPT/内容工厂管理/results/aesthetic/20260812-blind/flux/seed_0007.png"
ROOT = Path("/Users/jacky/Documents/ChatGPT/内容工厂管理/results/aesthetic/20260812-ipadapter")
RAW_OUT = Path("/Users/jacky/ComfyUI/output")


def check_memory_free_pct() -> float:
    """检查系统内存 free 百分比。低于 40% 拒绝启动。"""
    r = subprocess.run(["memory_pressure", "-Q"], capture_output=True, text=True, timeout=5)
    for line in r.stdout.splitlines():
        if "System-wide memory free percentage" in line:
            pct = float(line.split(":")[1].strip().rstrip("%"))
            return pct
    return -1.0


def comfy_health() -> bool:
    """检查 ComfyUI 8188 是否在线。"""
    r = subprocess.run(["curl", "-fsS", "--max-time", "3",
                        f"{API}/system_stats"],
                       capture_output=True, timeout=5)
    return r.returncode == 0


def submit(wf: dict, client_id: str, max_retry: int = 2) -> str:
    """提交 workflow 到 ComfyUI 队列。失败重试 max_retry 次。"""
    payload = json.dumps({"prompt": wf, "client_id": client_id})
    last_err = "unknown"
    for attempt in range(max_retry + 1):
        r: subprocess.CompletedProcess = subprocess.run(
            ["curl", "-fsS", "-X", "POST", f"{API}/prompt",
             "-H", "Content-Type: application/json",
             "-d", payload],
            capture_output=True, text=True, timeout=15,
        )
        if r.returncode == 0:
            return json.loads(r.stdout)["prompt_id"]
        last_err = r.stderr or "no stderr"
        if attempt < max_retry:
            print(f"  retry {attempt+1}/{max_retry}...", flush=True)
            time.sleep(3)
    raise RuntimeError(f"submit failed after {max_retry+1} attempts: {last_err}")


def wait_done(prompt_id: str, timeout_sec: int = 900,
              progress_cb=None) -> dict:
    """等 ComfyUI 完成 history entry。"""
    deadline = time.time() + timeout_sec
    while time.time() < deadline:
        r = subprocess.run(
            ["curl", "-fsS", f"{API}/history/{prompt_id}"],
            capture_output=True, text=True, timeout=10,
        )
        if r.returncode == 0:
            hist = json.loads(r.stdout)
            if prompt_id in hist:
                return hist[prompt_id]
        if progress_cb:
            progress_cb()
        time.sleep(2)
    raise TimeoutError(f"timeout {prompt_id}")


def collect_outputs(history: dict, model_key: str, seed: int) -> list:
    """从 history 收集图，拷到项目目录。"""
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
    parser.add_argument("--dry-run", action="store_true",
                        help="只检查环境，不实际跑")
    parser.add_argument("--reference", default=DEFAULT_REF_IMAGE,
                        help=f"参考脸图路径（默认 Flux seed 7）")
    parser.add_argument("--include-realvisxl", action="store_true",
                        help="显式启用已退出默认生产路线的 RealVisXL 对照组")
    parser.add_argument("--skip-flux", action="store_true")
    args = parser.parse_args()

    # 前置检查
    print("=== 前置检查 ===", flush=True)
    free_pct = check_memory_free_pct()
    print(f"  memory free: {free_pct}%", flush=True)
    if free_pct < 40:
        print(f"  ❌ 内存不足（<40%），拒绝启动。释放内存或先 kill 大模型。",
              flush=True)
        sys.exit(1)

    if not comfy_health():
        print(f"  ❌ ComfyUI 8188 不在线。请先启 ComfyUI：", flush=True)
        print(f"     ~/ComfyUI/.venv/bin/python ~/ComfyUI/main.py --listen 127.0.0.1 --port 8188 \\",
              flush=True)
        print(f"         --disable-auto-launch --preview-method none --cache-none \\", flush=True)
        print(f"         --output-directory /Users/jacky/ComfyUI/output --log-stdout &", flush=True)
        sys.exit(1)
    print(f"  ✅ ComfyUI online", flush=True)

    ref_img = args.reference
    if not Path(ref_img).exists():
        print(f"  ❌ 参考图不存在: {ref_img}", flush=True)
        sys.exit(1)
    print(f"  ✅ reference: {ref_img}", flush=True)

    if args.dry_run:
        print(f"\n  DRY RUN: 不实际跑图。删除 --dry-run 真正执行。", flush=True)
        sys.exit(0)

    # 创建目录
    for sub in (["flux", "realvisxl"] if args.include_realvisxl else ["flux"]):
        (ROOT / sub).mkdir(parents=True, exist_ok=True)

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
        # Flux 更慢，timeout 给更久
        timeout = 1800 if model_key == "flux" else 600

        for seed in SEEDS:
            # 跳过已存在的
            dst = ROOT / model_key / f"seed_{seed:04d}.png"
            if dst.exists():
                print(f"  seed {seed:>4}  skip (exists)", flush=True)
                continue

            client_id = f"ipa-{model_key}-{seed}-{uuid.uuid4().hex[:6]}"
            try:
                wf = builder(ref_img, seed)
                pid = submit(wf, client_id)
                print(f"  seed {seed:>4}  submitted {pid[:8]}", flush=True)
                t0 = time.time()
                # Flux 后段会变慢，单图 ~5 分钟，给 timeout 1800
                hist = wait_done(pid, timeout_sec=timeout)
                elapsed = time.time() - t0
                copied = collect_outputs(hist, model_key, seed)
                rec = {"model": model_key, "seed": seed,
                       "elapsed_sec": round(elapsed, 2),
                       "outputs": copied,
                       "status": "ok" if copied else "no_output"}
                print(f"  seed {seed:>4}  done {elapsed:6.1f}s  copied={len(copied)}",
                      flush=True)
            except Exception as e:
                rec = {"model": model_key, "seed": seed,
                       "status": "error", "error": str(e)}
                print(f"  seed {seed:>4}  ERROR: {e}", flush=True)
            results.append(rec)
            time.sleep(1)

    # 写报告
    report_path = ROOT / "fill_report.json"
    with open(report_path, "w") as f:
        json.dump(results, f, indent=2, ensure_ascii=False)

    ok = sum(1 for r in results if r["status"] == "ok")
    print(f"\n=== 完成 ===", flush=True)
    print(f"  {ok}/{len(results)} ok", flush=True)
    print(f"  report: {report_path}", flush=True)
    print(f"  images: {ROOT}/{{realvisxl,flux}}/", flush=True)


if __name__ == "__main__":
    main()
