#!/usr/bin/env python3
"""Benchmark Flux step count and resolution through the local ComfyUI API."""

from __future__ import annotations

import argparse
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
PROMPT = (
    "professional editorial photograph of one fictional adult woman age 30, full body visible head to toe, "
    "standing beside a modern red armchair in a bright minimalist studio, wearing an opaque emerald green "
    "long-sleeve jumpsuit and black ankle boots, holding a closed yellow notebook in her left hand, "
    "a tall leafy plant on the right side, soft daylight from the left, realistic skin texture, natural anatomy, "
    "balanced composition, accurate green red yellow color separation, sharp photographic detail"
)


def request_json(path: str, payload: dict | None = None, timeout: int = 30) -> dict:
    url = f"{API}{path}"
    if payload is None:
        with OPENER.open(url, timeout=timeout) as response:
            return json.loads(response.read())
    request = urllib.request.Request(
        url,
        data=json.dumps(payload).encode(),
        headers={"Content-Type": "application/json"},
    )
    with OPENER.open(request, timeout=timeout) as response:
        return json.loads(response.read())


def workflow(prefix: str, steps: int, width: int, height: int, seed: int) -> dict:
    return {
        "1": {"class_type": "UnetLoaderGGUF", "inputs": {"unet_name": "flux1-dev-Q4_K_S.gguf"}},
        "2": {"class_type": "DualCLIPLoaderGGUF", "inputs": {
            "clip_name1": "clip_l.safetensors", "clip_name2": "t5-v1_1-xxl-encoder-Q5_K_M.gguf", "type": "flux",
        }},
        "3": {"class_type": "VAELoader", "inputs": {"vae_name": "ae.safetensors"}},
        "4": {"class_type": "CLIPTextEncode", "inputs": {"clip": ["2", 0], "text": PROMPT}},
        "5": {"class_type": "CLIPTextEncode", "inputs": {"clip": ["2", 0], "text": ""}},
        "6": {"class_type": "EmptyLatentImage", "inputs": {"width": width, "height": height, "batch_size": 1}},
        "7": {"class_type": "KSampler", "inputs": {
            "model": ["1", 0], "seed": seed, "steps": steps, "cfg": 1.0,
            "sampler_name": "euler", "scheduler": "simple", "positive": ["4", 0],
            "negative": ["5", 0], "latent_image": ["6", 0], "denoise": 1.0,
        }},
        "8": {"class_type": "VAEDecode", "inputs": {"samples": ["7", 0], "vae": ["3", 0]}},
        "9": {"class_type": "SaveImage", "inputs": {"filename_prefix": prefix, "images": ["8", 0]}},
    }


def run_variant(label: str, steps: int, width: int, height: int, seed: int, output_dir: Path) -> dict:
    graph = workflow(f"flux_speed/{output_dir.name}/{label}", steps, width, height, seed)
    (output_dir / f"{label}_workflow_api.json").write_text(json.dumps(graph, ensure_ascii=False, indent=2) + "\n")
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
        raise RuntimeError(f"{label}: completed without an image")
    image = images[0]
    source = COMFY_OUTPUT / image.get("subfolder", "") / image["filename"]
    destination = output_dir / f"{label}.png"
    shutil.copy2(source, destination)
    elapsed = round(time.monotonic() - started, 2)
    return {
        "label": label, "steps": steps, "width": width, "height": height, "seed": seed,
        "elapsed_seconds": elapsed, "seconds_per_step": round(elapsed / steps, 2),
        "prompt_id": prompt_id, "output": str(destination), "status": "completed",
    }


def parse_variant(value: str) -> tuple[str, int, int, int]:
    label, steps, width, height = value.split(":")
    return label, int(steps), int(width), int(height)


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--run-id", required=True)
    parser.add_argument("--server-mode", required=True)
    parser.add_argument("--seed", type=int, default=2026081201)
    parser.add_argument("--variant", action="append", required=True, type=parse_variant)
    args = parser.parse_args()
    output_dir = PROJECT / "results" / "performance" / args.run_id
    output_dir.mkdir(parents=True, exist_ok=False)
    report = {
        "schema_version": 1, "run_id": args.run_id, "recorded_at": datetime.now().astimezone().isoformat(timespec="seconds"),
        "server_mode": args.server_mode, "seed": args.seed, "prompt": PROMPT,
        "system_stats": request_json("/system_stats"), "results": [],
    }
    for label, steps, width, height in args.variant:
        result = run_variant(label, steps, width, height, args.seed, output_dir)
        report["results"].append(result)
        (output_dir / "report.json").write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n")
        print(json.dumps(result, ensure_ascii=False), flush=True)


if __name__ == "__main__":
    main()
