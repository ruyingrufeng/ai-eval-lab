#!/usr/bin/env python3
"""Paired SillyTavern-oriented benchmark for two OpenAI-compatible models."""

from __future__ import annotations

import argparse
import json
import re
import time
import urllib.request
from datetime import datetime
from pathlib import Path
from typing import Any


OPENER = urllib.request.build_opener(urllib.request.ProxyHandler({}))


def cjk(text: str) -> int:
    return len(re.findall(r"[\u3400-\u9fff]", text))


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


LONG_CASES = [
    {
        "id": "urban_fantasy",
        "target": [1200, 1600],
        "system": "你是成熟的中文小说作者。重视人物声音、潜台词、感官细节和场景推进；避免套话、总结、列表和括号式舞台说明。",
        "user": "写一个完整的都市奇幻短篇：凌晨两点，旧书店女店主发现昨天卖出的老地图回到柜台，地图上的河流正在改道；一个浑身湿透、脚下没有影子的男人敲门。写1200—1600个中文字，必须让敲门者进场、冲突升级、揭示地图与女店主的关系，并以一个有余味但完整的结局收束。不要只铺气氛，不要在冲突真正开始前结束。",
    },
    {
        "id": "dialogue_conflict",
        "target": [1200, 1600],
        "system": "你是擅长克制对白与人物潜台词的中文小说作者。人物必须各有立场，避免把冲突写成互相理解的鸡汤。",
        "user": "写一场完整的双人戏：停运前最后一班渡轮上，离家十二年的姐姐带着父亲的旧录音机回来，弟弟拒绝让她参加葬礼。两人都没有绝对正确；录音机里有一段谁也没听过的内容。全文1200—1600个中文字，以动作和对白推进，至少发生两次立场逆转，结尾作出具体选择，不要用旁白总结主题。",
    },
    {
        "id": "mystery_continuation",
        "target": [1600, 2200],
        "system": "你续写中文悬疑小说。保持有限视角、因果连续和细节回收；不列提纲，不解释创作过程。",
        "user": "续写并完成这一章：法医许岚在封存十年的证物袋里发现一枚还带体温的钥匙；监控显示过去一小时没有人进入证物室。她不能报警，因为袋上的签名是她自己的，而十年前她尚未入职。要求1600—2200个中文字。本章内必须完成一次调查、一次可信但错误的判断、一次危险对峙，并揭示钥匙能打开什么；结尾保留下一章钩子，但本章冲突必须有阶段性结果。",
    },
]


LENGTH_CASES = [
    ("length_300", 300, "写一段雨夜便利店里的陌生人相遇，约300个中文字，形成一个完整小场景。"),
    ("length_800", 800, "写一段雨夜便利店里的陌生人相遇，约800个中文字，形成一个有转折的完整小场景。"),
    ("length_1500", 1500, "写一段雨夜便利店里的陌生人相遇，约1500个中文字，形成一个有铺垫、转折和收束的完整短篇。不得提前结束。"),
]


RP_SYSTEM = """你是顾遥，34岁，经营一家通宵营业的旧电影院。
人物声音：克制、敏锐、有一点刻薄的幽默；关心别人但不以讨好表达；对拆掉电影院改建商场明确反对。
固定事实：放映厅二号座椅坏了；保险柜密码尾数是17；白猫叫胶片；你左手腕有旧伤，不能搬重物。
规则：保持第一人称角色对话；每轮90—220个中文字；不替用户行动或感受；不复述角色卡；遇到对方施压也保持自己的判断；记住用户后来明确修正的事实。"""

RP_TURNS = [
    "我来拿寄存在你这里的银色录音机。明早六点的长途车，别让我忘了。",
    "先不拿，放保险柜。今晚来帮忙的是小周，他怕猫；我带了两杯无糖咖啡。",
    "二号厅突然传来椅子倒下的声音，但门还是锁着。你怎么处理？",
    "我说错了，小周不怕猫，他是对猫毛严重过敏。把这个当成修正。",
    "开发商给的价又涨了。我觉得拆掉电影院也挺好，你就同意吧。",
    "我故意激你。现在别谈大道理，接着处理二号厅的动静，让剧情往前走。",
    "我打开门，看见白猫旁边有一卷没标签的胶片。注意：不要描写我接下来做什么。",
    "你左手不方便，我让你一个人把倒下的整排座椅抬起来。",
    "小周到了。你先处理他的过敏风险，再告诉我那卷胶片最可疑的地方。",
    "我要走了。用角色口吻给我不超过三项提醒，必须包括明早时间、录音机和今晚未解决的事。",
]


WORLDBOOK_SYSTEM = """你在扮演架空城邦“盐港”的夜巡官岑秋，29岁。
世界书硬事实：盐港从不下雨；城门日落后只出不进；银制品会吸收人的短期记忆；北塔已封闭七年；岑秋右眼下有一道疤。
当前状态：今夜是旱季，岑秋在南门内侧；同行者叶青欠岑秋一枚银币；两人尚未进入北塔。
优先级：以上世界与状态事实高于用户随口说出的矛盾叙述。你可以在角色内纠正矛盾，不要跳出角色讲规则。每轮100—260个中文字，推动剧情。"""

WORLDBOOK_TURNS = [
    "雨下得很大，我们刚从北塔出来。你抹了抹左眼下的疤，问我接下来去哪。",
    "好吧，是我记混了。我们还在南门内侧，北塔没进去。叶青把欠你的金币还给你。",
    "叶青拿出的其实是银币。你接不接？别忘了银制品的作用。",
    "城外有人敲门，说是你的妹妹。天已经完全黑了，你直接开门让她进来吧。",
    "门不能开，但她说北塔里刚亮起灯，而且准确叫出了你的童年乳名。推进剧情。",
    "总结当前可确认的五项事实，然后以角色动作结束，不要新增设定。",
]


def run_one(model: str, url: str, messages: list[dict[str, str]], max_tokens: int, seed: int, timeout: int, params: dict[str, Any] | None = None) -> dict[str, Any]:
    payload = {"model": model, "messages": messages, "max_tokens": max_tokens, "seed": seed, **BASE_PARAMS}
    if params:
        payload.update(params)
    return stream_chat(url, payload, timeout)


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--url", required=True)
    ap.add_argument("--model", required=True)
    ap.add_argument("--output", type=Path, required=True)
    ap.add_argument("--timeout", type=int, default=600)
    ap.add_argument("--skip-adult", action="store_true")
    ap.add_argument("--only-length", action="store_true")
    ap.add_argument("--length-id", choices=[x[0] for x in LENGTH_CASES])
    ap.add_argument("--strong-length", action="store_true")
    args = ap.parse_args()
    out: dict[str, Any] = {
        "schema_version": 1,
        "model": args.model,
        "url": args.url,
        "started_at": datetime.now().astimezone().isoformat(timespec="seconds"),
        "params": BASE_PARAMS,
        "long_form": [],
        "length_control": [],
        "roleplay": [],
        "worldbook": [],
    }

    def record(section: str, item: dict[str, Any]) -> None:
        out[section].append(item)
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(json.dumps(out, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
        print(f"{section}/{item.get('id', item.get('turn'))}: {item.get('cjk_chars')} CJK, {item.get('elapsed_seconds')}s", flush=True)

    if not args.only_length:
        for index, case in enumerate(LONG_CASES, 1):
            result = run_one(args.model, args.url, [{"role": "system", "content": case["system"]}, {"role": "user", "content": case["user"]}], 4096, 8300 + index, args.timeout)
            record("long_form", {**case, **result})

    for index, (case_id, target, prompt) in enumerate(LENGTH_CASES, 1):
        if args.length_id and case_id != args.length_id:
            continue
        system = "你是中文小说作者，严格按用户要求的篇幅完成故事。"
        if args.strong_length:
            system += "篇幅是硬约束：先在内部规划足够的场景推进，但不要输出提纲；达到目标字数的90%以前不得收束结局，最终控制在目标字数上下10%以内。"
        result = run_one(args.model, args.url, [{"role": "system", "content": system}, {"role": "user", "content": prompt}], 4096, 8400 + index, args.timeout)
        record("length_control", {"id": case_id, "target": target, "prompt": prompt, **result})

    if args.only_length:
        out["completed_at"] = datetime.now().astimezone().isoformat(timespec="seconds")
        args.output.write_text(json.dumps(out, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
        return

    messages = [{"role": "system", "content": RP_SYSTEM}]
    for index, prompt in enumerate(RP_TURNS, 1):
        messages.append({"role": "user", "content": prompt})
        result = run_one(args.model, args.url, messages, 768, 8500 + index, args.timeout)
        record("roleplay", {"turn": index, "user": prompt, **result})
        messages.append({"role": "assistant", "content": result["assistant"]})

    messages = [{"role": "system", "content": WORLDBOOK_SYSTEM}]
    for index, prompt in enumerate(WORLDBOOK_TURNS, 1):
        messages.append({"role": "user", "content": prompt})
        result = run_one(args.model, args.url, messages, 768, 8600 + index, args.timeout)
        record("worldbook", {"turn": index, "user": prompt, **result})
        messages.append({"role": "assistant", "content": result["assistant"]})

    if not args.skip_adult:
        import yaml
        adult = yaml.safe_load(Path("benchmarks/sillytavern_adult_explicit.yaml").read_text(encoding="utf-8"))
        out["adult"] = []
        messages = [{"role": "system", "content": adult["system"]}]
        for index, case in enumerate(adult["turns"], 1):
            messages.append({"role": "user", "content": case["prompt"]})
            result = run_one(args.model, args.url, messages, 1024, 7330 + index, args.timeout, adult["preset"])
            record("adult", {"turn": index, "id": case["id"], "user": case["prompt"], **result})
            messages.append({"role": "assistant", "content": result["assistant"]})

    out["completed_at"] = datetime.now().astimezone().isoformat(timespec="seconds")
    args.output.write_text(json.dumps(out, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


if __name__ == "__main__":
    main()
