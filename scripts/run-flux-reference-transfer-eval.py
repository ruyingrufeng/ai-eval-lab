#!/usr/bin/env python3
"""Compare Dev reference transfer with and without pose control."""

from __future__ import annotations

import argparse
import json
import shutil
import time
import urllib.request
import uuid
from datetime import datetime
from pathlib import Path

from build_ipadapter_workflow import build_flux_ipadapter_workflow


API = "http://127.0.0.1:8188"
OPENER = urllib.request.build_opener(urllib.request.ProxyHandler({}))
PROJECT = Path(__file__).resolve().parents[1]
COMFY_OUTPUT = Path("/Users/jacky/ComfyUI/output")
DEFAULT_REFERENCE = PROJECT / "results/performance/flux-p0-closure-20260814/fast/seed_910001.png"
DEFAULT_BASELINE = PROJECT / "results/performance/flux-p0-closure-20260814/quality/seed_910001.png"
DEFAULT_ROOT = PROJECT / "results/performance/flux-reference-transfer-20260814"

PROMPT = (
    "full-body editorial photograph of a fictional adult woman age 30, standing naturally "
    "in a modern daylight studio, entire figure visible from head to shoes, realistic face, "
    "natural skin texture, anatomically correct hands, balanced proportions, neutral wardrobe, "
    "clean background, commercial photography"
)


def request_json(path: str, payload: dict | None = None, timeout: int = 30) -> dict:
    url = f"{API}{path}"
    if payload is None:
        with OPENER.open(url, timeout=timeout) as response:
            return json.loads(response.read())
    request = urllib.request.Request(
        url, data=json.dumps(payload).encode(), headers={"Content-Type": "application/json"},
    )
    with OPENER.open(request, timeout=timeout) as response:
        return json.loads(response.read())


def find_node(workflow: dict, class_type: str, *, text_truthy: bool | None = None) -> str:
    for node_id, node in workflow.items():
        if node["class_type"] != class_type:
            continue
        if text_truthy is not None and bool(node["inputs"].get("text")) != text_truthy:
            continue
        return node_id
    raise KeyError(class_type)


def build(reference: Path, seed: int, method: str) -> tuple[dict, str, str | None]:
    workflow = build_flux_ipadapter_workflow(str(reference), seed, ipadapter_weight=0.85, mode="quality")
    positive_id = find_node(workflow, "CLIPTextEncode", text_truthy=True)
    negative_id = find_node(workflow, "CLIPTextEncode", text_truthy=False)
    sampler_id = find_node(workflow, "KSampler")
    vae_id = find_node(workflow, "VAELoader")
    reference_id = find_node(workflow, "LoadImage")
    final_save_id = find_node(workflow, "SaveImage")
    workflow[positive_id]["inputs"]["text"] = PROMPT
    workflow[final_save_id]["inputs"]["filename_prefix"] = f"flux_reference_transfer/{method}_seed{seed}"
    pose_save_id = None

    if method == "reference_pose":
        pose_id = uuid.uuid4().hex[:8]
        pose_save_id = uuid.uuid4().hex[:8]
        control_loader_id = uuid.uuid4().hex[:8]
        control_apply_id = uuid.uuid4().hex[:8]
        workflow[pose_id] = {
            "class_type": "OpenposePreprocessor",
            "inputs": {
                "image": [reference_id, 0],
                "detect_hand": "enable",
                "detect_body": "enable",
                "detect_face": "disable",
                # The preprocessor keeps aspect ratio. Using 768 here produces
                # an exact 768x1024 control image for this evaluation canvas.
                "resolution": 768,
                "scale_stick_for_xinsr_cn": "disable",
            },
        }
        workflow[pose_save_id] = {
            "class_type": "SaveImage",
            "inputs": {"images": [pose_id, 0], "filename_prefix": f"flux_reference_transfer/pose_seed{seed}"},
        }
        workflow[control_loader_id] = {
            "class_type": "ControlNetLoader",
            "inputs": {"control_net_name": "flux-union-pro-2/diffusion_pytorch_model.safetensors"},
        }
        workflow[control_apply_id] = {
            "class_type": "ControlNetApplySD3",
            "inputs": {
                "positive": [positive_id, 0],
                "negative": [negative_id, 0],
                "control_net": [control_loader_id, 0],
                "vae": [vae_id, 0],
                "image": [pose_id, 0],
                "strength": 0.9,
                "start_percent": 0.0,
                "end_percent": 0.65,
            },
        }
        workflow[sampler_id]["inputs"]["positive"] = [control_apply_id, 0]
        workflow[sampler_id]["inputs"]["negative"] = [control_apply_id, 1]
    return workflow, final_save_id, pose_save_id


def run(workflow: dict, final_save_id: str, pose_save_id: str | None, timeout: int) -> tuple[str, dict, float]:
    started = time.monotonic()
    response = request_json("/prompt", {"prompt": workflow, "client_id": str(uuid.uuid4())})
    if response.get("error") or response.get("node_errors"):
        raise RuntimeError(json.dumps(response, ensure_ascii=False))
    prompt_id = response["prompt_id"]
    while time.monotonic() - started < timeout:
        time.sleep(2)
        item = request_json(f"/history/{prompt_id}").get(prompt_id)
        if not item:
            continue
        status = item.get("status", {})
        if status.get("status_str") == "error":
            raise RuntimeError(json.dumps(status, ensure_ascii=False))
        if status.get("completed") or status.get("status_str") == "success":
            return prompt_id, item, round(time.monotonic() - started, 2)
    raise TimeoutError(prompt_id)


def copy_node_image(history: dict, node_id: str | None, target: Path) -> str | None:
    if node_id is None:
        return None
    images = history.get("outputs", {}).get(node_id, {}).get("images", [])
    if not images:
        raise RuntimeError(f"node {node_id} completed without image")
    image = images[0]
    source = COMFY_OUTPUT / image.get("subfolder", "") / image["filename"]
    target.parent.mkdir(parents=True, exist_ok=True)
    shutil.copy2(source, target)
    return str(target)


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--reference", type=Path, default=DEFAULT_REFERENCE)
    parser.add_argument("--baseline", type=Path, default=DEFAULT_BASELINE)
    parser.add_argument("--root", type=Path, default=DEFAULT_ROOT)
    parser.add_argument("--seed", type=int, default=910001)
    parser.add_argument("--timeout", type=int, default=1800)
    parser.add_argument(
        "--methods", nargs="+", choices=("reference_only", "reference_pose"),
        default=("reference_only", "reference_pose"),
    )
    parser.add_argument("--baseline-kind", default="same_seed_baseline")
    parser.add_argument("--baseline-elapsed", type=float, default=420.2)
    args = parser.parse_args()

    for path in (args.reference, args.baseline):
        if not path.exists():
            raise FileNotFoundError(path)
    request_json("/system_stats")
    args.root.mkdir(parents=True, exist_ok=True)
    records = [{
        "method": args.baseline_kind, "seed": args.seed, "status": "existing",
        "output": str(args.baseline), "elapsed_seconds": args.baseline_elapsed,
    }]
    started_at = datetime.now().astimezone()

    report_path = args.root / "generation_report.json"

    def write_report() -> None:
        report = {
            "title": "Flux candidate reference transfer evaluation",
            "started_at": started_at.isoformat(timespec="seconds"),
            "finished_at": datetime.now().astimezone().isoformat(timespec="seconds"),
            "reference": str(args.reference), "seed": args.seed, "prompt": PROMPT,
            "ipadapter_weight": 0.85,
            "pose_control": {"strength": 0.9, "start_percent": 0.0, "end_percent": 0.65},
            "records": records,
        }
        report_path.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n")

    for method in args.methods:
        print(f"START {method}", flush=True)
        workflow, final_save_id, pose_save_id = build(args.reference, args.seed, method)
        workflow_path = args.root / "workflows" / f"{method}.json"
        workflow_path.parent.mkdir(parents=True, exist_ok=True)
        workflow_path.write_text(json.dumps(workflow, ensure_ascii=False, indent=2) + "\n")
        try:
            prompt_id, history, elapsed = run(workflow, final_save_id, pose_save_id, args.timeout)
            output = copy_node_image(history, final_save_id, args.root / method / f"seed_{args.seed}.png")
            pose_output = copy_node_image(history, pose_save_id, args.root / method / f"pose_{args.seed}.png")
            record = {
                "method": method, "seed": args.seed, "status": "ok", "prompt_id": prompt_id,
                "elapsed_seconds": elapsed, "output": output, "pose_output": pose_output,
            }
            print(f"DONE {method} {elapsed}s", flush=True)
        except KeyboardInterrupt:
            records.append({"method": method, "seed": args.seed, "status": "interrupted"})
            write_report()
            raise
        except Exception as exc:
            record = {"method": method, "seed": args.seed, "status": "error", "error": repr(exc)}
            print(f"ERROR {method}: {exc!r}", flush=True)
        records.append(record)
        write_report()
    print(f"REPORT {report_path}", flush=True)


if __name__ == "__main__":
    main()
