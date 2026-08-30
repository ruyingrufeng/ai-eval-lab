#!/usr/bin/env python3
"""Submit identical ComfyUI jobs concurrently and measure queue behaviour."""

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
ROOT = Path(__file__).resolve().parents[1]
WIDTH, HEIGHT = 768, 1024
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
        with OPENER.open(url, timeout=timeout) as response:
            return json.loads(response.read())
    request = urllib.request.Request(url, data=json.dumps(payload).encode(), headers={"Content-Type": "application/json"})
    with OPENER.open(request, timeout=timeout) as response:
        return json.loads(response.read())


def workflow(model: str, prefix: str, seed: int) -> dict:
    if model == "realvisxl_v5":
        return {
            "1": {"class_type": "CheckpointLoaderSimple", "inputs": {"ckpt_name": "RealVisXL_V5.0_fp16.safetensors"}},
            "2": {"class_type": "CLIPTextEncode", "inputs": {"clip": ["1", 1], "text": POSITIVE}},
            "3": {"class_type": "CLIPTextEncode", "inputs": {"clip": ["1", 1], "text": NEGATIVE}},
            "4": {"class_type": "EmptyLatentImage", "inputs": {"width": WIDTH, "height": HEIGHT, "batch_size": 1}},
            "5": {"class_type": "KSampler", "inputs": {"model": ["1", 0], "seed": seed, "steps": 25, "cfg": 6.5, "sampler_name": "dpmpp_2m_sde", "scheduler": "karras", "positive": ["2", 0], "negative": ["3", 0], "latent_image": ["4", 0], "denoise": 1.0}},
            "6": {"class_type": "VAEDecode", "inputs": {"samples": ["5", 0], "vae": ["1", 2]}},
            "7": {"class_type": "SaveImage", "inputs": {"filename_prefix": prefix, "images": ["6", 0]}},
        }
    if model == "flux1_dev_q4":
        return {
            "1": {"class_type": "UnetLoaderGGUF", "inputs": {"unet_name": "flux1-dev-Q4_K_S.gguf"}},
            "2": {"class_type": "DualCLIPLoaderGGUF", "inputs": {"clip_name1": "clip_l.safetensors", "clip_name2": "t5-v1_1-xxl-encoder-Q5_K_M.gguf", "type": "flux"}},
            "3": {"class_type": "VAELoader", "inputs": {"vae_name": "ae.safetensors"}},
            "4": {"class_type": "CLIPTextEncode", "inputs": {"clip": ["2", 0], "text": POSITIVE}},
            "5": {"class_type": "CLIPTextEncode", "inputs": {"clip": ["2", 0], "text": ""}},
            "6": {"class_type": "EmptyLatentImage", "inputs": {"width": WIDTH, "height": HEIGHT, "batch_size": 1}},
            "7": {"class_type": "KSampler", "inputs": {"model": ["1", 0], "seed": seed, "steps": 20, "cfg": 1.0, "sampler_name": "euler", "scheduler": "simple", "positive": ["4", 0], "negative": ["5", 0], "latent_image": ["6", 0], "denoise": 1.0}},
            "8": {"class_type": "VAEDecode", "inputs": {"samples": ["7", 0], "vae": ["3", 0]}},
            "9": {"class_type": "SaveImage", "inputs": {"filename_prefix": prefix, "images": ["8", 0]}},
        }
    raise ValueError(model)


def event_times(item: dict) -> tuple[float | None, float | None]:
    execution_start = None
    execution_end = None
    for message in item.get("status", {}).get("messages", []):
        if not isinstance(message, list) or len(message) < 2 or not isinstance(message[1], dict):
            continue
        timestamp = message[1].get("timestamp")
        if timestamp is None:
            continue
        seconds = float(timestamp) / 1000.0
        if message[0] == "execution_start":
            execution_start = seconds
        elif message[0] in ("execution_success", "execution_error"):
            execution_end = seconds
    return execution_start, execution_end


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--model", choices=["realvisxl_v5", "flux1_dev_q4"], required=True)
    parser.add_argument("--concurrency", type=int, choices=[1, 2, 4], required=True)
    parser.add_argument("--run-id", required=True)
    args = parser.parse_args()
    output_dir = ROOT / "results" / "performance" / args.run_id
    output_dir.mkdir(parents=True, exist_ok=True)
    if (output_dir / "report.json").exists():
        raise FileExistsError(output_dir / "report.json")
    run_start_epoch = time.time()
    jobs = []
    for index in range(args.concurrency):
        seed = 2026081210 + index
        graph = workflow(args.model, f"content_factory/{args.run_id}/{args.model}_{index + 1}", seed)
        (output_dir / f"workflow_{index + 1}.json").write_text(json.dumps(graph, ensure_ascii=False, indent=2) + "\n")
        submitted_epoch = time.time()
        response = request_json("/prompt", {"prompt": graph, "client_id": str(uuid.uuid4())})
        if response.get("error") or response.get("node_errors"):
            raise RuntimeError(json.dumps(response, ensure_ascii=False))
        jobs.append({"index": index + 1, "seed": seed, "prompt_id": response["prompt_id"], "submitted_epoch": submitted_epoch})

    pending = {job["prompt_id"] for job in jobs}
    history = {}
    while pending and time.time() - run_start_epoch < 3600:
        time.sleep(1)
        for prompt_id in list(pending):
            item = request_json(f"/history/{prompt_id}").get(prompt_id)
            if not item:
                continue
            status = item.get("status", {})
            if status.get("completed") or status.get("status_str") in ("success", "error"):
                history[prompt_id] = item
                pending.remove(prompt_id)
    if pending:
        raise TimeoutError(sorted(pending))

    results = []
    for job in jobs:
        item = history[job["prompt_id"]]
        start_epoch, end_epoch = event_times(item)
        end_epoch = end_epoch or time.time()
        images = []
        for output in item.get("outputs", {}).values():
            images.extend(output.get("images", []))
        destination = None
        if images:
            image = images[0]
            source = COMFY_OUTPUT / image.get("subfolder", "") / image["filename"]
            destination = output_dir / f"output_{job['index']}.png"
            shutil.copy2(source, destination)
        results.append({
            **job,
            "execution_start_epoch": start_epoch,
            "execution_end_epoch": end_epoch,
            "queue_wait_seconds": round((start_epoch or end_epoch) - job["submitted_epoch"], 3),
            "execution_seconds": round(end_epoch - (start_epoch or job["submitted_epoch"]), 3),
            "end_to_end_seconds": round(end_epoch - job["submitted_epoch"], 3),
            "status": item.get("status", {}).get("status_str"),
            "output": str(destination) if destination else None,
        })
    wall_seconds = round(max(result["execution_end_epoch"] for result in results) - run_start_epoch, 3)
    report = {
        "schema_version": 1,
        "run_id": args.run_id,
        "recorded_at": datetime.now().astimezone().isoformat(timespec="seconds"),
        "model": args.model,
        "level": "C0" if args.concurrency == 1 else ("C1" if args.concurrency == 2 else "C2"),
        "concurrency_submitted": args.concurrency,
        "wall_seconds": wall_seconds,
        "throughput_jobs_per_minute": round(args.concurrency / wall_seconds * 60, 4),
        "jobs": results,
    }
    (output_dir / "report.json").write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n")
    print(json.dumps(report, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
