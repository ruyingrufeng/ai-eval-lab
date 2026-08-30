#!/usr/bin/env python3
"""Run two-seed Flux Dev identity confirmation from a high-quality frontal master."""

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
DEFAULT_ROOT = PROJECT / "results/performance/flux-identity-master-confirmation-20260814"
DEFAULT_FRONTAL = Path("/Users/jacky/Documents/BaiLing/assets/face/meixue_face_img2_14.png")
DEFAULT_THREE_QUARTER = Path("/Users/jacky/Documents/BaiLing/assets/face/model.jpg")
DEFAULT_SIDE = Path("/Users/jacky/Documents/BaiLing/assets/face/meixue_face_img2_08.png")

PROMPT = (
    "full-body editorial photograph of one adult East Asian woman age 30, standing naturally "
    "in a modern daylight studio, entire figure visible from head to shoes, realistic face, "
    "natural skin texture, anatomically correct hands, balanced proportions, neutral cream top "
    "and tailored gray trousers, clean background, commercial photography"
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


def build(reference: Path, seed: int) -> tuple[dict, str]:
    workflow = build_flux_ipadapter_workflow(str(reference), seed, ipadapter_weight=0.85, mode="quality")
    positive_id = next(
        node_id for node_id, node in workflow.items()
        if node["class_type"] == "CLIPTextEncode" and node["inputs"].get("text")
    )
    save_id = next(node_id for node_id, node in workflow.items() if node["class_type"] == "SaveImage")
    workflow[positive_id]["inputs"]["text"] = PROMPT
    workflow[save_id]["inputs"]["filename_prefix"] = f"flux_identity_master/seed{seed}"
    return workflow, save_id


def run(workflow: dict, save_id: str, timeout: int) -> tuple[str, dict, float]:
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
            images = item.get("outputs", {}).get(save_id, {}).get("images", [])
            if not images:
                raise RuntimeError("completed without final image")
            return prompt_id, images[0], round(time.monotonic() - started, 2)
    raise TimeoutError(prompt_id)


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--frontal", type=Path, default=DEFAULT_FRONTAL)
    parser.add_argument("--three-quarter", type=Path, default=DEFAULT_THREE_QUARTER)
    parser.add_argument("--side", type=Path, default=DEFAULT_SIDE)
    parser.add_argument("--seeds", type=int, nargs="+", default=(31415, 27182))
    parser.add_argument("--root", type=Path, default=DEFAULT_ROOT)
    parser.add_argument("--timeout", type=int, default=1800)
    parser.add_argument("--inter-seed-pause", type=int, default=20)
    args = parser.parse_args()

    masters = {"frontal": args.frontal, "three_quarter": args.three_quarter, "side": args.side}
    for path in masters.values():
        if not path.exists():
            raise FileNotFoundError(path)
    request_json("/system_stats")
    args.root.mkdir(parents=True, exist_ok=True)
    report_path = args.root / "generation_report.json"
    started_at = datetime.now().astimezone()
    records = []

    def write_report() -> None:
        payload = {
            "title": "Flux high-quality identity master two-seed confirmation",
            "started_at": started_at.isoformat(timespec="seconds"),
            "updated_at": datetime.now().astimezone().isoformat(timespec="seconds"),
            "masters": {key: str(value) for key, value in masters.items()},
            "generation_reference": str(args.frontal), "seeds": args.seeds,
            "prompt": PROMPT, "ipadapter_weight": 0.85, "records": records,
        }
        report_path.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n")

    for index, seed in enumerate(args.seeds):
        print(f"START seed={seed}", flush=True)
        workflow, save_id = build(args.frontal, seed)
        workflow_path = args.root / "workflows" / f"seed_{seed}.json"
        workflow_path.parent.mkdir(parents=True, exist_ok=True)
        workflow_path.write_text(json.dumps(workflow, ensure_ascii=False, indent=2) + "\n")
        try:
            prompt_id, image, elapsed = run(workflow, save_id, args.timeout)
            source = COMFY_OUTPUT / image.get("subfolder", "") / image["filename"]
            target = args.root / "images" / f"seed_{seed}.png"
            target.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(source, target)
            record = {
                "seed": seed, "status": "ok", "prompt_id": prompt_id,
                "elapsed_seconds": elapsed, "output": str(target),
            }
            print(f"DONE seed={seed} {elapsed}s", flush=True)
        except KeyboardInterrupt:
            records.append({"seed": seed, "status": "interrupted"})
            write_report()
            raise
        except Exception as exc:
            record = {"seed": seed, "status": "error", "error": repr(exc)}
            print(f"ERROR seed={seed}: {exc!r}", flush=True)
        records.append(record)
        write_report()
        if index < len(args.seeds) - 1:
            print(f"PAUSE {args.inter_seed_pause}s before next seed", flush=True)
            time.sleep(args.inter_seed_pause)
    print(f"REPORT {report_path}", flush=True)


if __name__ == "__main__":
    main()
