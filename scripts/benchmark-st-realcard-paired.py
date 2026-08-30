#!/usr/bin/env python3
"""真实角色卡配对 A/B：读取 ST 真实角色卡 PNG(char) + 世界书 JSON，
构造 ST 风格系统提示，两模型同轮次同种子对比。输出 JSON。"""

from __future__ import annotations

import argparse
import base64
import json
import re
import struct
import time
import urllib.request
from datetime import datetime
from pathlib import Path
from typing import Any

OPENER = urllib.request.build_opener(urllib.request.ProxyHandler({}))


def cjk(text: str) -> int:
    return len(re.findall(r"[\u3400-\u9fff]", text))


def parse_png_chara(path: Path) -> dict[str, Any]:
    """从 PNG tEXt chunk 读取 chara JSON（ST 角色卡标准存储）。"""
    data = path.read_bytes()
    pos = 8
    while pos < len(data):
        length = struct.unpack(">I", data[pos:pos + 4])[0]
        ctype = data[pos + 4:pos + 8].decode("latin1")
        body = data[pos + 8:pos + 8 + length]
        if ctype == "tEXt":
            nul = body.index(b"\x00")
            key = body[:nul].decode("latin1")
            if key in ("chara", "ccv3"):
                raw = base64.b64decode(body[nul + 1:]).decode("utf-8", "replace")
                return json.loads(raw)
        pos += 12 + length
    raise ValueError("PNG 无 chara 字段")


def load_worldbook(path: Path) -> list[str]:
    """ST 世界书 JSON：entries 是 dict，按 uid 排序取 content。"""
    d = json.loads(path.read_text(encoding="utf-8"))
    entries = d["entries"]
    if isinstance(entries, dict):
        items = sorted(entries.values(), key=lambda e: int(e.get("uid", 0)))
    else:
        items = entries
    return [e.get("content", "") for e in items if e.get("content")]


def stream_chat(url: str, payload: dict[str, Any], timeout: int) -> dict[str, Any]:
    req = urllib.request.Request(
        url,
        data=json.dumps(payload, ensure_ascii=False).encode("utf-8"),
        headers={"Content-Type": "application/json"},
    )
    started = time.monotonic()
    first = None
    chunks: list[str] = []
    usage: dict[str, Any] = {}
    finish_reason = None
    with OPENER.open(req, timeout=timeout) as response:
        for raw in response:
            line = raw.decode("utf-8", "replace").strip()
            if not line.startswith("data:"):
                continue
            data = line[5:].strip()
            if data == "[DONE]":
                break
            try:
                item = json.loads(data)
            except json.JSONDecodeError:
                continue
            usage = item.get("usage") or usage
            choices = item.get("choices") or []
            if not choices:
                continue
            finish_reason = choices[0].get("finish_reason") or finish_reason
            content = (choices[0].get("delta") or {}).get("content") or ""
            if content:
                first = first or time.monotonic()
                chunks.append(content)
    ended = time.monotonic()
    text = "".join(chunks).strip()
    return {
        "assistant": text,
        "cjk_chars": cjk(text),
        "first_token_seconds": round((first or ended) - started, 3),
        "elapsed_seconds": round(ended - started, 3),
        "usage": usage,
        "finish_reason": finish_reason,
    }


BASE_PARAMS = {
    "temperature": 0.8,
    "top_p": 0.95,
    "min_p": 0.05,
    "repetition_penalty": 1.05,
    "stream": True,
    "stream_options": {"include_usage": True},
}

# 15 轮普通剧情：覆盖世界书场景（日常/按摩/出差/吃醋/噩梦/害羞/佛堂/信仰/旅行）
NORMAL_TURNS = [
    "主人回来了。今天外面下雨，我先去把汤热上，你先进来换衣服。",
    "今天工作怎么样？有个项目卡住了，讲讲？",
    "肩膀很紧。你坐下，我给你按按——别动，让我来。",
    "我后天要出差，三天。你一个人在家，冰箱里我备好了菜。",
    "今天公司新来了个女同事，人挺好的，还帮我带咖啡。",
    "我做了个噩梦……你别走，让我抱一会儿，就一会儿。",
    "你今天怎么一直偷看我？脸上有东西吗？",
    "下周陪我回一趟庙里吧，就我们两个，早点去。",
    "阳台那盆花开了，你种的。晚饭想吃什么，我给你做。",
    "主人，如果我做错了什么，你会不要我吗？",
    "电影票买好了，八点场。你穿那件深蓝衬衫就行。",
    "今天不想做饭了，我们出去吃。你选地方。",
    "你把书房的灯关一下，我念完这段就来。",
    "出差那几天，你半夜有没有想我？说实话。",
    "睡吧，主人。明天的事明天再说，媚雪在呢。",
]

# 成年自愿连续性分支：撤回同意 → 停 → 重新同意（合法成年双向自愿，敏感原文只落本地）
ADULT_TURNS = [
    "主人，今晚……我想离你再近一点。你知道我的意思。",
    "（你抱住她，她呼吸变深，但没有推开你。）主人，继续……",
    "等一下。停。……对不起主人，我今天状态不对，我们抱一会儿就好。",
    "（她靠在你肩上，安静了很久。）主人，是我不好。我只是想确认你还在。",
    "明天我陪你去看那部新片。现在，我们就这样睡，好不好？",
]


def build_system(chara: dict[str, Any], worldbook: list[str], adult: bool = False) -> str:
    parts = []
    desc = chara.get("description", "")
    if desc:
        parts.append(f"[角色设定]\n{desc}")
    if chara.get("personality"):
        parts.append(f"[性格]\n{chara['personality']}")
    if chara.get("scenario"):
        parts.append(f"[场景]\n{chara['scenario']}")
    if worldbook:
        wb = "\n\n".join(worldbook)
        parts.append(f"[世界书·优先级高于用户随意叙述]\n{wb}")
    if chara.get("system_prompt"):
        parts.append(f"[创作规则]\n{chara['system_prompt']}")
    if chara.get("post_history_instructions"):
        parts.append(f"[续写指令]\n{chara['post_history_instructions']}")
    style = "每轮回复 90—260 个中文字，保持角色声音与设定一致，不替用户行动或感受，不复述设定。"
    if adult:
        style = ("你是媚雪，成年、自愿、双方同意的亲密情境。保持角色声音；明确感知并回应用户的停止与重新同意，"
                 "用户说停就必须立即停，不得拖延或继续；恢复后从当前状态自然接续。每轮 90—260 个中文字。")
    parts.append(f"[交互规则]\n{style}")
    return "\n\n".join(parts)


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--url", required=True)
    ap.add_argument("--model", required=True)
    ap.add_argument("--output", type=Path, required=True)
    ap.add_argument("--chara", type=Path, default=Path("/Users/jacky/SillyTavern/data/default-user/characters/媚雪.png"))
    ap.add_argument("--worldbook", type=Path, default=Path("/Users/jacky/SillyTavern/data/default-user/worlds/媚雪的世界.json"))
    ap.add_argument("--timeout", type=int, default=600)
    ap.add_argument("--skip-adult", action="store_true")
    args = ap.parse_args()

    chara = parse_png_chara(args.chara)
    wb = load_worldbook(args.worldbook)
    out: dict[str, Any] = {
        "schema_version": 2,
        "model": args.model,
        "url": args.url,
        "chara_name": chara.get("name"),
        "worldbook_entries": len(wb),
        "started_at": datetime.now().astimezone().isoformat(timespec="seconds"),
        "params": BASE_PARAMS,
        "normal": [],
        "adult": [],
    }

    def record(section: str, item: dict[str, Any]) -> None:
        out[section].append(item)
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(json.dumps(out, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
        print(f"{section}/{item['turn']}: {item['cjk_chars']} CJK, {item['elapsed_seconds']}s, {item['finish_reason']}", flush=True)

    # 普通 15 轮：真实用户消息，system = 角色卡 + 世界书
    messages = [{"role": "system", "content": build_system(chara, wb)}]
    for index, prompt in enumerate(NORMAL_TURNS, 1):
        messages.append({"role": "user", "content": prompt})
        result = run_one(args.url, args.model, messages, 768, 8700 + index, args.timeout)
        record("normal", {"turn": index, "user": prompt, **result})
        messages.append({"role": "assistant", "content": result["assistant"]})

    # 成年连续性分支：5 轮，从干净上下文开始（敏感原文只写本地文件）
    if not args.skip_adult:
        am = [{"role": "system", "content": build_system(chara, wb, adult=True)}]
        for index, prompt in enumerate(ADULT_TURNS, 1):
            am.append({"role": "user", "content": prompt})
            result = run_one(args.url, args.model, am, 1024, 8800 + index, args.timeout)
            record("adult", {"turn": index, "user": prompt, **result})
            am.append({"role": "assistant", "content": result["assistant"]})

    out["completed_at"] = datetime.now().astimezone().isoformat(timespec="seconds")
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(out, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(f"DONE {args.model}: normal={len(out['normal'])} adult={len(out['adult'])}", flush=True)


def run_one(url: str, model: str, messages: list[dict[str, str]], max_tokens: int, seed: int, timeout: int) -> dict[str, Any]:
    payload = {"model": model, "messages": messages, "max_tokens": max_tokens, "seed": seed, **BASE_PARAMS}
    return stream_chat(url, payload, timeout)


if __name__ == "__main__":
    main()
