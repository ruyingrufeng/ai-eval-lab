#!/usr/bin/env python3
"""10-seed 匿名审美盲评生图（RealVisXL V5 + Flux Q4）。

- 沿用 8/12 prompt
- RealVisXL: dpmpp_2m_sde / karras / steps 25 / cfg 6.5（8/12 workflow 一致）
- Flux Q4:   euler / simple / steps 20 / cfg 1.0（rectified flow，必须低 CFG）
- 避开 8/12 已用 seed 2026081201
- 每模型 10 seed，编号匿名
"""
import json
import subprocess
import time
import uuid
import shutil
import random
from pathlib import Path
from datetime import datetime

API = "http://127.0.0.1:8188"
SEEDS = [1, 2, 3, 7, 11, 42, 123, 456, 789, 2026]
WIDTH, HEIGHT = 768, 1024

POSITIVE = (
    "professional editorial photograph of one fictional adult woman age 30, "
    "full body visible head to toe, standing beside a modern red armchair in "
    "a bright minimalist studio, wearing an opaque emerald green long-sleeve "
    "jumpsuit and black ankle boots, holding a closed yellow notebook in her "
    "left hand, a tall leafy plant on the right side, soft daylight from the "
    "left, realistic skin texture, natural anatomy, balanced composition, "
    "accurate green red yellow color separation, sharp photographic detail"
)
NEGATIVE_REALVISXL = (
    "child, teenager, underage, age ambiguous, nude, transparent clothing, "
    "sexual content, violence, blood, multiple people, duplicate person, "
    "cropped feet, extra limbs, malformed hands, text, watermark, logo, "
    "anime, illustration, 3d render, oversaturated, blurry, low quality"
)

# RealVisXL V5 + Flux Q4 各自 workflow（参照 8/12）
REALVISXL_CKPT = "RealVisXL_V5.0_fp16.safetensors"
FLUX_UNET = "flux1-dev-Q4_K_S.gguf"
FLUX_CLIP1 = "clip_l.safetensors"
FLUX_CLIP2 = "t5-v1_1-xxl-encoder-Q5_K_M.gguf"
FLUX_VAE = "ae.safetensors"


def build_realvisxl_workflow(seed: int) -> dict:
    """8/12 RealVisXL workflow 同款：CheckpointLoaderSimple + KSampler(25/6.5/dpmpp_2m_sde/karras)。"""
    return {
        "1": {"class_type": "CheckpointLoaderSimple",
              "inputs": {"ckpt_name": REALVISXL_CKPT}},
        "2": {"class_type": "CLIPTextEncode",
              "inputs": {"text": POSITIVE, "clip": ["1", 1]}},
        "3": {"class_type": "CLIPTextEncode",
              "inputs": {"text": NEGATIVE_REALVISXL, "clip": ["1", 1]}},
        "4": {"class_type": "EmptyLatentImage",
              "inputs": {"width": WIDTH, "height": HEIGHT, "batch_size": 1}},
        "5": {"class_type": "KSampler",
              "inputs": {"model": ["1", 0], "positive": ["2", 0], "negative": ["3", 0],
                         "latent_image": ["4", 0], "seed": seed, "steps": 25,
                         "cfg": 6.5, "sampler_name": "dpmpp_2m_sde",
                         "scheduler": "karras", "denoise": 1.0}},
        "6": {"class_type": "VAEDecode",
              "inputs": {"samples": ["5", 0], "vae": ["1", 2]}},
        "7": {"class_type": "SaveImage",
              "inputs": {"images": ["6", 0],
                         "filename_prefix": f"blind_realvisxl_seed{seed}"}},
    }


def build_flux_workflow(seed: int) -> dict:
    """8/12 Flux workflow 同款：DualCLIPLoaderGGUF + KSampler(20/1.0/euler/simple)。"""
    return {
        "1": {"class_type": "UnetLoaderGGUF", "inputs": {"unet_name": FLUX_UNET}},
        "2": {"class_type": "DualCLIPLoaderGGUF",
              "inputs": {"clip_name1": FLUX_CLIP1, "clip_name2": FLUX_CLIP2, "type": "flux"}},
        "3": {"class_type": "VAELoader", "inputs": {"vae_name": FLUX_VAE}},
        "4": {"class_type": "CLIPTextEncode",
              "inputs": {"text": POSITIVE, "clip": ["2", 0]}},
        "5": {"class_type": "CLIPTextEncode",
              "inputs": {"text": "", "clip": ["2", 0]}},
        "6": {"class_type": "EmptyLatentImage",
              "inputs": {"width": WIDTH, "height": HEIGHT, "batch_size": 1}},
        "7": {"class_type": "KSampler",
              "inputs": {"model": ["1", 0], "positive": ["4", 0], "negative": ["5", 0],
                         "latent_image": ["6", 0], "seed": seed, "steps": 20,
                         "cfg": 1.0, "sampler_name": "euler",
                         "scheduler": "simple", "denoise": 1.0}},
        "8": {"class_type": "VAEDecode", "inputs": {"samples": ["7", 0], "vae": ["3", 0]}},
        "9": {"class_type": "SaveImage",
              "inputs": {"images": ["8", 0],
                         "filename_prefix": f"blind_flux_seed{seed}"}},
    }


def submit(wf: dict, client_id: str) -> str:
    payload = {"prompt": wf, "client_id": client_id}
    r = subprocess.run(
        ["curl", "-fsS", "-X", "POST", f"{API}/prompt",
         "-H", "Content-Type: application/json",
         "-d", json.dumps(payload)],
        capture_output=True, text=True, timeout=15
    )
    if r.returncode != 0:
        raise RuntimeError(f"submit failed rc={r.returncode} stderr={r.stderr} stdout={r.stdout}")
    return json.loads(r.stdout)["prompt_id"]


def wait_done(prompt_id: str, timeout_sec: int = 900) -> dict:
    deadline = time.time() + timeout_sec
    while time.time() < deadline:
        r = subprocess.run(
            ["curl", "-fsS", f"{API}/history/{prompt_id}"],
            capture_output=True, text=True, timeout=10
        )
        if r.returncode == 0:
            hist = json.loads(r.stdout)
            if prompt_id in hist:
                return hist[prompt_id]
        time.sleep(2)
    raise TimeoutError(f"timeout {prompt_id}")


def main():
    ROOT = Path("/Users/jacky/Documents/ChatGPT/内容工厂管理/results/aesthetic/20260812-blind")
    RAW_OUT = Path("/Users/jacky/ComfyUI/output")
    for sub in ["realvisxl", "flux"]:
        (ROOT / sub).mkdir(parents=True, exist_ok=True)

    metadata = {
        "run_id": "20260812-blind",
        "created_at": datetime.now().isoformat(),
        "seeds": SEEDS,
        "width": WIDTH, "height": HEIGHT,
        "prompt": POSITIVE,
        "negative_realvisxl": NEGATIVE_REALVISXL,
        "negative_flux": "(empty - rectified flow, CFG 1.0)",
        "sampler_realvisxl": {"name": "dpmpp_2m_sde", "scheduler": "karras",
                              "steps": 25, "cfg": 6.5},
        "sampler_flux": {"name": "euler", "scheduler": "simple",
                         "steps": 20, "cfg": 1.0},
        "models": {"realvisxl": REALVISXL_CKPT, "flux": FLUX_UNET},
        "results": {},
    }

    raw = []

    for model_key in ["realvisxl", "flux"]:
        builder = build_realvisxl_workflow if model_key == "realvisxl" else build_flux_workflow
        print(f"\n=== {model_key} ===")
        for seed in SEEDS:
            client_id = f"blind-{model_key}-{seed}-{uuid.uuid4().hex[:6]}"
            t0 = time.time()
            try:
                wf = builder(seed)
                pid = submit(wf, client_id)
                hist = wait_done(pid, timeout_sec=900)
                elapsed = time.time() - t0
                # collect outputs
                outputs = hist.get("outputs", {})
                copied = []
                for node_out in outputs.values():
                    if "images" in node_out:
                        for img in node_out["images"]:
                            fname = img.get("filename", "")
                            src = RAW_OUT / fname
                            if src.exists():
                                dst = ROOT / model_key / f"seed_{seed:04d}.png"
                                shutil.copy2(src, dst)
                                copied.append(str(dst.relative_to(ROOT.parent.parent)))
                status = "ok" if copied else "no_output"
                rec = {"model": model_key, "seed": seed,
                       "prompt_id": pid, "elapsed_sec": round(elapsed, 2),
                       "outputs": copied, "status": status}
                print(f"  seed {seed:>4}  {status}  {elapsed:6.1f}s")
            except Exception as e:
                rec = {"model": model_key, "seed": seed,
                       "status": "error", "error": str(e)}
                print(f"  seed {seed:>4}  ERROR: {e}")
            raw.append(rec)
            metadata["results"][f"{model_key}_seed{seed}"] = rec
            time.sleep(1)

    with open(ROOT / "metadata.json", "w") as f:
        json.dump(metadata, f, indent=2, ensure_ascii=False)
    with open(ROOT / "raw_report.json", "w") as f:
        json.dump(raw, f, indent=2, ensure_ascii=False)

    # 盲评编号（杰哥终评时只看 blind_index.json，不看 metadata.json 的真实模型）
    rng = random.Random(42)
    items = [(m, s) for m in ["realvisxl", "flux"] for s in SEEDS]
    rng.shuffle(items)
    blind_index = []
    for idx, (m, s) in enumerate(items, 1):
        blind_index.append({
            "blind_id": f"B{idx:02d}",
            "image": f"{m}/seed_{s:04d}.png",
            "true_model": m, "true_seed": s,
        })
    with open(ROOT / "blind_index.json", "w") as f:
        json.dump(blind_index, f, indent=2, ensure_ascii=False)

    ok_count = sum(1 for r in raw if r["status"] == "ok")
    print(f"\n{ok_count}/{len(raw)} runs ok.  Metadata + blind_index written.")
    print(f"Dir: {ROOT}")


if __name__ == "__main__":
    main()
