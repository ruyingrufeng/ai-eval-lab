#!/usr/bin/env python3
"""Compare FLUX.1-dev 20-step and FLUX.1-schnell 4-step on three scenes."""

from __future__ import annotations

import json
import shutil
import time
import urllib.request
import uuid
from datetime import datetime
from pathlib import Path


API = "http://127.0.0.1:8188"
OPENER = urllib.request.build_opener(urllib.request.ProxyHandler({}))
COMFY_OUTPUT = Path("/Users/jacky/ComfyUI/output")
PROJECT = Path(__file__).resolve().parents[1]
ROOT = PROJECT / "results/performance/flux-schnell-eval-20260814"
SEED = 2026081201
MODELS = {
    "dev20": ("flux1-dev-Q4_K_S.gguf", 20),
    "schnell4": ("flux1-schnell-Q4_K_S.gguf", 4),
}
SCENES = {
    "editorial_fullbody": {
        "width": 768, "height": 1024,
        "prompt": (
            "professional editorial photograph of one fictional adult woman age 30, full body visible head to toe, "
            "standing beside a modern red armchair in a bright minimalist studio, wearing an opaque emerald green "
            "long-sleeve jumpsuit and black ankle boots, holding a closed yellow notebook in her left hand, "
            "a tall leafy plant on the right side, soft daylight from the left, realistic skin texture, natural anatomy, "
            "balanced composition, accurate green red yellow color separation, sharp photographic detail"
        ),
    },
    "closeup_portrait": {
        "width": 768, "height": 1024,
        "prompt": (
            "professional close-up editorial portrait photograph of one fictional adult woman age 30, shoulders and head, "
            "looking directly at camera, natural symmetrical facial features, realistic skin pores and subtle freckles, "
            "dark brown wavy hair, opaque navy blazer over a white shirt, soft window light from the left, neutral warm gray "
            "studio background, 85mm lens look, shallow depth of field, eyes in sharp focus, no text, no watermark"
        ),
    },
    "wide_environment": {
        "width": 1024, "height": 576,
        "prompt": (
            "cinematic wide photograph of one fictional adult woman age 30 walking through a modern glass railway station, "
            "full body visible, wearing a long mustard yellow coat and black trousers, carrying a red travel bag, repeating "
            "steel beams and glass roof, morning sunlight casting long diagonal shadows, a blue train in the background, "
            "accurate perspective, natural anatomy, realistic materials, balanced composition, sharp photographic detail"
        ),
    },
}


def request_json(path: str, payload: dict | None = None, timeout: int = 30) -> dict:
    url = f"{API}{path}"
    if payload is None:
        with OPENER.open(url, timeout=timeout) as response:
            return json.loads(response.read())
    request = urllib.request.Request(url, data=json.dumps(payload).encode(), headers={"Content-Type": "application/json"})
    with OPENER.open(request, timeout=timeout) as response:
        return json.loads(response.read())


def workflow(model_name: str, steps: int, scene: dict, prefix: str) -> dict:
    return {
        "1": {"class_type": "UnetLoaderGGUF", "inputs": {"unet_name": model_name}},
        "2": {"class_type": "DualCLIPLoaderGGUF", "inputs": {
            "clip_name1": "clip_l.safetensors", "clip_name2": "t5-v1_1-xxl-encoder-Q5_K_M.gguf", "type": "flux",
        }},
        "3": {"class_type": "VAELoader", "inputs": {"vae_name": "ae.safetensors"}},
        "4": {"class_type": "CLIPTextEncode", "inputs": {"clip": ["2", 0], "text": scene["prompt"]}},
        "5": {"class_type": "CLIPTextEncode", "inputs": {"clip": ["2", 0], "text": ""}},
        "6": {"class_type": "EmptyLatentImage", "inputs": {
            "width": scene["width"], "height": scene["height"], "batch_size": 1,
        }},
        "7": {"class_type": "KSampler", "inputs": {
            "model": ["1", 0], "seed": SEED, "steps": steps, "cfg": 1.0, "sampler_name": "euler",
            "scheduler": "simple", "positive": ["4", 0], "negative": ["5", 0],
            "latent_image": ["6", 0], "denoise": 1.0,
        }},
        "8": {"class_type": "VAEDecode", "inputs": {"samples": ["7", 0], "vae": ["3", 0]}},
        "9": {"class_type": "SaveImage", "inputs": {"filename_prefix": prefix, "images": ["8", 0]}},
    }


def run_one(model_id: str, scene_id: str) -> dict:
    model_name, steps = MODELS[model_id]
    scene = SCENES[scene_id]
    graph = workflow(model_name, steps, scene, f"flux_schnell_eval/{model_id}_{scene_id}")
    (ROOT / f"{model_id}_{scene_id}_workflow.json").write_text(json.dumps(graph, ensure_ascii=False, indent=2) + "\n")
    started = time.monotonic()
    response = request_json("/prompt", {"prompt": graph, "client_id": str(uuid.uuid4())})
    if response.get("error") or response.get("node_errors"):
        raise RuntimeError(json.dumps(response, ensure_ascii=False))
    prompt_id = response["prompt_id"]
    item = None
    while time.monotonic() - started < 1800:
        time.sleep(1)
        item = request_json(f"/history/{prompt_id}").get(prompt_id)
        if not item:
            continue
        status = item.get("status", {})
        if status.get("status_str") == "error":
            raise RuntimeError(json.dumps(status, ensure_ascii=False))
        if status.get("completed") or status.get("status_str") == "success":
            break
    else:
        raise TimeoutError(prompt_id)
    images = [image for output in item.get("outputs", {}).values() for image in output.get("images", [])]
    if not images:
        raise RuntimeError("completed without image")
    image = images[0]
    source = COMFY_OUTPUT / image.get("subfolder", "") / image["filename"]
    destination = ROOT / f"{model_id}_{scene_id}.png"
    shutil.copy2(source, destination)
    elapsed = round(time.monotonic() - started, 2)
    return {
        "model": model_id, "model_file": model_name, "scene": scene_id, "steps": steps,
        "width": scene["width"], "height": scene["height"], "seed": SEED,
        "elapsed_seconds": elapsed, "prompt_id": prompt_id, "output": str(destination), "status": "completed",
    }


def main() -> None:
    ROOT.mkdir(parents=True, exist_ok=True)
    baseline = PROJECT / "results/performance/flux-speed-default-20260813/dev20_768x1024.png"
    baseline_copy = ROOT / "dev20_editorial_fullbody.png"
    shutil.copy2(baseline, baseline_copy)
    report = {
        "schema_version": 1, "run_id": ROOT.name,
        "recorded_at": datetime.now().astimezone().isoformat(timespec="seconds"),
        "seed": SEED, "system_stats": request_json("/system_stats"), "scenes": SCENES,
        "results": [{
            "model": "dev20", "model_file": MODELS["dev20"][0], "scene": "editorial_fullbody",
            "steps": 20, "width": 768, "height": 1024, "seed": SEED, "elapsed_seconds": 350.87,
            "output": str(baseline_copy), "status": "reused_identical_baseline",
        }],
    }
    order = [
        ("schnell4", "editorial_fullbody"),
        ("dev20", "closeup_portrait"), ("schnell4", "closeup_portrait"),
        ("dev20", "wide_environment"), ("schnell4", "wide_environment"),
    ]
    for model_id, scene_id in order:
        result = run_one(model_id, scene_id)
        report["results"].append(result)
        (ROOT / "report.json").write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n")
        print(json.dumps(result, ensure_ascii=False), flush=True)


if __name__ == "__main__":
    main()
