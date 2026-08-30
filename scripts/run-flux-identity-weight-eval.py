#!/usr/bin/env python3
"""Flux full-body identity test: compare IP-Adapter weights on shared seeds."""

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
ROOT = PROJECT / "results/aesthetic/20260813-flux-identity-lock"
RAW_OUT = Path("/Users/jacky/ComfyUI/output")
REFERENCE = PROJECT / "results/aesthetic/20260812-blind/flux/seed_0007.png"
SEEDS = [31415, 27182]
WEIGHTS = [0.85, 1.0, 1.15]
PROMPT = (
    "professional editorial long-shot photograph of one fictional adult woman age 30, "
    "strict full-length composition, entire person visible continuously from the top of "
    "her hair to the soles of both boots, both complete feet inside the frame, standing "
    "upright centered in a bright minimalist studio, camera pulled far back at waist height, "
    "generous empty floor below both boots, margin above her head, subject occupies about "
    "65 percent of frame height, wearing an opaque emerald green long-sleeve jumpsuit and "
    "black ankle boots, relaxed natural pose, soft daylight, realistic skin texture, natural "
    "anatomy, commercial fashion catalog quality, no crop, not a portrait, not a close-up"
)


def request_json(args: list[str]) -> dict:
    result = subprocess.run(args, capture_output=True, text=True, timeout=30)
    if result.returncode:
        raise RuntimeError(result.stderr.strip())
    return json.loads(result.stdout)


def submit(workflow: dict) -> str:
    data = request_json(["curl", "-fsS", "-X", "POST", f"{API}/prompt", "-H", "Content-Type: application/json",
                         "-d", json.dumps({"prompt": workflow, "client_id": f"identity-{uuid.uuid4().hex}"})])
    if "error" in data:
        raise RuntimeError(json.dumps(data, ensure_ascii=False))
    return data["prompt_id"]


def wait_done(prompt_id: str, timeout: int = 1000) -> dict:
    deadline = time.time() + timeout
    while time.time() < deadline:
        data = request_json(["curl", "-fsS", f"{API}/history/{prompt_id}"])
        if prompt_id in data:
            return data[prompt_id]
        time.sleep(3)
    raise TimeoutError(prompt_id)


def collect(history: dict, target: Path) -> None:
    images = [im for output in history.get("outputs", {}).values() for im in output.get("images", [])]
    if not images:
        raise RuntimeError("no image output")
    item = images[-1]
    source = RAW_OUT / item.get("subfolder", "") / item["filename"]
    target.parent.mkdir(parents=True, exist_ok=True)
    shutil.copy2(source, target)


def build(weight: float, seed: int) -> dict:
    workflow = build_flux_ipadapter_workflow(str(REFERENCE), seed, ipadapter_weight=weight)
    positive = next(n for n in workflow.values() if n["class_type"] == "CLIPTextEncode" and n["inputs"].get("text"))
    positive["inputs"]["text"] = PROMPT
    save = next(n for n in workflow.values() if n["class_type"] == "SaveImage")
    save["inputs"]["filename_prefix"] = f"flux_identity_lock/w{weight:.2f}_seed{seed}"
    return workflow


def main() -> None:
    ROOT.mkdir(parents=True, exist_ok=True)
    started = datetime.now().astimezone()
    records = []
    for weight in WEIGHTS:
        folder = ROOT / f"weight_{weight:.2f}"
        for seed in SEEDS:
            target = folder / f"seed_{seed}.png"
            if target.exists():
                records.append({"weight": weight, "seed": seed, "status": "existing", "output": str(target)})
                continue
            print(f"START weight={weight:.2f} seed={seed}", flush=True)
            t0 = time.time()
            try:
                collect(wait_done(submit(build(weight, seed))), target)
                record = {"weight": weight, "seed": seed, "status": "ok",
                          "elapsed_sec": round(time.time() - t0, 2), "output": str(target)}
                print(f"DONE weight={weight:.2f} seed={seed} {record['elapsed_sec']}s", flush=True)
            except Exception as exc:
                record = {"weight": weight, "seed": seed, "status": "error",
                          "elapsed_sec": round(time.time() - t0, 2), "error": repr(exc)}
                print(f"ERROR weight={weight:.2f} seed={seed} {exc!r}", flush=True)
            records.append(record)
    report = {"title": "Flux identity lock weight evaluation", "started_at": started.isoformat(timespec="seconds"),
              "finished_at": datetime.now().astimezone().isoformat(timespec="seconds"), "reference": str(REFERENCE),
              "prompt": PROMPT, "seeds": SEEDS, "weights": WEIGHTS, "records": records}
    (ROOT / "generation_report.json").write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n")


if __name__ == "__main__":
    main()
