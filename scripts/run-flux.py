#!/usr/bin/env python3
"""Default Flux production entry point: fast by default, quality on demand."""

from __future__ import annotations

import argparse
import json
import shutil
import time
import urllib.request
import uuid
from pathlib import Path

from flux_presets import FLUX_PRESETS, build_flux_workflow, get_flux_preset


API = "http://127.0.0.1:8188"
OPENER = urllib.request.build_opener(urllib.request.ProxyHandler({}))
COMFY_OUTPUT = Path("/Users/jacky/ComfyUI/output")


def request_json(path: str, payload: dict | None = None, timeout: int = 30) -> dict:
    url = f"{API}{path}"
    if payload is None:
        with OPENER.open(url, timeout=timeout) as response:
            return json.loads(response.read())
    request = urllib.request.Request(url, data=json.dumps(payload).encode(), headers={"Content-Type": "application/json"})
    with OPENER.open(request, timeout=timeout) as response:
        return json.loads(response.read())


def run_workflow(workflow: dict, timeout: int) -> tuple[str, Path, float]:
    started = time.monotonic()
    response = request_json("/prompt", {"prompt": workflow, "client_id": str(uuid.uuid4())})
    if response.get("error") or response.get("node_errors"):
        raise RuntimeError(json.dumps(response, ensure_ascii=False))
    prompt_id = response["prompt_id"]
    item = None
    while time.monotonic() - started < timeout:
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
        raise RuntimeError("completed without image output")
    image = images[0]
    source = COMFY_OUTPUT / image.get("subfolder", "") / image["filename"]
    return prompt_id, source, round(time.monotonic() - started, 2)


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("prompt", help="Flux prompt")
    parser.add_argument("--mode", choices=FLUX_PRESETS, default="fast")
    parser.add_argument("--seed", type=int, default=2026081201)
    parser.add_argument("--width", type=int, default=768)
    parser.add_argument("--height", type=int, default=1024)
    parser.add_argument("--output", type=Path)
    parser.add_argument("--workflow-json", type=Path)
    parser.add_argument("--result-json", type=Path, help="Write the machine-readable run result to this path")
    parser.add_argument("--dry-run", action="store_true")
    parser.add_argument("--timeout", type=int, default=1800)
    args = parser.parse_args()

    prefix = f"flux_production/{args.mode}"
    workflow = build_flux_workflow(
        args.prompt, args.seed, mode=args.mode, width=args.width, height=args.height, filename_prefix=prefix,
    )
    preset = get_flux_preset(args.mode)
    if args.workflow_json:
        args.workflow_json.parent.mkdir(parents=True, exist_ok=True)
        args.workflow_json.write_text(json.dumps(workflow, ensure_ascii=False, indent=2) + "\n")
    if args.dry_run:
        print(json.dumps({"mode": args.mode, "preset": preset, "workflow": workflow}, ensure_ascii=False, indent=2))
        return

    prompt_id, source, elapsed = run_workflow(workflow, args.timeout)
    output = args.output
    if output:
        output.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(source, output)
    result = {
        "status": "completed", "mode": args.mode, "preset": preset, "prompt_id": prompt_id,
        "seed": args.seed, "width": args.width, "height": args.height,
        "elapsed_seconds": elapsed, "source_output": str(source), "output": str(output) if output else str(source),
    }
    if args.result_json:
        args.result_json.parent.mkdir(parents=True, exist_ok=True)
        args.result_json.write_text(json.dumps(result, ensure_ascii=False, indent=2) + "\n")
    print(json.dumps(result, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
