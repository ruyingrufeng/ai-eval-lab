#!/usr/bin/env python3
"""Re-test installed RealVisXL and Flux Q4 through the local ComfyUI API."""

from __future__ import annotations

import argparse
import json
import os
import shutil
import subprocess
import time
import urllib.request
import uuid
from datetime import datetime
from pathlib import Path


API = "http://127.0.0.1:8188"
URL_OPENER = urllib.request.build_opener(urllib.request.ProxyHandler({}))
COMFY_OUTPUT = Path("/Users/jacky/ComfyUI/output")
ROOT = Path(__file__).resolve().parents[1]
WIDTH, HEIGHT, SEED = 768, 1024, 2026081201
POSITIVE = (
    "professional editorial photograph of one fictional adult woman age 30, full body visible head to toe, "
    "standing beside a modern red armchair in a bright minimalist studio, wearing an opaque emerald green "
    "long-sleeve jumpsuit and black ankle boots, holding a closed yellow notebook in her left hand, "
    "a tall leafy plant on the right side, soft daylight from the left, realistic skin texture, natural anatomy, "
    "balanced composition, accurate green red yellow color separation, sharp photographic detail"
)
NEGATIVE = (
    "child, teenager, underage, age ambiguous, nude, transparent clothing, sexual content, violence, blood, "
    "multiple people, duplicate person, cropped feet, extra limbs, malformed hands, text, watermark, logo, "
    "anime, illustration, 3d render, oversaturated, blurry, low quality"
)


def request_json(path: str, payload: dict | None = None, timeout: int = 30) -> dict:
    url = f"{API}{path}"
    if payload is None:
        with URL_OPENER.open(url, timeout=timeout) as response:
            return json.loads(response.read())
    request = urllib.request.Request(
        url,
        data=json.dumps(payload).encode(),
        headers={"Content-Type": "application/json"},
    )
    with URL_OPENER.open(request, timeout=timeout) as response:
        return json.loads(response.read())


def realvis_workflow(prefix: str) -> dict:
    return {
        "1": {"class_type": "CheckpointLoaderSimple", "inputs": {"ckpt_name": "RealVisXL_V5.0_fp16.safetensors"}},
        "2": {"class_type": "CLIPTextEncode", "inputs": {"clip": ["1", 1], "text": POSITIVE}},
        "3": {"class_type": "CLIPTextEncode", "inputs": {"clip": ["1", 1], "text": NEGATIVE}},
        "4": {"class_type": "EmptyLatentImage", "inputs": {"width": WIDTH, "height": HEIGHT, "batch_size": 1}},
        "5": {"class_type": "KSampler", "inputs": {
            "model": ["1", 0], "seed": SEED, "steps": 25, "cfg": 6.5,
            "sampler_name": "dpmpp_2m_sde", "scheduler": "karras",
            "positive": ["2", 0], "negative": ["3", 0], "latent_image": ["4", 0], "denoise": 1.0,
        }},
        "6": {"class_type": "VAEDecode", "inputs": {"samples": ["5", 0], "vae": ["1", 2]}},
        "7": {"class_type": "SaveImage", "inputs": {"filename_prefix": prefix, "images": ["6", 0]}},
    }


def flux_workflow(prefix: str) -> dict:
    return {
        "1": {"class_type": "UnetLoaderGGUF", "inputs": {"unet_name": "flux1-dev-Q4_K_S.gguf"}},
        "2": {"class_type": "DualCLIPLoaderGGUF", "inputs": {
            "clip_name1": "clip_l.safetensors", "clip_name2": "t5-v1_1-xxl-encoder-Q5_K_M.gguf", "type": "flux",
        }},
        "3": {"class_type": "VAELoader", "inputs": {"vae_name": "ae.safetensors"}},
        "4": {"class_type": "CLIPTextEncode", "inputs": {"clip": ["2", 0], "text": POSITIVE}},
        "5": {"class_type": "CLIPTextEncode", "inputs": {"clip": ["2", 0], "text": ""}},
        "6": {"class_type": "EmptyLatentImage", "inputs": {"width": WIDTH, "height": HEIGHT, "batch_size": 1}},
        "7": {"class_type": "KSampler", "inputs": {
            "model": ["1", 0], "seed": SEED, "steps": 20, "cfg": 1.0,
            "sampler_name": "euler", "scheduler": "simple",
            "positive": ["4", 0], "negative": ["5", 0], "latent_image": ["6", 0], "denoise": 1.0,
        }},
        "8": {"class_type": "VAEDecode", "inputs": {"samples": ["7", 0], "vae": ["3", 0]}},
        "9": {"class_type": "SaveImage", "inputs": {"filename_prefix": prefix, "images": ["8", 0]}},
    }


def rss_mib(pid: int) -> float | None:
    try:
        value = subprocess.check_output(["ps", "-o", "rss=", "-p", str(pid)], text=True).strip()
        return round(int(value) / 1024, 1) if value else None
    except Exception:
        return None


def run_one(model_id: str, workflow: dict, output_dir: Path, comfy_pid: int) -> dict:
    submitted_at = datetime.now().astimezone().isoformat(timespec="seconds")
    started = time.monotonic()
    response = request_json("/prompt", {"prompt": workflow, "client_id": str(uuid.uuid4())})
    if response.get("error") or response.get("node_errors"):
        raise RuntimeError(json.dumps(response, ensure_ascii=False))
    prompt_id = response["prompt_id"]
    peak_rss = rss_mib(comfy_pid)
    history_item = None
    while time.monotonic() - started < 1800:
        time.sleep(2)
        current_rss = rss_mib(comfy_pid)
        if current_rss is not None:
            peak_rss = max(peak_rss or 0, current_rss)
        history_item = request_json(f"/history/{prompt_id}").get(prompt_id)
        if not history_item:
            continue
        status = history_item.get("status", {})
        if status.get("status_str") == "error":
            raise RuntimeError(json.dumps(status, ensure_ascii=False))
        if status.get("completed") or status.get("status_str") == "success":
            break
    else:
        raise TimeoutError(prompt_id)

    images = []
    for node_output in history_item.get("outputs", {}).values():
        images.extend(node_output.get("images", []))
    if not images:
        raise RuntimeError(f"{model_id}: completed without image output")
    image = images[0]
    source = COMFY_OUTPUT / image.get("subfolder", "") / image["filename"]
    destination = output_dir / f"{model_id}.png"
    shutil.copy2(source, destination)
    elapsed = round(time.monotonic() - started, 2)
    return {
        "model_id": model_id,
        "prompt_id": prompt_id,
        "submitted_at": submitted_at,
        "completed_at": datetime.now().astimezone().isoformat(timespec="seconds"),
        "elapsed_seconds": elapsed,
        "peak_comfyui_rss_mib": peak_rss,
        "output": str(destination),
        "source_output": str(source),
        "width": WIDTH,
        "height": HEIGHT,
        "seed": SEED,
        "status": "completed",
    }


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--comfy-pid", type=int, required=True)
    parser.add_argument("--run-id", default=datetime.now().astimezone().strftime("%Y%m%d-%H%M%S"))
    args = parser.parse_args()
    output_dir = ROOT / "results" / "image" / args.run_id
    output_dir.mkdir(parents=True, exist_ok=False)
    system_stats = request_json("/system_stats")
    workflows = {
        "realvisxl_v5": realvis_workflow(f"content_factory/{args.run_id}/realvisxl_v5"),
        "flux1_dev_q4": flux_workflow(f"content_factory/{args.run_id}/flux1_dev_q4"),
    }
    report = {
        "schema_version": 1,
        "run_id": args.run_id,
        "recorded_at": datetime.now().astimezone().isoformat(timespec="seconds"),
        "api": API,
        "comfy_pid": args.comfy_pid,
        "system_stats": system_stats,
        "test": {"positive": POSITIVE, "negative": NEGATIVE, "width": WIDTH, "height": HEIGHT, "seed": SEED},
        "results": [],
    }
    for model_id, workflow in workflows.items():
        (output_dir / f"{model_id}_workflow_api.json").write_text(
            json.dumps(workflow, ensure_ascii=False, indent=2) + "\n"
        )
        try:
            result = run_one(model_id, workflow, output_dir, args.comfy_pid)
        except Exception as exc:
            result = {
                "model_id": model_id,
                "completed_at": datetime.now().astimezone().isoformat(timespec="seconds"),
                "status": "failed",
                "error": repr(exc),
            }
        report["results"].append(result)
        (output_dir / "report.json").write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n")
    print(json.dumps(report, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
