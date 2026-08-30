#!/usr/bin/env python3
"""Create a deterministic square face reference crop using InsightFace."""

from __future__ import annotations

import argparse
import json
from pathlib import Path

import cv2
from insightface.app import FaceAnalysis


INSIGHTFACE_ROOT = "/Users/jacky/ComfyUI/models/insightface"


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("input", type=Path)
    parser.add_argument("output", type=Path)
    parser.add_argument("--expand", type=float, default=2.8, help="Square side as a multiple of detected face height")
    parser.add_argument("--size", type=int, default=512)
    parser.add_argument("--metadata", type=Path)
    args = parser.parse_args()

    image = cv2.imread(str(args.input))
    if image is None:
        raise FileNotFoundError(args.input)
    app = FaceAnalysis(name="antelopev2", root=INSIGHTFACE_ROOT, providers=["CPUExecutionProvider"])
    app.prepare(ctx_id=-1, det_size=(640, 640))
    faces = app.get(image)
    if not faces:
        raise RuntimeError("no face detected")
    face = max(faces, key=lambda item: (item.bbox[2] - item.bbox[0]) * (item.bbox[3] - item.bbox[1]))
    x1, y1, x2, y2 = (float(value) for value in face.bbox)
    face_height = y2 - y1
    side = max(128, round(face_height * args.expand))
    center_x = (x1 + x2) / 2
    # Shift down slightly so the crop includes chin/shoulders while retaining hair.
    center_y = (y1 + y2) / 2 + face_height * 0.12
    height, width = image.shape[:2]
    left = max(0, min(round(center_x - side / 2), width - side))
    top = max(0, min(round(center_y - side / 2), height - side))
    right = min(width, left + side)
    bottom = min(height, top + side)
    crop = image[top:bottom, left:right]
    crop = cv2.resize(crop, (args.size, args.size), interpolation=cv2.INTER_LANCZOS4)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    if not cv2.imwrite(str(args.output), crop):
        raise RuntimeError(f"failed to write {args.output}")

    metadata = {
        "input": str(args.input), "output": str(args.output),
        "detected_bbox": [round(x1, 2), round(y1, 2), round(x2, 2), round(y2, 2)],
        "crop_box": [left, top, right, bottom], "expand": args.expand,
        "output_size": [args.size, args.size],
    }
    if args.metadata:
        args.metadata.parent.mkdir(parents=True, exist_ok=True)
        args.metadata.write_text(json.dumps(metadata, ensure_ascii=False, indent=2) + "\n")
    print(json.dumps(metadata, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
