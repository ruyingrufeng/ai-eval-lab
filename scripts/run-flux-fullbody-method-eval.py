#!/usr/bin/env python3
"""One-hour Flux full-body method shootout: 3 methods x 2 shared seeds."""

from __future__ import annotations

import json
import shutil
import subprocess
import sys
import time
import uuid
from datetime import datetime
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
from build_ipadapter_workflow import build_flux_ipadapter_workflow

API = "http://127.0.0.1:8188"
PROJECT = Path(__file__).resolve().parents[1]
ROOT = PROJECT / "results/aesthetic/20260813-flux-fullbody-methods"
RAW_OUT = Path("/Users/jacky/ComfyUI/output")
REFERENCE = PROJECT / "results/aesthetic/20260812-blind/flux/seed_0007.png"
POSE_IMAGE = Path("/Users/jacky/ComfyUI/input/flux_fullbody_openpose_768x1024.png")
SEEDS = [31415, 27182]

BASE_PROMPT = (
    "professional editorial photograph of one fictional adult woman age 30, "
    "full body visible, standing in a bright minimalist studio, wearing an opaque "
    "emerald green long-sleeve jumpsuit and black ankle boots, relaxed symmetrical "
    "standing pose, soft daylight, realistic skin texture, natural anatomy, sharp detail"
)
ENHANCED_PROMPT = (
    "professional editorial long-shot photograph of one fictional adult woman age 30, "
    "strict full-length composition, entire person visible continuously from the top of "
    "her hair to the soles of both boots, both complete feet and all toes inside the frame, "
    "standing upright centered in a bright minimalist studio, camera pulled far back at "
    "waist height, generous empty floor visible below both boots, generous margin above her "
    "head, subject occupies about 65 percent of frame height, wearing an opaque emerald green "
    "long-sleeve jumpsuit and black ankle boots, relaxed symmetrical pose, soft daylight, "
    "realistic skin texture, natural anatomy, commercial fashion catalog quality, no crop, "
    "not a portrait, not a medium shot, not a close-up"
)

METHODS = {
    "a_baseline_prompt": {"prompt": BASE_PROMPT, "pose_condition": False},
    "b_enhanced_prompt": {"prompt": ENHANCED_PROMPT, "pose_condition": False},
    "c_enhanced_flux_openpose": {"prompt": ENHANCED_PROMPT, "pose_condition": True},
}


def submit(workflow: dict, client_id: str) -> str:
    payload = json.dumps({"prompt": workflow, "client_id": client_id})
    result = subprocess.run(
        ["curl", "-fsS", "-X", "POST", f"{API}/prompt", "-H", "Content-Type: application/json", "-d", payload],
        capture_output=True, text=True, timeout=30,
    )
    if result.returncode:
        raise RuntimeError(result.stderr.strip())
    data = json.loads(result.stdout)
    if "error" in data:
        raise RuntimeError(json.dumps(data, ensure_ascii=False))
    return data["prompt_id"]


def wait_done(prompt_id: str, timeout_sec: int = 900) -> dict:
    deadline = time.time() + timeout_sec
    while time.time() < deadline:
        result = subprocess.run(
            ["curl", "-fsS", f"{API}/history/{prompt_id}"],
            capture_output=True, text=True, timeout=15,
        )
        if result.returncode == 0:
            history = json.loads(result.stdout)
            if prompt_id in history:
                return history[prompt_id]
        time.sleep(3)
    raise TimeoutError(prompt_id)


def build(method: str, seed: int) -> dict:
    spec = METHODS[method]
    workflow = build_flux_ipadapter_workflow(str(REFERENCE), seed, ipadapter_weight=0.85)
    positive_id = next(
        node_id for node_id, node in workflow.items()
        if node["class_type"] == "CLIPTextEncode" and node["inputs"].get("text")
    )
    workflow[positive_id]["inputs"]["text"] = spec["prompt"]
    save_id = next(node_id for node_id, node in workflow.items() if node["class_type"] == "SaveImage")
    workflow[save_id]["inputs"]["filename_prefix"] = f"flux_fullbody_eval/{method}_seed{seed}"

    if spec["pose_condition"]:
        load_id = uuid.uuid4().hex[:8]
        cn_loader_id = uuid.uuid4().hex[:8]
        cn_apply_id = uuid.uuid4().hex[:8]
        vae_id = next(node_id for node_id, node in workflow.items() if node["class_type"] == "VAELoader")
        pos_id = next(node_id for node_id, node in workflow.items() if node["class_type"] == "CLIPTextEncode" and node["inputs"].get("text"))
        neg_id = next(node_id for node_id, node in workflow.items() if node["class_type"] == "CLIPTextEncode" and not node["inputs"].get("text"))
        sampler_id = next(node_id for node_id, node in workflow.items() if node["class_type"] == "KSampler")
        pose_input_name = str(POSE_IMAGE.relative_to(Path("/Users/jacky/ComfyUI/input")))
        workflow[load_id] = {"class_type": "LoadImage", "inputs": {"image": pose_input_name}}
        workflow[cn_loader_id] = {
            "class_type": "ControlNetLoader",
            "inputs": {"control_net_name": "flux-union-pro-2/diffusion_pytorch_model.safetensors"},
        }
        workflow[cn_apply_id] = {
            "class_type": "ControlNetApplySD3",
            "inputs": {
                "positive": [pos_id, 0],
                "negative": [neg_id, 0],
                "control_net": [cn_loader_id, 0],
                "vae": [vae_id, 0],
                "image": [load_id, 0],
                "strength": 0.9,
                "start_percent": 0.0,
                "end_percent": 0.65,
            },
        }
        workflow[sampler_id]["inputs"]["positive"] = [cn_apply_id, 0]
        workflow[sampler_id]["inputs"]["negative"] = [cn_apply_id, 1]
    return workflow


def collect(history: dict, target: Path) -> None:
    images = []
    for output in history.get("outputs", {}).values():
        images.extend(output.get("images", []))
    if not images:
        raise RuntimeError("ComfyUI history contains no image output")
    source = RAW_OUT / images[-1].get("subfolder", "") / images[-1]["filename"]
    if not source.exists():
        raise FileNotFoundError(source)
    target.parent.mkdir(parents=True, exist_ok=True)
    shutil.copy2(source, target)


def main() -> None:
    ROOT.mkdir(parents=True, exist_ok=True)
    records = []
    started = datetime.now().astimezone()
    for method in METHODS:
        for seed in SEEDS:
            target = ROOT / method / f"seed_{seed}.png"
            if target.exists():
                records.append({"method": method, "seed": seed, "status": "existing", "output": str(target)})
                print(f"EXISTING {method} seed={seed}", flush=True)
                continue
            print(f"START {method} seed={seed}", flush=True)
            t0 = time.time()
            try:
                prompt_id = submit(build(method, seed), f"fullbody-{method}-{seed}-{uuid.uuid4().hex[:6]}")
                history = wait_done(prompt_id)
                collect(history, target)
                record = {
                    "method": method, "seed": seed, "status": "ok",
                    "elapsed_sec": round(time.time() - t0, 2), "output": str(target),
                }
                print(f"DONE {method} seed={seed} {record['elapsed_sec']}s", flush=True)
            except Exception as exc:
                record = {
                    "method": method, "seed": seed, "status": "error",
                    "elapsed_sec": round(time.time() - t0, 2), "error": repr(exc),
                }
                print(f"ERROR {method} seed={seed}: {exc!r}", flush=True)
            records.append(record)
    payload = {
        "title": "Flux full-body best-method first-round evaluation",
        "started_at": started.isoformat(timespec="seconds"),
        "finished_at": datetime.now().astimezone().isoformat(timespec="seconds"),
        "reference": str(REFERENCE), "pose_image": str(POSE_IMAGE),
        "seeds": SEEDS, "methods": METHODS,
        "controlnet": {
            "model": "Shakker-Labs/FLUX.1-dev-ControlNet-Union-Pro-2.0",
            "file": "/Users/jacky/ComfyUI/models/controlnet/flux-union-pro-2/diffusion_pytorch_model.safetensors",
            "sha256": "9d03f63f36206bab2f36aed5cfedc8693c2881397534e9d5f9ae9a0a41362517",
            "pose_strength": 0.9, "control_end": 0.65,
        },
        "records": records,
    }
    (ROOT / "generation_report.json").write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n")
    print(f"REPORT {ROOT / 'generation_report.json'}", flush=True)


if __name__ == "__main__":
    main()
