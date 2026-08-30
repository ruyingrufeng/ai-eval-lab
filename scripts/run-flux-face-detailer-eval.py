#!/usr/bin/env python3
"""Second-stage Flux face refinement with a face-cropped identity reference."""

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
ROOT = PROJECT / "results/aesthetic/20260813-flux-identity-lock/two_stage_face_2x"
RAW_OUT = Path("/Users/jacky/ComfyUI/output")
FACE_REFERENCE = "/Users/jacky/ComfyUI/input/flux_identity_lock/reference_face.png"
SEEDS = [31415, 27182]
PROMPT = (
    "close-up detailed natural face of the same fictional adult woman from the identity "
    "reference, straight dark brown hair, oval face, soft natural eyebrows, almond brown "
    "eyes, straight nose, natural lips, realistic skin texture, subtle editorial makeup, "
    "photorealistic, preserve head angle and lighting"
)


def curl_json(args: list[str]) -> dict:
    r = subprocess.run(args, capture_output=True, text=True, timeout=30)
    if r.returncode:
        raise RuntimeError(r.stderr.strip())
    return json.loads(r.stdout)


def build(seed: int) -> dict:
    workflow = build_flux_ipadapter_workflow(FACE_REFERENCE, seed, ipadapter_weight=1.0)
    ids = {node["class_type"]: node_id for node_id, node in workflow.items()}
    pos_id = next(i for i, n in workflow.items() if n["class_type"] == "CLIPTextEncode" and n["inputs"].get("text"))
    neg_id = next(i for i, n in workflow.items() if n["class_type"] == "CLIPTextEncode" and not n["inputs"].get("text"))
    workflow[pos_id]["inputs"]["text"] = PROMPT
    base_id, detector_id, detail_id, save_id = [uuid.uuid4().hex[:8] for _ in range(4)]
    workflow[base_id] = {"class_type": "LoadImage", "inputs": {"image": f"flux_identity_lock_2x/base_seed_{seed}.png"}}
    workflow[detector_id] = {"class_type": "UltralyticsDetectorProvider", "inputs": {"model_name": "bbox/face_yolov8m.pt"}}
    workflow[detail_id] = {
        "class_type": "FaceDetailer",
        "inputs": {
            "image": [base_id, 0], "model": [ids["ApplyIPAdapterFlux"], 0], "clip": [ids["DualCLIPLoaderGGUF"], 0],
            "vae": [ids["VAELoader"], 0], "guide_size": 640, "guide_size_for": True, "max_size": 1024,
            "seed": seed + 900000, "steps": 12, "cfg": 1.0, "sampler_name": "euler", "scheduler": "simple",
            "positive": [pos_id, 0], "negative": [neg_id, 0], "denoise": 0.38, "feather": 8,
            "noise_mask": True, "force_inpaint": True, "bbox_threshold": 0.35, "bbox_dilation": 12,
            "bbox_crop_factor": 3.0, "sam_detection_hint": "none", "sam_dilation": 0, "sam_threshold": 0.93,
            "sam_bbox_expansion": 0, "sam_mask_hint_threshold": 0.7, "sam_mask_hint_use_negative": "False",
            "drop_size": 10, "bbox_detector": [detector_id, 0], "wildcard": "", "cycle": 1,
            "noise_mask_feather": 20,
        },
    }
    workflow[save_id] = {"class_type": "SaveImage", "inputs": {"images": [detail_id, 0], "filename_prefix": f"flux_identity_lock/two_stage_2x_seed{seed}"}}
    old_save = ids["SaveImage"]
    del workflow[old_save]
    return workflow


def run(seed: int, target: Path) -> dict:
    payload = json.dumps({"prompt": build(seed), "client_id": f"face-detail-{uuid.uuid4().hex}"})
    data = curl_json(["curl", "-fsS", "-X", "POST", f"{API}/prompt", "-H", "Content-Type: application/json", "-d", payload])
    if "error" in data:
        raise RuntimeError(json.dumps(data, ensure_ascii=False))
    prompt_id = data["prompt_id"]
    deadline = time.time() + 900
    while time.time() < deadline:
        hist = curl_json(["curl", "-fsS", f"{API}/history/{prompt_id}"])
        if prompt_id in hist:
            record = hist[prompt_id]
            images = [im for out in record.get("outputs", {}).values() for im in out.get("images", [])]
            if not images:
                raise RuntimeError("no output image")
            im = images[-1]
            target.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(RAW_OUT / im.get("subfolder", "") / im["filename"], target)
            return record
        time.sleep(3)
    raise TimeoutError(prompt_id)


def main() -> None:
    ROOT.mkdir(parents=True, exist_ok=True)
    started = datetime.now().astimezone()
    records = []
    for seed in SEEDS:
        target = ROOT / f"seed_{seed}.png"
        t0 = time.time()
        print(f"START seed={seed}", flush=True)
        try:
            run(seed, target)
            rec = {"seed": seed, "status": "ok", "elapsed_sec": round(time.time()-t0, 2), "output": str(target)}
            print(f"DONE seed={seed} {rec['elapsed_sec']}s", flush=True)
        except Exception as exc:
            rec = {"seed": seed, "status": "error", "elapsed_sec": round(time.time()-t0, 2), "error": repr(exc)}
            print(f"ERROR seed={seed} {exc!r}", flush=True)
        records.append(rec)
    data = {"title": "Flux two-stage face detail evaluation", "started_at": started.isoformat(timespec="seconds"),
            "finished_at": datetime.now().astimezone().isoformat(timespec="seconds"), "reference_face": FACE_REFERENCE,
            "ipadapter_weight": 1.0, "steps": 12, "denoise": 0.38, "records": records}
    (ROOT / "generation_report.json").write_text(json.dumps(data, ensure_ascii=False, indent=2)+"\n")


if __name__ == "__main__":
    main()
