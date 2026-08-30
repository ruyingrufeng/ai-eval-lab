#!/usr/bin/env python3
"""数字人夜跑脚本 4：内容尺度（3 档 × 5 seed，Flux only，无 IP-Adapter）。

档位：casual（家居服）/ fashion（泳衣）/ artistic（艺术性大尺度）
不使用 IP-Adapter——测 Flux 在不同内容尺度下的稳定性和过 prompt 过滤能力
"""
import argparse, json, shutil, subprocess, sys, time, uuid
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
from avatar_prompts import SCALE_TIERS

API = "http://127.0.0.1:8188"
SEEDS = [1, 42, 123, 456, 2026]
ROOT = Path("/Users/jacky/Documents/ChatGPT/内容工厂管理/results/aesthetic/20260812-scale")
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


def _build_flux_scale_workflow(seed, positive, negative=""):
    """Flux 基础 workflow（无 IP-Adapter），用于尺度测试。"""
    import uuid as _uuid
    def nid(): return str(_uuid.uuid4())[:8]
    unet, clip, vae, pos, neg, latent, sampler, decode, save = (nid() for _ in range(9))
    return {
        unet: {"class_type": "UnetLoaderGGUF", "inputs": {"unet_name": "flux1-dev-Q4_K_S.gguf"}},
        clip: {"class_type": "DualCLIPLoaderGGUF",
               "inputs": {"clip_name1": "clip_l.safetensors",
                          "clip_name2": "t5-v1_1-xxl-encoder-Q5_K_M.gguf",
                          "type": "flux"}},
        vae: {"class_type": "VAELoader", "inputs": {"vae_name": "ae.safetensors"}},
        pos: {"class_type": "CLIPTextEncode", "inputs": {"text": positive, "clip": [clip, 0]}},
        neg: {"class_type": "CLIPTextEncode", "inputs": {"text": negative, "clip": [clip, 0]}},
        latent: {"class_type": "EmptyLatentImage", "inputs": {"width": 768, "height": 1024, "batch_size": 1}},
        sampler: {"class_type": "KSampler",
                  "inputs": {"model": [unet, 0], "positive": [pos, 0], "negative": [neg, 0],
                             "latent_image": [latent, 0], "seed": seed,
                             "steps": 20, "cfg": 1.0,
                             "sampler_name": "euler", "scheduler": "simple", "denoise": 1.0}},
        decode: {"class_type": "VAEDecode", "inputs": {"samples": [sampler, 0], "vae": [vae, 0]}},
        save: {"class_type": "SaveImage",
               "inputs": {"images": [decode, 0],
                          "filename_prefix": f"scale_{seed}"}},
    }


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args()

    print("=== 内容尺度盲评（Flux only）===", flush=True)
    if _check_memory() < 40:
        print("  ❌ 内存不足", flush=True); sys.exit(1)
    if not _comfy_health():
        print("  ❌ ComfyUI 不在线", flush=True); sys.exit(1)
    print("  ✅ ready", flush=True)
    if args.dry_run:
        sys.exit(0)

    results = []
    for tier_key, tier in SCALE_TIERS.items():
        (ROOT / tier_key).mkdir(parents=True, exist_ok=True)
        print(f"\n--- {tier['name']} ---", flush=True)
        for seed in SEEDS:
            dst = ROOT / tier_key / f"seed_{seed:04d}.png"
            if dst.exists():
                print(f"  seed {seed:>4}  skip", flush=True)
                continue
            client_id = f"sc-{tier_key}-{seed}-{uuid.uuid4().hex[:6]}"
            try:
                wf = _build_flux_scale_workflow(
                    seed, tier["positive"], tier.get("negative", ""),
                )
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
                rec = {"tier": tier_key, "seed": seed,
                       "elapsed_sec": round(elapsed, 2),
                       "outputs": copied,
                       "status": "ok" if copied else "no_output"}
                print(f"  seed {seed:>4}  done {elapsed:6.1f}s  copied={len(copied)}", flush=True)
            except Exception as e:
                rec = {"tier": tier_key, "seed": seed,
                       "status": "error", "error": str(e)}
                print(f"  seed {seed:>4}  ERROR: {e}", flush=True)
            results.append(rec)
            time.sleep(1)

    report_path = ROOT / "scale_report.json"
    with open(report_path, "w") as f:
        json.dump(results, f, indent=2, ensure_ascii=False)
    ok = sum(1 for r in results if r["status"] == "ok")
    print(f"\n=== 完成 {ok}/{len(results)} ok ===", flush=True)


if __name__ == "__main__":
    main()
