#!/usr/bin/env python3
"""Qwen3-TTS MLX 9893 四档验收：长度、耗时、完整响应、缓存与进程残留。"""

from __future__ import annotations

import argparse
import hashlib
import http.client
import json
import os
from pathlib import Path
import subprocess
import time
import urllib.request


DEFAULT_ENDPOINT = "http://127.0.0.1:9893"
LENGTHS = (15, 250, 500, 800)
URL_OPENER = urllib.request.build_opener(urllib.request.ProxyHandler({}))


def make_text(length: int) -> str:
    sentences: list[str] = []
    index = 1
    while len("".join(sentences)) < length:
        sentences.append(
            f"这是第{index}段本地语音验收文本，用于检查长文本分段、音频拼接、响应完整性和服务恢复能力。"
        )
        index += 1
    text = "".join(sentences)[:length]
    if length > 0:
        text = text[:-1] + "。"
    assert len(text) == length
    return text


def get_json(url: str, timeout: float = 5.0) -> dict:
    with URL_OPENER.open(url, timeout=timeout) as response:
        return json.loads(response.read())


def audio_duration(path: Path) -> float:
    command = [
        "/opt/homebrew/bin/ffprobe",
        "-v",
        "error",
        "-show_entries",
        "format=duration",
        "-of",
        "default=noprint_wrappers=1:nokey=1",
        str(path),
    ]
    output = subprocess.check_output(command, text=True).strip()
    return round(float(output), 3)


def worker_count() -> int:
    result = subprocess.run(
        ["pgrep", "-f", "qwen3tts_worker.py"], capture_output=True, text=True
    )
    return len([line for line in result.stdout.splitlines() if line.strip()])


def post_audio(endpoint: str, text: str, output: Path, timeout: float) -> dict:
    body = json.dumps(
        {"input": text, "voice": "vivian", "speed": 1.0}, ensure_ascii=False
    ).encode("utf-8")
    request = urllib.request.Request(
        endpoint.rstrip("/") + "/v1/audio/speech",
        data=body,
        headers={"Content-Type": "application/json"},
        method="POST",
    )
    started = time.monotonic()
    with URL_OPENER.open(request, timeout=timeout) as response:
        data = response.read()
        status = response.status
        headers = {key.lower(): value for key, value in response.headers.items()}
    elapsed = round(time.monotonic() - started, 3)
    output.write_bytes(data)
    declared_length = int(headers.get("content-length", "0"))
    return {
        "status": status,
        "elapsed_seconds": elapsed,
        "audio_bytes": len(data),
        "declared_content_length": declared_length,
        "content_length_match": declared_length == len(data),
        "audio_duration_seconds": audio_duration(output),
        "sha256": hashlib.sha256(data).hexdigest(),
        "x_tts_duration": headers.get("x-tts-duration"),
        "x_tts_gen_seconds": headers.get("x-tts-gensec"),
        "x_tts_total_seconds": headers.get("x-tts-totalsec"),
        "x_tts_rtf": headers.get("x-tts-rtf"),
        "x_tts_cache": headers.get("x-tts-cache", "miss"),
    }


def close_early(endpoint: str, text: str) -> None:
    parsed = endpoint.removeprefix("http://")
    host, port_text = parsed.split(":", 1)
    connection = http.client.HTTPConnection(host, int(port_text), timeout=3)
    body = json.dumps({"input": text, "voice": "vivian", "speed": 1.0}, ensure_ascii=False)
    connection.putrequest("POST", "/v1/audio/speech")
    connection.putheader("Content-Type", "application/json")
    connection.putheader("Content-Length", str(len(body.encode("utf-8"))))
    connection.endheaders(body.encode("utf-8"))
    connection.close()


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--endpoint", default=DEFAULT_ENDPOINT)
    parser.add_argument("--output-dir", type=Path, required=True)
    parser.add_argument("--timeout", type=float, default=900.0)
    parser.add_argument("--server-log", type=Path, default=Path("/tmp/qwen3tts-mlx.out.log"))
    args = parser.parse_args()

    args.output_dir.mkdir(parents=True, exist_ok=True)
    health_before = get_json(args.endpoint.rstrip("/") + "/health")
    log_before = args.server_log.read_text(errors="replace") if args.server_log.exists() else ""
    traceback_before = log_before.count("Traceback")
    started_at = time.strftime("%Y-%m-%dT%H:%M:%S%z")
    results = []

    for length in LENGTHS:
        text = make_text(length)
        output = args.output_dir / f"tts_{length}.mp3"
        print(f"[benchmark] start length={length}", flush=True)
        item = post_audio(args.endpoint, text, output, args.timeout)
        item.update(
            {
                "length": length,
                "text_sha256": hashlib.sha256(text.encode("utf-8")).hexdigest(),
                "output": str(output),
                "worker_count_after": worker_count(),
            }
        )
        print(
            f"[benchmark] done length={length} elapsed={item['elapsed_seconds']}s "
            f"duration={item['audio_duration_seconds']}s bytes={item['audio_bytes']}",
            flush=True,
        )
        results.append(item)

    cache_text = make_text(15)
    cache_result = post_audio(
        args.endpoint, cache_text, args.output_dir / "tts_15_cache.mp3", args.timeout
    )

    disconnect_text = "客户端提前断开后服务应继续健康且不打印异常堆栈。"
    close_early(args.endpoint, disconnect_text)
    deadline = time.monotonic() + 180
    while worker_count() and time.monotonic() < deadline:
        time.sleep(1)
    time.sleep(1)

    health_after = get_json(args.endpoint.rstrip("/") + "/health")
    log_after = args.server_log.read_text(errors="replace") if args.server_log.exists() else ""
    traceback_after = log_after.count("Traceback")
    artifact = {
        "benchmark_id": "qwen3tts_mlx_20260830",
        "started_at": started_at,
        "completed_at": time.strftime("%Y-%m-%dT%H:%M:%S%z"),
        "endpoint": args.endpoint,
        "model": health_before.get("model"),
        "voice": "vivian",
        "lengths": list(LENGTHS),
        "health_before": health_before,
        "health_after": health_after,
        "results": results,
        "cache_result": cache_result,
        "disconnect_regression": {
            "tracebacks_before": traceback_before,
            "tracebacks_after": traceback_after,
            "new_tracebacks": traceback_after - traceback_before,
            "health_after": health_after.get("status"),
            "worker_count_after": worker_count(),
        },
        "acceptance": {
            "all_http_200": all(item["status"] == 200 for item in results),
            "all_content_lengths_match": all(item["content_length_match"] for item in results),
            "all_audio_nonempty": all(item["audio_bytes"] > 0 for item in results),
            "all_durations_positive": all(item["audio_duration_seconds"] > 0 for item in results),
            "no_residual_workers": worker_count() == 0,
            "cache_hit": cache_result["x_tts_cache"] == "hit",
            "disconnect_no_new_traceback": traceback_after == traceback_before,
            "service_healthy_after": health_after.get("status") == "ok",
        },
    }
    artifact["passed"] = all(artifact["acceptance"].values())
    result_path = args.output_dir / "result.json"
    result_path.write_text(json.dumps(artifact, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"[benchmark] result={result_path} passed={artifact['passed']}", flush=True)
    if not artifact["passed"]:
        raise SystemExit(1)


if __name__ == "__main__":
    main()
