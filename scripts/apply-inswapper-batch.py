#!/usr/bin/env python3
"""Apply the local InSwapper model to one or more images with a shared source identity."""

from __future__ import annotations

import argparse
import json
import os
from datetime import datetime
from pathlib import Path

import cv2
import insightface
from insightface.app import FaceAnalysis


os.environ.setdefault("OMP_NUM_THREADS", "4")
INSIGHTFACE_ROOT = "/Users/jacky/ComfyUI/models/insightface"
SWAPPER_MODEL = Path("/Users/jacky/ComfyUI/models/insightface/inswapper_128.onnx")


def biggest(faces):
    return max(faces, key=lambda face: (face.bbox[2] - face.bbox[0]) * (face.bbox[3] - face.bbox[1]))


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--source", type=Path, required=True)
    parser.add_argument("--targets", type=Path, nargs="+", required=True)
    parser.add_argument("--output-dir", type=Path, required=True)
    parser.add_argument("--report", type=Path)
    args = parser.parse_args()

    if not args.source.exists():
        raise FileNotFoundError(args.source)
    if not SWAPPER_MODEL.exists():
        raise FileNotFoundError(SWAPPER_MODEL)
    for target in args.targets:
        if not target.exists():
            raise FileNotFoundError(target)

    app = FaceAnalysis(name="antelopev2", root=INSIGHTFACE_ROOT, providers=["CPUExecutionProvider"])
    app.prepare(ctx_id=-1, det_size=(640, 640))
    swapper = insightface.model_zoo.get_model(str(SWAPPER_MODEL), providers=["CPUExecutionProvider"])
    source_image = cv2.imread(str(args.source))
    source_faces = app.get(source_image)
    if not source_faces:
        raise RuntimeError("source face not detected")
    source_face = biggest(source_faces)
    args.output_dir.mkdir(parents=True, exist_ok=True)
    records = []

    for target_path in args.targets:
        target_image = cv2.imread(str(target_path))
        target_faces = app.get(target_image)
        if not target_faces:
            records.append({"target": str(target_path), "status": "no_face"})
            continue
        target_face = biggest(target_faces)
        swapped = swapper.get(target_image, target_face, source_face, paste_back=True)
        output = args.output_dir / target_path.name
        if not cv2.imwrite(str(output), swapped):
            raise RuntimeError(f"failed to write {output}")
        check_faces = app.get(swapped)
        if not check_faces:
            records.append({"target": str(target_path), "status": "output_no_face", "output": str(output)})
            continue
        check_face = biggest(check_faces)
        similarity = float(source_face.normed_embedding @ check_face.normed_embedding)
        records.append({
            "target": str(target_path), "status": "ok", "output": str(output),
            "similarity_to_source": round(similarity, 4),
            "target_bbox": [round(float(value), 2) for value in target_face.bbox],
            "output_bbox": [round(float(value), 2) for value in check_face.bbox],
        })
        print(target_path.name, round(similarity, 4), output, flush=True)

    report = {
        "title": "Local InSwapper batch identity replacement",
        "created_at": datetime.now().astimezone().isoformat(timespec="seconds"),
        "source": str(args.source), "model": str(SWAPPER_MODEL), "records": records,
    }
    report_path = args.report or args.output_dir / "report.json"
    report_path.parent.mkdir(parents=True, exist_ok=True)
    report_path.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n")
    print(f"REPORT {report_path}", flush=True)


if __name__ == "__main__":
    main()
