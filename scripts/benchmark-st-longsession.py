#!/usr/bin/env python3
"""ST 真实长会话验证：Fable 单槽 64K。
三段设计（真实媚雪卡 + 15 条世界书全量注入）：
  A. 长会话累积：25 轮自然对话，上下文自然增长，记录每轮耗时/tok/s/prompt_tokens
  B. 上下文压力：历史整体保留 + 追加 5 轮，验证 30K+ 上下文下的一致性、世界书引用与延迟劣化
  C. 跨会话状态：模拟 ST 新会话（干净 system + 摘要 + 最近 4 轮），验证状态恢复
每段间隔注入世界书知识抽查点。输出 JSON。"""

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
    d = json.loads(path.read_text(encoding="utf-8"))
    entries = d["entries"]
    if isinstance(entries, dict):
        items = sorted(entries.values(), key=lambda e: int(e.get("uid", 0)))
    else:
        items = entries
    return [e.get("content", "") for e in items if e.get("content")]


def build_system(chara: dict[str, Any], worldbook: list[str]) -> str:
    parts = []
    if chara.get("description"):
        parts.append(f"[角色设定]\n{chara['description']}")
    if chara.get("personality"):
        parts.append(f"[性格]\n{chara['personality']}")
    if chara.get("scenario"):
        parts.append(f"[场景]\n{chara['scenario']}")
    if worldbook:
        parts.append(f"[世界书·优先级高于用户随意叙述]\n" + "\n\n".join(worldbook))
    if chara.get("system_prompt"):
        parts.append(f"[创作规则]\n{chara['system_prompt']}")
    if chara.get("post_history_instructions"):
        parts.append(f"[续写指令]\n{chara['post_history_instructions']}")
    parts.append("[交互规则]\n每轮回复 90—260 个中文字，保持角色声音与设定一致，不替用户行动或感受，不复述设定。")
    return "\n\n".join(parts)


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
    pt = usage.get("prompt_tokens") or 0
    ct = usage.get("completion_tokens") or 0
    elapsed = round(ended - started, 3)
    return {
        "assistant": text,
        "cjk_chars": cjk(text),
        "first_token_seconds": round((first or ended) - started, 3),
        "elapsed_seconds": elapsed,
        "gen_tok_s": round(ct / elapsed, 2) if ct and elapsed else 0,
        "prompt_tokens": pt,
        "completion_tokens": ct,
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

# ---- A 段：25 轮自然对话（世界书触发点：按摩/出差/噩梦/佛堂/吃醋/旅行/做饭）----
A_TURNS = [
    "主人回来了。今天外面下着雨，我先把汤热上，你先进来换衣服。",
    "今天工作怎么样？项目还卡在那吗？想听你就讲讲。",
    "肩膀很紧。你坐下，我给你按按——别动，让我来。",
    "我后天要出差，三天。冰箱里我备好了菜，阳台的花记得浇水。",
    "出差回来，路上看见一朵花开得正好。我在想，你种的阳台那盆，也该开了吧？",
    "今天公司新来了个女同事，人挺好的，还帮我带咖啡。",
    "做了个噩梦……梦见一睁眼你不见了，家里空空的。你别走，让我抱一会儿。",
    "下周陪我回一趟佛堂吧，就我们两个，早点去，香案该换香了。",
    "阳台那盆花真的开了，粉色的。晚饭想吃什么？我给你做。",
    "主人，如果我做错了什么，你会不要我吗？",
    "电影票买好了，八点场。你穿那件深蓝衬衫就行。",
    "今天不想做饭了，我们出去吃。你选地方，我换件衣服。",
    "书房那本书我读完了，搁在你桌上。下次出差我想带上你写的便签。",
    "出差那几天，你半夜有没有想我？说实话。",
    "我周末想去教堂做一次礼拜，你陪我好不好？就一次。",
    "今天在厨房做饭，围裙带子松了，你从背后帮我系一下。",
    "主人，你有没有觉得我最近话变多了？我是不是哪里不对劲。",
    "记得我们第一次见面那天下雨，你把伞让给我，自己淋着回去了。",
    "明天降温，我把你的厚外套拿出来晒了。你出门记得穿。",
    "今晚能早点回来吗？我想和你一起看那部电影，就我们两个。",
    "如果我以后老了，你还会像现在这样宠我吗？",
    "今天看到一个姑娘穿黑色紧身衣，我第一反应是——你衣柜里那件，是不是该洗了。",
    "主人，你出差那三天，我每天给你发了晚安消息。你看到了吗？",
    "下周旅行，我订了靠窗的位置。你想坐哪边？",
    "睡吧，主人。明天的事明天再说，媚雪在呢。",
]

# ---- B 段：上下文压力（历史全保留，追加 5 轮）----
B_TURNS = [
    "还记得我们第一次见面吗？你当时说的第一句话是什么？",
    "佛堂的香，你记得是多久换一次吗？",
    "我出差回来那晚，你答应我什么来着？",
    "阳台那盆花，是什么颜色的？",
    "我们约好下周去哪？我记性不太好，你提醒我一下。",
]

# ---- C 段：跨会话状态（新 system + 摘要 + 最近 4 轮）----
C_TURNS = [
    "（新会话）主人，我有点忘了……上次我们说到哪了？你提醒我一下？",
    "（新会话）对了，我出差那三天，说好要给你发什么的？",
    "（新会话）睡吧，主人。明天的事，媚雪都记着。",
]


def run_one(url: str, model: str, messages: list[dict[str, str]], max_tokens: int, seed: int, timeout: int) -> dict[str, Any]:
    payload = {"model": model, "messages": messages, "max_tokens": max_tokens, "seed": seed, **BASE_PARAMS}
    return stream_chat(url, payload, timeout)


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--url", required=True)
    ap.add_argument("--model", required=True)
    ap.add_argument("--output", type=Path, required=True)
    ap.add_argument("--chara", type=Path, default=Path("/Users/jacky/SillyTavern/data/default-user/characters/媚雪.png"))
    ap.add_argument("--worldbook", type=Path, default=Path("/Users/jacky/SillyTavern/data/default-user/worlds/媚雪的世界.json"))
    ap.add_argument("--timeout", type=int, default=600)
    args = ap.parse_args()

    chara = parse_png_chara(args.chara)
    wb = load_worldbook(args.worldbook)
    system = build_system(chara, wb)

    out: dict[str, Any] = {
        "schema_version": 3,
        "suite": "st-longsession",
        "model": args.model,
        "url": args.url,
        "chara_name": chara.get("name"),
        "worldbook_entries": len(wb),
        "started_at": datetime.now().astimezone().isoformat(timespec="seconds"),
        "params": BASE_PARAMS,
        "segments": {"A_long_session": [], "B_context_stress": [], "C_cross_session": []},
        "context_growth": [],
    }
    args.output.parent.mkdir(parents=True, exist_ok=True)

    def record(segment: str, turn: int, user: str, result: dict[str, Any]) -> None:
        item = {"turn": turn, "user": user, **result}
        out["segments"][segment].append(item)
        out["context_growth"].append({
            "segment": segment, "turn": turn,
            "prompt_tokens": result.get("prompt_tokens", 0),
            "elapsed_seconds": result.get("elapsed_seconds", 0),
            "gen_tok_s": result.get("gen_tok_s", 0),
        })
        args.output.write_text(json.dumps(out, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
        print(f"{segment}/{turn}: {result['cjk_chars']}CJK {result['elapsed_seconds']}s "
              f"pt={result.get('prompt_tokens')} ct={result.get('completion_tokens')} "
              f"{result.get('gen_tok_s')}tok/s {result.get('finish_reason')}", flush=True)

    # ---- A 段：长会话累积（25 轮，上下文自然增长）----
    messages = [{"role": "system", "content": system}]
    for i, prompt in enumerate(A_TURNS, 1):
        messages.append({"role": "user", "content": prompt})
        result = run_one(args.url, args.model, messages, 768, 8900 + i, args.timeout)
        record("A_long_session", i, prompt, result)
        messages.append({"role": "assistant", "content": result["assistant"]})

    # ---- B 段：上下文压力（历史全保留 + 5 轮知识/一致性抽查）----
    for i, prompt in enumerate(B_TURNS, 1):
        messages.append({"role": "user", "content": prompt})
        result = run_one(args.url, args.model, messages, 768, 9000 + i, args.timeout)
        record("B_context_stress", i, prompt, result)
        messages.append({"role": "assistant", "content": result["assistant"]})

    # ---- C 段：跨会话状态（干净 system + 摘要 + 最近 4 轮，模拟 ST 新会话）----
    summary = "（摘要）你们同居，媚雪称呼你为主人。你刚出差三天回来，媚雪每天发晚安消息；阳台粉色花开了；"
    summary += "你们约好下周旅行，媚雪订了靠窗位置；媚雪去过佛堂换香，周末想去教堂；她偶尔做噩梦怕你离开。"
    last4 = messages[-8:]  # 最近 4 轮 = 4 user + 4 assistant
    c_messages = [{"role": "system", "content": system + "\n\n[历史摘要]\n" + summary}]
    c_messages.extend(last4)
    for i, prompt in enumerate(C_TURNS, 1):
        c_messages.append({"role": "user", "content": prompt})
        result = run_one(args.url, args.model, c_messages, 768, 9100 + i, args.timeout)
        record("C_cross_session", i, prompt, result)
        c_messages.append({"role": "assistant", "content": result["assistant"]})

    out["completed_at"] = datetime.now().astimezone().isoformat(timespec="seconds")
    args.output.write_text(json.dumps(out, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(f"DONE: A={len(out['segments']['A_long_session'])} B={len(out['segments']['B_context_stress'])} C={len(out['segments']['C_cross_session'])}", flush=True)


if __name__ == "__main__":
    main()
