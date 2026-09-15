#!/usr/bin/env python3
"""Fish S2 Pro follow-up Phase P/R/A control script.

Subcommands:
    prepare  — freeze the test matrix, compute hashes, allocate run directory.
    check    — validate the prepared run without loading Fish or ASR.
    status   — print the live status of a run (no model interaction).
    analyze  — post-run summariser that produces summary.json / artifact.json.

This file is the only entry point the 27B Agent should call during Phase P.
It must not import mlx, mlx_speech or load any large model weights.
"""
from __future__ import annotations

import argparse
import datetime as dt
import hashlib
import json
import os
import platform
import re
import shutil
import socket
import subprocess
import sys
import textwrap
import time
from pathlib import Path
from typing import Any, Iterable

# --------------------------------------------------------------------------- #
# Paths and constants
# --------------------------------------------------------------------------- #

ROOT = Path(__file__).resolve().parents[1]
DEPLOY = Path("/Users/jacky/Documents/Codex/2026-09-03/referenced-chatgpt-conversation-this-is-an/outputs/fish-s2-local")
DEPLOY_VENV = DEPLOY / ".venv"
DEPLOY_PYTHON = DEPLOY_VENV / "bin" / "python"
RUNNER = ROOT / "scripts" / "fish-s2-followup-runner.py"
MONITOR = ROOT / "scripts" / "fish-s2-followup-monitor.py"
LAUNCHER = ROOT / "scripts" / "start-fish-s2-followup.sh"

BENCHMARK = ROOT / "benchmarks" / "fish_s2_pro_followup_20260903.yaml"
PLAN = ROOT / "docs" / "FISH_S2_27B_TEST_PLAN_20260903.md"
LEGACY_RESULTS = ROOT / "results" / "fish_s2_pro_mlx_20260903"

GIB = 1024 ** 3

# Plan §6 thresholds
SAMPLE_INTERVAL_S = 2.0
EXTERNAL_LOAD_INTERVAL_S = 5.0
THERMAL_INTERVAL_S = 30.0
DISK_FREE_MIN_GIB = 20.0
STOP_SWAP_DELTA_GIB = 2.0
STOP_SWAP_PER_MIN_GIB = 1.0
STOP_MEM_FREE_PCT = 10.0
STOP_MEM_LOW_CONSECUTIVE = 3
STOP_MISSING_FIELD_CONSECUTIVE = 3

GENERATION_TIMEOUT_S = 180.0
ASR_TIMEOUT_S = 120.0
HEARTBEAT_TIMEOUT_S = 30.0
TOTAL_WALL_MIN = 120
FISH_WALL_MIN = 90

# Acceptance targets (proposed, not measured)
ACCEPTANCE = {
    "first_attempt_completion_rate": 1.0,
    "weighted_rtf_max": 3.0,
    "per_clip_rtf_p95_max": 5.0,
    "anchor_rtf_slowdown_max": 0.30,
    "routine_swap_delta_max_gib": 1.0,
    "weighted_cer_max": 0.08,
    "per_clip_cer_review_above": 0.15,
    "asr_length_ratio_review_outside": [0.85, 1.15],
    "confirmed_content_errors_allowed": 0,
    "assembled_duration_error_max_seconds": 0.1,
    "clipped_fraction_max": 0.0001,
}

STATUS_VALUES = {
    "prepared", "waiting_for_unload", "running", "aborted", "failed",
    "awaiting_human_review", "completed",
}


# --------------------------------------------------------------------------- #
# Synthetic, neutral, fictional-adult chapter and edge-case text.
# Frozen once prepare runs; do not edit at run time.
# --------------------------------------------------------------------------- #

CHAPTER_TEMPLATE = (
    "{intro_1}\n"
    "{line_a1}\n"
    "{line_b1}\n"
    "{intro_2}\n"
    "{line_a2}\n"
    "{line_b2}\n"
    "{narrator_mid_1}\n"
    "{line_a3}\n"
    "{line_b3}\n"
    "{narrator_mid_2}\n"
    "{line_a4}\n"
    "{line_b4}\n"
    "{narrator_close_1}\n"
    "{narrator_close_2}\n"
    "{narrator_end}"
)

NARRATOR_VOICE = "narrator"     # uses samples/01-basic-zh.wav
ROLE_A_VOICE = "A"               # uses references/voice-a.wav
ROLE_B_VOICE = "B"               # uses references/voice-b.wav

# Fictional adult characters in the neutral chapter. Total target
# 1200–1600 Chinese characters before segmentation.
CHAPTER = {
    "intro_1": "夜色已经很深了。林薇停在旧仓库门口，回头看了看陈川。风把远处的狗叫声送过来，又慢慢散掉。仓库边上的老槐树被风吹得沙沙作响，几片枯叶飘到了他们脚边。天上没有月亮，只有几颗暗暗的星星挂在天边，远处镇子上的灯火一闪一闪，像是有人在那边守着夜。河岸那边的芦苇被吹得倒伏下来，又慢慢直起身。",
    "intro_2": "陈川把手搭在铁锁上，锁早已生锈，他稍稍用力，锁便咔嗒一声打开了。门缝里透出一点微弱的灯光，地板上落着厚厚的灰尘。空气里有一种旧木头发霉的味道，让人忍不住皱起眉头。他下意识地把林薇往身后挡了挡，又朝她点了点头，让她贴在自己背后。",
    "line_a1": "[whisper]你刚才听到了吗？门后面好像有人在翻东西。我先过去看一眼，你在门口替我把风。如果我敲门三下，你就跑。",
    "line_b1": "[low voice]别怕，我在这里。你退后一点，我来开门。先把灯打开，看看里面到底是什么。如果有人，先别出声。",
    "line_a2": "[whisper]这扇门以前从来没有人用过，今晚为什么有人来？这件事有点奇怪，我心里一直放不下。",
    "line_b2": "[low voice]也许只是过路人，我们先看清楚再说。如果情况不对，我们立刻退出去，先回镇上再说。",
    "narrator_mid_1": "仓库里堆着几摞旧木箱，角落里放着一张折叠床，床上的被褥已经看不出原来的颜色。灯泡在头顶摇摇晃晃，把两个人的影子拉得很长很长。空气里有一种发霉的味道，让人忍不住皱起眉头。木箱上落满了灰，几只小虫子在灰尘里慢慢爬过去。",
    "line_a3": "[excited]原来是那只小猫！真是吓死我了。它缩在木箱后面，肚皮一起一伏，看起来又冷又饿。",
    "line_b3": "[chuckle]走吧，我们带它一起回家，今晚就让它住我房间。明天再带它去兽医那里检查一下，看看它到底有没有受伤，要不要打一针。",
    "narrator_mid_2": "陈川脱下外套，把小猫轻轻裹住。林薇弯腰把那碗放了一夜的牛奶端过来，小心地放在地上。小猫犹豫了一会儿，慢慢地凑了过去，开始舔。它的尾巴尖微微地翘起来，像是在试探。",
    "line_a4": "[excited]回去我给它热一点牛奶，它看起来很饿。我家里还有几条小毛巾，正好可以给它垫一下，让它先暖暖身子。",
    "line_b4": "[low voice]我们慢慢走，别惊到它，让它自己跟上。路上如果有车，我们先把它抱起来，过完马路再放它下来。前面那盏路灯有点闪，我们绕一下。",
    "narrator_close_1": "风停了一下，又重新吹起来。两个人走出仓库，把门轻轻带上。灯泡在他们身后又晃了几下，然后熄灭了。夜色依旧很静，只有他们两个的脚步声轻轻地响，远处的狗叫声也听不到了。仓库外面那盏路灯又亮了起来，把他们的影子重新照回到墙上。",
    "narrator_close_2": "街灯把两个人的影子拉得很长，小猫在他们脚边轻轻地叫了一声，像是在和他们说话。林薇笑了一下，弯腰把小猫抱了起来。三个人沿着河岸慢慢往前走，河水在桥下静静地流。远处有几只夜鸟从芦苇丛里飞起来，又轻轻落下。",
    "narrator_end": "风把树叶吹得沙沙响，远处的狗叫声已经听不见了。三个人沿着河岸慢慢往前走，谁也没有说话，但心里都觉得踏实了许多。夜色依旧很静，但他们已经不再害怕了，因为小猫蜷在他们怀里，像一团暖暖的小毛球，正在轻轻地打着呼噜。",
}

EDGE_CASES = [
    {  # T2-1: numbers and date
        "id": "T2_1_date_numbers",
        "category": "数字与日期",
        "text": "今年是一九四五年八月十五日晚上十点三十七分，我们要在凌晨两点之前把东西送过去。",
    },
    {  # T2-2: polyphonic characters
        "id": "T2_2_polyphone",
        "category": "多音字",
        "text": "他在银行里给行长行长的工作报告，行长把报告里的行长二字圈了出来。",
    },
    {  # T2-3: punctuation and pauses
        "id": "T2_3_pause",
        "category": "停顿与标点",
        "text": "停一下……听，那边有人在叫。等一下，我先过去看。",
    },
    {  # T2-4: continuous dialogue
        "id": "T2_4_dialogue",
        "category": "连续对白",
        "text": "[whisper]你先进去。[whisper]我跟在后面。[whisper]小心台阶。",
    },
    {  # T2-5: emotion switch
        "id": "T2_5_emotion_switch",
        "category": "情绪转换",
        "text": "[excited]我们终于做到了！[sad]可是大家都没能一起等到这一天。",
    },
    {  # T2-6: name and abbreviation
        "id": "T2_6_names",
        "category": "专有名词",
        "text": "FBE 实验室的林博士、Chen 教授、Helen 工程师，今天下午两点半要在三号楼 B 区见面。",
    },
]

EMOTION_TEST_SENTENCE = "今天的夜色很静，我们沿着河岸一路走过去，谁也没有开口说话。"
EMOTION_TAGS = {
    "neutral": "",
    "excited": "[excited]",
    "sad": "[sad]",
}
ROLE_TEXT = {  # identical text per role to compare voice identity vs emotion
    "narrator": "夜色越来越深，远处的灯光也一点点地暗下去。",
    "A": "你终于回来了。我在这里等了很久，还以为今天见不到你了。",
    "B": "别担心，我已经检查过四周。风停了，我们可以继续往前走。",
}
ANCHOR_TEXT = {  # identical text per role across start/middle/end
    "narrator": "故事发生在深秋的一个晚上，仓库外面的街灯被风吹得直晃。",
    "A": "你终于回来了，我还以为再也见不到你了。",
    "B": "我们已经检查过四周，可以放心往前走了。",
}
T5_PAD_TEXT = "她沿着河岸慢慢走，把外衣领子竖起来，听着水流的声音。"


# --------------------------------------------------------------------------- #
# Helpers
# --------------------------------------------------------------------------- #

def sha256_file(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as f:
        for chunk in iter(lambda: f.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def sha256_text(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def now_iso() -> str:
    return dt.datetime.now().astimezone().isoformat()


def utc_offset() -> int:
    return int(time.localtime().tm_gmtoff)


def write_json(path: Path, obj: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(obj, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def append_jsonl(path: Path, obj: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("a", encoding="utf-8") as f:
        f.write(json.dumps(obj, ensure_ascii=False) + "\n")
        f.flush()
        os.fsync(f.fileno())


def write_atomic(path: Path, content: bytes | str) -> None:
    """Write to a sibling temp file, fsync, then atomically rename."""
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(path.suffix + ".tmp")
    if isinstance(content, str):
        tmp.write_text(content, encoding="utf-8")
    else:
        tmp.write_bytes(content)
    os.replace(tmp, path)


def load_yaml_simple(path: Path) -> dict:
    import yaml
    return yaml.safe_load(path.read_text(encoding="utf-8"))


def segment_chapter(text: str, target_min: int = 40, target_max: int = 60,
                    hard_max: int = 80, max_segments: int = 40) -> list[str]:
    """Split chapter into 40-60 char segments (max 80), respecting sentence boundaries."""
    # Normalise line breaks.
    raw = re.sub(r"\s+", " ", text.strip())
    # Sentence split keeping Chinese punctuation.
    parts = re.split(r"(?<=[。！？!?\.])\s*", raw)
    parts = [p.strip() for p in parts if p.strip()]
    segments: list[str] = []
    cur = ""
    for s in parts:
        if len(s) > hard_max:
            # Hard-split a too-long sentence at last comma before hard_max.
            mid = s.rfind("，", 0, hard_max)
            if mid < target_min:
                mid = s.rfind("、", 0, hard_max)
            if mid < target_min:
                mid = hard_max
            segments.append(s[:mid].strip())
            rest = s[mid:].strip()
            if rest:
                segments.append(rest)
            cur = ""
            continue
        if not cur:
            cur = s
            continue
        if len(cur) + len(s) <= target_max:
            cur = cur + s
        else:
            segments.append(cur)
            cur = s
    if cur:
        segments.append(cur)
    # Coalesce tiny trailing segments (<target_min) into the previous one.
    out: list[str] = []
    for seg in segments:
        if out and len(seg) < target_min and len(out[-1]) + len(seg) <= hard_max:
            out[-1] = out[-1] + seg
        else:
            out.append(seg)
    # Final safety cap.
    if len(out) > max_segments:
        # Coalesce from the end until <= max_segments.
        while len(out) > max_segments and len(out) >= 2:
            out[-2] = out[-2] + out[-1]
            out.pop()
    return out


def atomic_rename(src: Path, dst: Path) -> None:
    dst.parent.mkdir(parents=True, exist_ok=True)
    os.replace(src, dst)


def host_fingerprint() -> dict:
    return {
        "host": socket.gethostname(),
        "platform": platform.platform(),
        "machine": platform.machine(),
        "system": platform.system(),
        "release": platform.release(),
        "python": sys.version.split()[0],
        "utc_offset_seconds": utc_offset(),
        "captured_at": now_iso(),
    }


def git_state() -> dict:
    repo = ROOT
    if not (repo / ".git").exists():
        return {"has_git": False}
    try:
        head = subprocess.check_output(["git", "-C", str(repo), "rev-parse", "HEAD"], text=True).strip()
        branch = subprocess.check_output(["git", "-C", str(repo), "rev-parse", "--abbrev-ref", "HEAD"], text=True).strip()
        status = subprocess.check_output(["git", "-C", str(repo), "status", "--short"], text=True)
    except subprocess.CalledProcessError as exc:
        return {"has_git": True, "error": str(exc)}
    return {
        "has_git": True,
        "head": head,
        "branch": branch,
        "status_short": status,
        "uncommitted_modifications": bool(status.strip()),
    }


def get_run_paths(run_id: str) -> dict[str, Path]:
    project_results = ROOT / "results" / run_id
    deploy_experiments = DEPLOY / "experiments" / run_id
    report_dir = ROOT / "docs" / "reports" / run_id
    return {
        "project_results": project_results,
        "deploy_experiments": deploy_experiments,
        "report_dir": report_dir,
        "config_dir": project_results / "config",
        "logs_dir": project_results / "logs",
        "audio_dir": project_results / "audio",
        "asr_dir": project_results / "asr",
        "assembled_dir": project_results / "assembled",
        "deploy_audio_dir": deploy_experiments / "audio",
        "deploy_refs_dir": deploy_experiments / "references",
        "deploy_texts_dir": deploy_experiments / "texts",
        "deploy_assembled_dir": deploy_experiments / "assembled",
    }


def status_path(run_id: str) -> Path:
    return ROOT / "results" / run_id / "status.json"


def load_status(run_id: str) -> dict:
    p = status_path(run_id)
    if not p.exists():
        return {"run_id": run_id, "state": "missing"}
    return json.loads(p.read_text(encoding="utf-8"))


def write_status(run_id: str, payload: dict) -> None:
    payload.setdefault("run_id", run_id)
    payload.setdefault("updated_at", now_iso())
    write_atomic(status_path(run_id), json.dumps(payload, ensure_ascii=False, indent=2))


def update_status(run_id: str, **fields) -> None:
    current = load_status(run_id)
    current.update(fields)
    current["updated_at"] = now_iso()
    write_status(run_id, current)


# --------------------------------------------------------------------------- #
# prepare: freeze the test matrix onto disk and allocate run directory.
# --------------------------------------------------------------------------- #

def build_test_matrix() -> dict[str, Any]:
    """Build the frozen, hash-bound task manifest.

    Order policy: T4 anchors go to the front, middle and tail of the queue.
    The tail anchor sits AFTER any T5 padding inserted to reach >=30 min.
    Stage ordering is captured in `execution_order` so the runner does not
    need to recompute it.
    """
    benchmark = load_yaml_simple(BENCHMARK)
    matrix = {"benchmark": str(BENCHMARK.relative_to(ROOT)),
              "plan": str(PLAN.relative_to(ROOT)),
              "frozen_at": now_iso(),
              "cases": {}}

    # ---- T0: historical retest — same inputs, seeds and parameters. ----
    legacy_validation = LEGACY_RESULTS / "logs" / "validation.jsonl"
    t0_rows = []
    if legacy_validation.exists():
        for line in legacy_validation.read_text(encoding="utf-8").splitlines():
            try:
                rec = json.loads(line)
            except json.JSONDecodeError:
                continue
            if rec.get("event") == "generated":
                t0_rows.append(rec)
    # Map historical names → role_id.  Per plan, T0 does NOT re-extract voices
    # (voice_a_reference & voice_b_reference originally created references),
    # so in retest we reuse the existing voice-a.wav / voice-b.wav with the
    # same text+seed+max_new_tokens.  basic_zh & speaker_tags_experimental
    # were no-reference generations in round 1; we keep them that way.
    t0_role_map = {
        "basic_zh": "narrator",
        "voice_a_reference": ROLE_A_VOICE,
        "voice_b_reference": ROLE_B_VOICE,
        "clone_neutral": ROLE_A_VOICE,
        "clone_excited": ROLE_A_VOICE,
        "clone_sad": ROLE_A_VOICE,
        "speaker_tags_experimental": None,           # no-reference in round 1
        "scene_1_narrator": "narrator",
        "scene_2_A": ROLE_A_VOICE,
        "scene_3_B": ROLE_B_VOICE,
        "scene_4_narrator": "narrator",
        "scene_5_A": ROLE_A_VOICE,
        "scene_6_B": ROLE_B_VOICE,
    }
    t0_clips = []
    for rec in t0_rows:
        clip_id = f"T0_{rec['name']}"
        role_id = t0_role_map.get(rec["name"], "narrator")
        t0_clips.append({
            "case_id": clip_id,
            "group": "T0",
            "role_id": role_id,
            "text": rec.get("text"),
            "reference_audio": None,  # resolved by snapshot_references
            "reference_text": None,    # resolved by snapshot_references
            "uses_reference": role_id is not None,
            "seed": rec.get("seed"),
            "max_new_tokens": rec.get("max_new_tokens", 512),
            "config_hash": sha256_text(json.dumps({
                "seed": rec.get("seed"), "max_new_tokens": rec.get("max_new_tokens"),
                "role_id": role_id, "name": rec.get("name")}, ensure_ascii=False)),
            "input_hash": sha256_text(rec.get("text", "")),
            "reference_hash": None,
            "position_in_run": None,
            "expected_path": str(Path("audio") / f"{clip_id}.wav"),
        })
    matrix["cases"]["T0"] = {
        "kind": "historical_matched_retest",
        "description": "Re-run T0 historical clips with identical inputs/seeds. References not re-extracted.",
        "expected_clips": len(t0_clips),
        "clips": t0_clips,
    }

    # ---- T1: synthetic chapter segmentation. ----
    # The chapter is already authored as a sequence of speaker turns (one
    # role per block in CHAPTER).  We keep that mapping and segment each
    # turn into 40–80-char chunks at sentence boundaries so the role_id
    # of every segment is unambiguous (no cross-speaker segments).
    chapter_turns: list[tuple[str, str]] = []  # (role_id, text)
    template_order = [
        ("narrator", "intro_1"),
        (ROLE_A_VOICE, "line_a1"),
        (ROLE_B_VOICE, "line_b1"),
        ("narrator", "intro_2"),
        (ROLE_A_VOICE, "line_a2"),
        (ROLE_B_VOICE, "line_b2"),
        ("narrator", "narrator_mid_1"),
        (ROLE_A_VOICE, "line_a3"),
        (ROLE_B_VOICE, "line_b3"),
        ("narrator", "narrator_mid_2"),
        (ROLE_A_VOICE, "line_a4"),
        (ROLE_B_VOICE, "line_b4"),
        ("narrator", "narrator_close_1"),
        ("narrator", "narrator_close_2"),
        ("narrator", "narrator_end"),
    ]
    for role_id, key in template_order:
        chapter_turns.append((role_id, CHAPTER[key]))
    chapter_text = "\n".join(t for _, t in chapter_turns)
    t1_clips = []
    seg_idx = 0
    for turn_role, turn_text in chapter_turns:
        # Drop explicit role tag if present (the model may or may not respect it
        # — keep the tag intact, but it does not change the speaker identity
        # for our metrics).
        turn_chunks = segment_chapter(turn_text)
        for chunk in turn_chunks:
            seg_idx += 1
            clip_id = f"T1_chapter_seg{seg_idx:02d}"
            t1_clips.append({
                "case_id": clip_id,
                "group": "T1",
                "role_id": turn_role,
                "text": chunk,
                "reference_audio": None,
                "reference_text": None,
                "seed": 42,
                "max_new_tokens": 512,
                "config_hash": sha256_text(f"T1:{turn_role}:42:512:{seg_idx}"),
                "input_hash": sha256_text(chunk),
                "reference_hash": None,
                "position_in_run": None,
                "expected_path": str(Path("audio") / f"{clip_id}.wav"),
            })
    # Apply the hard 40-segment cap from the plan.
    if len(t1_clips) > 40:
        # Coalesce adjacent chunks of the same role (last-in-first-out).
        while len(t1_clips) > 40:
            # Find last adjacent same-role pair and merge.
            merged = False
            for i in range(len(t1_clips) - 1, 0, -1):
                if t1_clips[i]["role_id"] == t1_clips[i - 1]["role_id"]:
                    t1_clips[i - 1]["text"] = t1_clips[i - 1]["text"] + t1_clips[i]["text"]
                    t1_clips[i - 1]["input_hash"] = sha256_text(t1_clips[i - 1]["text"])
                    t1_clips[i - 1]["config_hash"] = sha256_text(
                        f"T1:{t1_clips[i-1]['role_id']}:42:512:merged")
                    t1_clips[i - 1]["case_id"] = (
                        f"T1_chapter_seg{int(t1_clips[i-1]['case_id'].split('seg')[1]):02d}"
                    )
                    t1_clips.pop(i)
                    merged = True
                    break
            if not merged:
                break  # can't merge further without crossing roles; bail out.
    # Renumber after coalescing.
    for i, clip in enumerate(t1_clips, 1):
        clip["case_id"] = f"T1_chapter_seg{i:02d}"
    matrix["cases"]["T1"] = {
        "kind": "synthetic_chapter",
        "description": "Frozen chapter split at sentence boundaries; narrator/A/B per segment heuristics.",
        "chapter_char_count": len(chapter_text.replace("\n", "")),
        "chapter_text_hash": sha256_text(chapter_text),
        "expected_clips": len(t1_clips),
        "clips": t1_clips,
    }

    # ---- T2: edge cases × extra seeds (123, 321). ----
    t2_clips = []
    for edge in EDGE_CASES:
        for seed in (42, 123, 321):  # 42 used to keep parity with main suite
            cid = f"{edge['id']}_seed{seed}"
            t2_clips.append({
                "case_id": cid,
                "group": "T2",
                "role_id": NARRATOR_VOICE,
                "text": edge["text"],
                "reference_audio": None,
                "reference_text": None,
                "seed": seed,
                "max_new_tokens": 512,
                "config_hash": sha256_text(f"T2:{edge['id']}:{seed}:512"),
                "input_hash": sha256_text(edge["text"]),
                "reference_hash": None,
                "position_in_run": None,
                "expected_path": str(Path("audio") / f"{cid}.wav"),
                "category": edge["category"],
            })
    matrix["cases"]["T2"] = {
        "kind": "edge_cases_repeat",
        "description": "6 difficult segments × 3 seeds to expose one-shot flukes.",
        "expected_clips": 18,
        "clips": t2_clips,
    }

    # ---- T3: same reference + same text + 3 emotions × 2 seeds. ----
    t3_clips = []
    for role_id in ("narrator", ROLE_A_VOICE, ROLE_B_VOICE):
        text = ROLE_TEXT[role_id]
        for emotion in ("neutral", "excited", "sad"):
            for seed in (42, 123):
                tag = EMOTION_TAGS[emotion]
                synth_text = (tag + text) if tag else text
                cid = f"T3_{role_id}_{emotion}_seed{seed}"
                t3_clips.append({
                    "case_id": cid,
                    "group": "T3",
                    "role_id": role_id,
                    "text": synth_text,
                    "reference_audio": None,
                    "reference_text": ROLE_TEXT[role_id],
                    "seed": seed,
                    "max_new_tokens": 512,
                    "config_hash": sha256_text(f"T3:{role_id}:{emotion}:{seed}:512"),
                    "input_hash": sha256_text(synth_text),
                    "reference_hash": None,
                    "position_in_run": None,
                    "expected_path": str(Path("audio") / f"{cid}.wav"),
                    "emotion": emotion,
                })
    matrix["cases"]["T3"] = {
        "kind": "role_emotion",
        "description": "Same role / same text / 3 emotions × 2 seeds; tests emotion without voice drift.",
        "expected_clips": 18,
        "clips": t3_clips,
    }

    # ---- T4: identical role anchors at start / middle / end. ----
    t4_clips = []
    for role_id in ("narrator", ROLE_A_VOICE, ROLE_B_VOICE):
        for position in ("start", "middle", "end"):
            cid = f"T4_{role_id}_{position}"
            t4_clips.append({
                "case_id": cid,
                "group": "T4",
                "role_id": role_id,
                "text": ANCHOR_TEXT[role_id],
                "reference_audio": None,
                "reference_text": ANCHOR_TEXT[role_id],
                "seed": 42,
                "max_new_tokens": 512,
                "config_hash": sha256_text(f"T4:{role_id}:{position}:42:512"),
                "input_hash": sha256_text(ANCHOR_TEXT[role_id]),
                "reference_hash": None,
                "position_in_run": position,  # semantic position
                "expected_path": str(Path("audio") / f"{cid}.wav"),
            })
    matrix["cases"]["T4"] = {
        "kind": "identical_role_anchors",
        "description": "Same role / same text / same seed at start, middle and end of queue.",
        "expected_clips": 9,
        "clips": t4_clips,
    }

    # ---- T5: padding with a single neutral short text until >=30 active min
    # OR until the cumulative task count including T5 reaches 120. ----
    # Each generated clip averages ~25s of generation (legacy). We estimate
    # ~28s to be conservative and refit after Phase R baseline is captured.
    matrix["cases"]["T5"] = {
        "kind": "sustained_generation",
        "description": "Same neutral short text used as filler to reach >=30 active min or 120 total tasks.",
        "padding_text": T5_PAD_TEXT,
        "padding_role": "narrator",
        "padding_seed": 42,
        "max_new_tokens": 512,
        "padding_template": {
            "case_id_prefix": "T5_padding",
            "text": T5_PAD_TEXT,
            "group": "T5",
            "role_id": "narrator",
            "reference_audio": None,
            "reference_text": None,
            "seed": 42,
            "max_new_tokens": 512,
            "config_hash": sha256_text("T5:padding:42:512"),
            "input_hash": sha256_text(T5_PAD_TEXT),
            "reference_hash": None,
            "expected_path_pattern": "audio/T5_padding_{index:03d}.wav",
        },
        "minimum_active_minutes": benchmark["cases"]["T5"]["minimum_active_minutes"],
        "maximum_total_generation_tasks": benchmark["cases"]["T5"]["maximum_total_generation_tasks"],
        "min_active_seconds_per_clip_estimate": 28.0,
    }

    return matrix


def snapshot_references(matrix: dict, deploy_refs_dir: Path, project_refs_dir: Path) -> dict[str, dict]:
    """Copy reference audio (and the narrator reference WAV) into the run directory,
    record pre/post SHA-256, and bind reference_hash / reference_audio path into
    every clip that needs it.

    Returns the reference map keyed by role_id.
    """
    sources = {
        NARRATOR_VOICE: (DEPLOY / "samples" / "01-basic-zh.wav",
                         "夜色渐深，远处传来了轻轻的脚步声。她停下脚步，认真地听着。"),
        ROLE_A_VOICE: (DEPLOY / "references" / "voice-a.wav",
                       "你终于回来了。我在这里等了很久，还以为今天见不到你了。"),
        ROLE_B_VOICE: (DEPLOY / "references" / "voice-b.wav",
                       "别担心，我已经检查过四周。风停了，我们可以继续往前走。"),
    }
    deploy_refs_dir.mkdir(parents=True, exist_ok=True)
    project_refs_dir.mkdir(parents=True, exist_ok=True)
    ref_map: dict[str, dict] = {}
    for role_id, (src_path, ref_text) in sources.items():
        if not src_path.exists():
            raise FileNotFoundError(f"Reference audio missing for {role_id}: {src_path}")
        src_size = src_path.stat().st_size
        src_sha = sha256_file(src_path)
        deploy_target = deploy_refs_dir / src_path.name
        project_target = project_refs_dir / src_path.name
        # Copy once to deploy target; copy again to project results for backup.
        shutil.copy2(src_path, deploy_target)
        shutil.copy2(src_path, project_target)
        post_sha = sha256_file(deploy_target)
        if post_sha != src_sha:
            raise RuntimeError(f"Reference copy hash mismatch for {role_id}: {src_sha} != {post_sha}")
        ref_map[role_id] = {
            "role_id": role_id,
            "source_path": str(src_path),
            "project_path": str(project_target),
            "deploy_path": str(deploy_target),
            "reference_text": ref_text,
            "size_bytes": src_size,
            "sha256": post_sha,
        }

    # Bind reference info into every clip and the T5 template.
    # T0 clips with role_id is None (basic_zh, speaker_tags_experimental) keep
    # reference_audio / reference_text / reference_hash = None — they were
    # no-reference generations in round 1 and must stay that way to keep
    # T0 strictly matched.
    for group in matrix["cases"].values():
        if group["kind"] in ("historical_matched_retest", "synthetic_chapter",
                             "edge_cases_repeat", "role_emotion",
                             "identical_role_anchors"):
            for clip in group.get("clips", []):
                role_id = clip["role_id"]
                if role_id is None or role_id not in ref_map:
                    clip["reference_audio"] = None
                    clip["reference_text"] = None
                    clip["reference_hash"] = None
                else:
                    clip["reference_audio"] = ref_map[role_id]["deploy_path"]
                    clip["reference_text"] = ref_map[role_id]["reference_text"]
                    clip["reference_hash"] = ref_map[role_id]["sha256"]
        if group["kind"] == "sustained_generation":
            tpl = group["padding_template"]
            tpl["reference_audio"] = ref_map[tpl["role_id"]]["deploy_path"]
            tpl["reference_text"] = ref_map[tpl["role_id"]]["reference_text"]
            tpl["reference_hash"] = ref_map[tpl["role_id"]]["sha256"]

    return ref_map


def build_execution_order(matrix: dict) -> list[dict]:
    """Compute the runtime queue. T4 anchors are pinned at start, middle and tail.
    T5 padding slots are computed by the runner; the manifest declares only the
    initial queue with placeholders for the runner to fill.

    The returned list contains dicts with `position` (0-based index) so the runner
    does not reorder. Each entry is a copy of the clip record.
    """
    queue: list[dict] = []
    # Front anchor = T4 start
    for clip in matrix["cases"]["T4"]["clips"]:
        if clip["position_in_run"] == "start":
            queue.append(dict(clip, position=len(queue)))
    # T0 retest
    for clip in matrix["cases"]["T0"]["clips"]:
        queue.append(dict(clip, position=len(queue)))
    # T2 edges (12 clips, two seeds each)
    for clip in matrix["cases"]["T2"]["clips"]:
        queue.append(dict(clip, position=len(queue)))
    # T1 chapter segments (≤40)
    for clip in matrix["cases"]["T1"]["clips"]:
        queue.append(dict(clip, position=len(queue)))
    # T3 emotion variations
    for clip in matrix["cases"]["T3"]["clips"]:
        queue.append(dict(clip, position=len(queue)))
    # Middle anchor = T4 middle
    for clip in matrix["cases"]["T4"]["clips"]:
        if clip["position_in_run"] == "middle":
            queue.append(dict(clip, position=len(queue)))
    return queue


def cmd_prepare(args: argparse.Namespace) -> int:
    run_id = args.run_id
    paths = get_run_paths(run_id)
    project_results = paths["project_results"]
    if project_results.exists():
        if not args.force:
            print(f"ERROR: {project_results} already exists. Use --force to overwrite.", file=sys.stderr)
            return 2
        shutil.rmtree(project_results)

    for p in paths.values():
        p.mkdir(parents=True, exist_ok=True)

    # Stage the test matrix.
    matrix = build_test_matrix()
    ref_map = snapshot_references(
        matrix, paths["deploy_refs_dir"], paths["project_results"] / "references_snapshot"
    )
    queue = build_execution_order(matrix)
    matrix["queue"] = queue

    # Manifest: serialisable summary, with hashes for binding.
    manifest = {
        "schema_version": 1,
        "run_id": run_id,
        "created_at": now_iso(),
        "benchmark": str(BENCHMARK.relative_to(ROOT)),
        "plan": str(PLAN.relative_to(ROOT)),
        "deployment": str(DEPLOY),
        "runner_python": str(DEPLOY_PYTHON),
        "runner_path": str(RUNNER),
        "monitor_path": str(MONITOR),
        "launcher_path": str(LAUNCHER),
        "host": host_fingerprint(),
        "git": git_state(),
        "acceptance": ACCEPTANCE,
        "limits": {
            "total_wall_minutes": TOTAL_WALL_MIN,
            "fish_wall_minutes": FISH_WALL_MIN,
            "generation_timeout_seconds": GENERATION_TIMEOUT_S,
            "asr_timeout_seconds": ASR_TIMEOUT_S,
            "heartbeat_timeout_seconds": HEARTBEAT_TIMEOUT_S,
            "resource_sample_seconds": SAMPLE_INTERVAL_S,
            "external_load_check_seconds": EXTERNAL_LOAD_INTERVAL_S,
            "thermal_sample_seconds": THERMAL_INTERVAL_S,
            "disk_free_min_gib": DISK_FREE_MIN_GIB,
            "stop_swap_delta_gib": STOP_SWAP_DELTA_GIB,
            "stop_swap_growth_gib_per_60_seconds": STOP_SWAP_PER_MIN_GIB,
            "stop_memory_free_percent_below": STOP_MEM_FREE_PCT,
            "stop_memory_low_consecutive_samples": STOP_MEM_LOW_CONSECUTIVE,
            "stop_required_resource_fields_missing_samples": STOP_MISSING_FIELD_CONSECUTIVE,
        },
        "reference_map": ref_map,
        "expected_case_counts": {g: len(matrix["cases"][g].get("clips", [])) for g in matrix["cases"]},
        "expected_total_initial_queue": len(queue),
        "repair_policy": {"max_distinct_failed_clips": 3, "max_attempts_each": 1, "keep_original_failures": True},
        "states": list(STATUS_VALUES),
    }
    write_json(paths["config_dir"] / "manifest.json", manifest)

    # Frozen matrix YAML for human review.
    import yaml
    matrix_yaml = paths["config_dir"] / "test-matrix.yaml"
    matrix_yaml.write_text(
        yaml.safe_dump(matrix, allow_unicode=True, sort_keys=False, width=120),
        encoding="utf-8",
    )

    # Texts as a separate JSONL with the same hashes for easy diff.
    texts_path = paths["config_dir"] / "texts.jsonl"
    with texts_path.open("w", encoding="utf-8") as f:
        for clip in queue:
            f.write(json.dumps({
                "case_id": clip["case_id"], "group": clip["group"],
                "role_id": clip["role_id"], "text": clip["text"],
                "seed": clip["seed"], "input_hash": clip["input_hash"],
                "reference_hash": clip["reference_hash"],
                "config_hash": clip["config_hash"],
            }, ensure_ascii=False) + "\n")
        # T5 placeholder so the file lists every variant the runner may emit.
        f.write(json.dumps({
            "case_id": "T5_padding_<index>", "group": "T5",
            "role_id": matrix["cases"]["T5"]["padding_role"],
            "text": matrix["cases"]["T5"]["padding_text"],
            "seed": matrix["cases"]["T5"]["padding_seed"],
            "input_hash": sha256_text(matrix["cases"]["T5"]["padding_text"]),
            "reference_hash": matrix["cases"]["T5"]["padding_template"]["reference_hash"],
            "config_hash": matrix["cases"]["T5"]["padding_template"]["config_hash"],
        }, ensure_ascii=False) + "\n")

    # Environment snapshot — record but do NOT yet probe heavy load.
    write_json(paths["config_dir"] / "environment.json", {
        "host": host_fingerprint(),
        "git": git_state(),
        "deploy_exists": DEPLOY.exists(),
        "deploy_python_exists": DEPLOY_PYTHON.exists(),
        "runner_exists": RUNNER.exists(),
        "monitor_exists": MONITOR.exists(),
        "launcher_exists": LAUNCHER.exists(),
        "legacy_results_exists": LEGACY_RESULTS.exists(),
        "captured_at": now_iso(),
    })

    # Initial status.
    initial_status = {
        "run_id": run_id,
        "state": "prepared",
        "verdict": "pending",
        "stop_reason": None,
        "started_wall_at": None,
        "ended_wall_at": None,
        "expected_total_initial_queue": len(queue),
        "expected_case_counts": manifest["expected_case_counts"],
        "completed_case_ids": [],
        "failed_case_ids": [],
        "skipped_case_ids": [],
        "process_ids": {},
        "last_heartbeat_at": None,
        "updated_at": now_iso(),
    }
    write_status(run_id, initial_status)

    print(f"Prepared run {run_id}")
    print(f"  Initial queue length (excl. T5 padding): {len(queue)}")
    print(f"  Expected case counts: {manifest['expected_case_counts']}")
    print(f"  Manifest: {paths['config_dir'] / 'manifest.json'}")
    print(f"  Frozen matrix: {paths['config_dir'] / 'test-matrix.yaml'}")
    print(f"  Texts: {texts_path}")
    print(f"  References snapshot: {paths['project_results'] / 'references_snapshot'}")
    print(f"  Status: {status_path(run_id)}")
    return 0


# --------------------------------------------------------------------------- #
# check: verify manifest without loading any models.
# --------------------------------------------------------------------------- #

def cmd_check(args: argparse.Namespace) -> int:
    run_id = args.run_id
    paths = get_run_paths(run_id)
    manifest_path = paths["config_dir"] / "manifest.json"
    if not manifest_path.exists():
        print(f"ERROR: manifest missing at {manifest_path}. Run prepare first.", file=sys.stderr)
        return 2

    errors: list[str] = []
    warnings: list[str] = []

    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    matrix_yaml = paths["config_dir"] / "test-matrix.yaml"
    if not matrix_yaml.exists():
        errors.append(f"missing {matrix_yaml}")
    if not (paths["config_dir"] / "texts.jsonl").exists():
        errors.append(f"missing {paths['config_dir'] / 'texts.jsonl'}")

    # Verify reference snapshot.
    for role_id, ref in manifest["reference_map"].items():
        target = Path(ref["deploy_path"])
        if not target.exists():
            errors.append(f"reference deploy copy missing for {role_id}: {target}")
            continue
        sha = sha256_file(target)
        if sha != ref["sha256"]:
            errors.append(f"reference hash mismatch for {role_id}: stored {ref['sha256']} != now {sha}")

    # Verify expected case counts vs matrix.
    matrix = load_yaml_simple(matrix_yaml)
    for group_name, expected in manifest["expected_case_counts"].items():
        actual = len(matrix["cases"][group_name].get("clips", []))
        if actual != expected:
            errors.append(f"{group_name} expected {expected} clips, found {actual}")

    # Verify every clip in the queue has required fields.
    queue = matrix.get("queue", [])
    required_clip_fields = {"case_id", "group", "role_id", "text", "seed",
                            "max_new_tokens", "config_hash", "input_hash",
                            "reference_hash", "reference_audio", "position"}
    seen_ids = set()
    for clip in queue:
        missing = required_clip_fields - set(clip.keys())
        if missing:
            errors.append(f"{clip.get('case_id')} missing fields {sorted(missing)}")
        if clip["case_id"] in seen_ids:
            errors.append(f"duplicate case_id in queue: {clip['case_id']}")
        seen_ids.add(clip["case_id"])

    # Verify hashes are non-empty 64-char hex.  input_hash and config_hash are
    # always required; reference_hash is allowed to be None for clips that
    # were no-reference generations in round 1 (T0_basic_zh,
    # T0_speaker_tags_experimental).
    for clip in queue:
        for field in ("input_hash", "config_hash"):
            value = clip.get(field, "")
            if not re.fullmatch(r"[0-9a-f]{64}", value or ""):
                errors.append(f"{clip['case_id']} {field} not 64-char hex: {value!r}")
        value = clip.get("reference_hash")
        if value is not None and not re.fullmatch(r"[0-9a-f]{64}", value):
            errors.append(f"{clip['case_id']} reference_hash not 64-char hex: {value!r}")
        # Cross-check: if reference_audio is None, reference_hash must be None.
        if clip.get("reference_audio") is None and clip.get("reference_hash") is not None:
            errors.append(f"{clip['case_id']} reference_audio=None but reference_hash set")
        if clip.get("reference_audio") is not None and clip.get("reference_hash") is None:
            errors.append(f"{clip['case_id']} reference_audio set but reference_hash missing")

    # Verify runner and monitor scripts exist and are importable / parseable.
    for script in (RUNNER, MONITOR, LAUNCHER):
        if not script.exists():
            errors.append(f"missing script: {script}")
    # Light parse: py_compile on the runner and monitor without importing mlx.
    import py_compile
    for script in (RUNNER, MONITOR):
        try:
            py_compile.compile(str(script), doraise=True)
        except py_compile.PyCompileError as exc:
            errors.append(f"{script} failed to compile: {exc}")

    # Verify deploy venv and DEPLOY python exist.
    if not DEPLOY_PYTHON.exists():
        errors.append(f"deploy python missing: {DEPLOY_PYTHON}")
    if not (DEPLOY / "scripts" / "tts.py").exists():
        errors.append(f"DEPLOY tts.py missing: {DEPLOY / 'scripts' / 'tts.py'}")

    # Light sanity: status file exists and is at 'prepared'.
    status = load_status(run_id)
    if status.get("state") not in ("prepared", "waiting_for_unload", "running"):
        # Allow check on completed runs too.
        if status.get("state") not in STATUS_VALUES:
            errors.append(f"unexpected status state: {status.get('state')}")

    report = {
        "run_id": run_id,
        "checked_at": now_iso(),
        "manifest_sha256": sha256_file(manifest_path),
        "matrix_sha256": sha256_file(matrix_yaml),
        "queue_length": len(queue),
        "expected_case_counts": manifest["expected_case_counts"],
        "errors": errors,
        "warnings": warnings,
        "verdict": "pass" if not errors else "fail",
    }
    out = paths["config_dir"] / "dry-run-check.json"
    write_json(out, report)
    print(f"check {run_id}: {report['verdict']}")
    if errors:
        for e in errors:
            print(f"  ERR  {e}")
    if warnings:
        for w in warnings:
            print(f"  warn {w}")
    print(f"  Report: {out}")
    return 0 if report["verdict"] == "pass" else 1


# --------------------------------------------------------------------------- #
# status: live inspection, no model load.
# --------------------------------------------------------------------------- #

def cmd_status(args: argparse.Namespace) -> int:
    run_id = args.run_id
    paths = get_run_paths(run_id)
    status = load_status(run_id)
    manifest_path = paths["config_dir"] / "manifest.json"
    manifest_exists = manifest_path.exists()
    expected_counts = status.get("expected_case_counts")
    if manifest_exists and not expected_counts:
        m = json.loads(manifest_path.read_text(encoding="utf-8"))
        expected_counts = m["expected_case_counts"]

    print(json.dumps({
        "run_id": run_id,
        "state": status.get("state"),
        "verdict": status.get("verdict"),
        "stop_reason": status.get("stop_reason"),
        "expected_case_counts": expected_counts,
        "completed_count": len(status.get("completed_case_ids", [])),
        "failed_count": len(status.get("failed_case_ids", [])),
        "skipped_count": len(status.get("skipped_case_ids", [])),
        "started_wall_at": status.get("started_wall_at"),
        "ended_wall_at": status.get("ended_wall_at"),
        "last_heartbeat_at": status.get("last_heartbeat_at"),
        "process_ids": status.get("process_ids", {}),
        "updated_at": status.get("updated_at"),
    }, ensure_ascii=False, indent=2))
    return 0


# --------------------------------------------------------------------------- #
# analyze: post-run summariser. Reads logs, computes metrics, emits summary.json.
# --------------------------------------------------------------------------- #

def cmd_analyze(args: argparse.Namespace) -> int:
    run_id = args.run_id
    paths = get_run_paths(run_id)
    logs_dir = paths["logs_dir"]
    summary: dict[str, Any] = {"run_id": run_id, "analyzed_at": now_iso()}

    fish_log = logs_dir / "fish-runner.jsonl"
    asr_log = logs_dir / "asr-runner.jsonl"
    resource_log = logs_dir / "resource-samples.jsonl"
    baseline_log = logs_dir / "baseline.jsonl"
    manifest_path = paths["config_dir"] / "manifest.json"

    if not manifest_path.exists():
        print(f"ERROR: {manifest_path} missing; prepare first.", file=sys.stderr)
        return 2
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))

    # -------------------------------------------------------------------------
    # Build the frozen expected-id set from the manifest. Every clip in the
    # prepared test matrix must show up in the run, either as a successful
    # generated row, a fish_clip_finished row, or an explicit failure row.
    # Without this cross-check, "100% pass" can be claimed on a partial run.
    # -------------------------------------------------------------------------
    expected_ids: set[str] = set()
    for group, count in manifest.get("expected_case_counts", {}).items():
        if isinstance(count, int):
            pass  # we only know the count; the actual IDs live in test-matrix.yaml
    matrix_yaml = paths["config_dir"] / "test-matrix.yaml"
    if matrix_yaml.exists():
        try:
            import yaml as _yaml
            m = _yaml.safe_load(matrix_yaml.read_text(encoding="utf-8"))
            for grp in m.get("cases", {}).values():
                for clip in grp.get("clips", []):
                    cid = clip.get("case_id")
                    if cid:
                        expected_ids.add(cid)
        except Exception:
            pass
    # T5 padding cases are generated at runtime; we don't know exact IDs in
    # advance. They are recorded under prefix T5_padding_*. Treat those as
    # optional and DON'T include them in the strict "missing" list.
    expected_ids = {cid for cid in expected_ids if not cid.startswith("T5_padding_")}

    clips: list[dict] = []
    clip_attempts: dict[str, list[dict]] = {}
    fish_aborted_records: list[dict] = []
    if fish_log.exists():
        for line in fish_log.read_text(encoding="utf-8").splitlines():
            try:
                rec = json.loads(line)
            except json.JSONDecodeError:
                continue
            ev = rec.get("event")
            if ev == "generated":
                clips.append(rec)
                cid = rec.get("case_id")
                if cid:
                    clip_attempts.setdefault(cid, []).append(rec)
            elif ev == "fish_clip_finished":
                cid = rec.get("case_id")
                if cid:
                    clip_attempts.setdefault(cid, []).append(rec)
            elif ev == "fish_aborted":
                fish_aborted_records.append(rec)
    summary["clip_count"] = len(clips)
    summary["fish_aborted_count"] = len(fish_aborted_records)
    summary["attempted_case_count"] = len(clip_attempts)
    summary["expected_case_count_excl_t5"] = len(expected_ids)

    # -------------------------------------------------------------------------
    # Completion: every expected case_id must appear with ok=true. first_attempt
    # is FAIL when any expected case is missing or has a failed fish_clip_finished.
    # -------------------------------------------------------------------------
    success_ids = {c.get("case_id") for c in clips if c.get("exit_status") in (None, "ok", "success")}
    successes = [c for c in clips if c.get("exit_status") in (None, "ok", "success")]
    audio_seconds = sum(c.get("audio_seconds", 0.0) for c in successes)
    generation_seconds = sum(c.get("generation_seconds", 0.0) for c in successes)
    missing_case_ids = sorted(cid for cid in expected_ids if cid not in success_ids)
    failed_ids = sorted(
        cid for cid, evs in clip_attempts.items()
        if any(e.get("ok") is False for e in evs if e.get("event") == "fish_clip_finished")
    )
    summary["failed_clip_count"] = len(failed_ids)
    summary["failed_case_ids"] = failed_ids
    summary["missing_case_ids"] = missing_case_ids
    summary["audio_seconds_total"] = round(audio_seconds, 3)
    summary["generation_seconds_total"] = round(generation_seconds, 3)
    summary["weighted_rtf"] = round(generation_seconds / audio_seconds, 4) if audio_seconds else None

    rtfs = [c.get("rtf") for c in successes if c.get("rtf")]
    if rtfs:
        summary["per_clip_rtf"] = {
            "p50": round(_percentile(rtfs, 0.5), 4),
            "p95": round(_percentile(rtfs, 0.95), 4),
            "max": round(max(rtfs), 4),
            "min": round(min(rtfs), 4),
            "samples": len(rtfs),
            "quantile_method": "linear interpolation, sorted ascending",
        }

    summary["hit_token_limit_count"] = sum(1 for c in clips if c.get("hit_token_limit"))

    # -------------------------------------------------------------------------
    # Anchor slowdown — original metric is RTF, per-role pairing so narrator's
    # slowdown is not hidden by pooled median.
    # -------------------------------------------------------------------------
    anchor_per_role: dict[str, dict] = {}
    roles_pos = ("narrator", "A", "B")
    for role in roles_pos:
        per: dict[str, float] = {}
        for c in clips:
            cid = c.get("case_id", "")
            if not cid.startswith("T4_"):
                continue
            parts = cid.split("_")
            if len(parts) != 3 or parts[1] != role:
                continue
            pos = parts[2]
            if c.get("rtf"):
                per[pos] = c["rtf"]
        s = per.get("start")
        m = per.get("middle")
        e = per.get("end")
        entry = {"start_rtf": s, "middle_rtf": m, "end_rtf": e}
        if s and m:
            entry["middle_slowdown_ratio"] = round((m - s) / s, 4)
        if s and e:
            entry["end_slowdown_ratio"] = round((e - s) / s, 4)
        anchor_per_role[role] = entry
    summary["anchor_per_role_rtf"] = anchor_per_role

    def median(values):
        if not values:
            return None
        s = sorted(values)
        n = len(s)
        if n % 2 == 1:
            return s[n // 2]
        return (s[n // 2 - 1] + s[n // 2]) / 2

    anchor_groups: dict[str, list[float]] = {"start": [], "middle": [], "end": []}
    for c in clips:
        if c.get("group") != "T4":
            continue
        for k in anchor_groups:
            if c["case_id"].endswith(f"_{k}"):
                anchor_groups[k].append(c.get("rtf") or 0.0)
    pooled = {}
    for k, vals in anchor_groups.items():
        pooled[k] = {"median_rtf": round(median(vals), 4) if vals else None, "samples": len(vals)}
    if pooled.get("start", {}).get("median_rtf") not in (None, 0):
        for k in ("middle", "end"):
            a = pooled[k]["median_rtf"]
            s = pooled["start"]["median_rtf"]
            if a is not None and s:
                pooled[k]["slowdown_ratio"] = round((a - s) / s, 4)
    pooled["_warn"] = (
        "Pooled median across 3 roles hides narrator's per-role slowdown. "
        "Use anchor_per_role_rtf for the verdict."
    )
    summary["anchor_rtf_pooled_median_legacy"] = pooled

    # -------------------------------------------------------------------------
    # ASR — recompute weighted CER from raw asr-verification.json using the
    # CORRECT cleaning (strip <|...|> and [...] instruction tags first, then
    # NFKC + lowercase + drop punctuation/whitespace). Don't trust any
    # pre-computed CER field in the existing logs.
    # -------------------------------------------------------------------------
    import re as _re
    import unicodedata as _ud

    def _clean(s):
        s = _re.sub(r"<\|[^>]+\|>", "", s or "")
        s = _re.sub(r"\[[^\]]*\]", "", s)
        s = _ud.normalize("NFKC", s)
        return "".join(c.lower() for c in s
                       if not c.isspace() and not _ud.category(c).startswith(("P", "S")))

    def _lev(a, b):
        if len(a) < len(b):
            a, b = b, a
        prev = list(range(len(b) + 1))
        for i, ca in enumerate(a, 1):
            cur = [i]
            for j, cb in enumerate(b, 1):
                cur.append(min(cur[-1] + 1, prev[j] + 1, prev[j - 1] + (ca != cb)))
            prev = cur
        return prev[-1]

    asr_json = paths["project_results"] / "logs" / "asr-verification.json"
    asr_records_raw: list[dict] = []
    if asr_json.exists():
        asr_records_raw = json.loads(asr_json.read_text(encoding="utf-8"))
    elif asr_log.exists():
        for line in asr_log.read_text(encoding="utf-8").splitlines():
            try:
                rec = json.loads(line)
            except json.JSONDecodeError:
                continue
            if rec.get("event") == "asr_transcribed":
                asr_records_raw.append(rec)

    cers = []
    edits_total = 0
    refs_total = 0
    asr_per_clip = []
    for r in asr_records_raw:
        e = _clean(r.get("expected", ""))
        a = _clean(r.get("transcript", ""))
        edits = _lev(e, a)
        refs = max(1, len(e))
        cer = edits / refs
        cers.append(cer)
        edits_total += edits
        refs_total += refs
        asr_per_clip.append({"name": r.get("name"), "ref_chars": refs, "edits": edits, "cer": round(cer, 4)})

    summary["asr_clip_count"] = len(asr_records_raw)
    summary["asr_weighted_cer_numerator"] = edits_total
    summary["asr_weighted_cer_denominator"] = refs_total
    summary["asr_weighted_cer"] = round(edits_total / refs_total, 6) if refs_total else None
    summary["asr_cleaning_method"] = (
        "strip <|...|> and [...] instruction tags, NFKC normalize, lowercase, drop punct/whitespace"
    )
    if cers:
        summary["asr_cer_distribution"] = {
            "p50": round(_percentile(cers, 0.5), 4),
            "p95": round(_percentile(cers, 0.95), 4),
            "max": round(max(cers), 4),
            "samples": len(cers),
        }
    summary["asr_per_clip"] = asr_per_clip

    # -------------------------------------------------------------------------
    # Resource summary.
    # -------------------------------------------------------------------------
    samples: list[dict] = []
    if resource_log.exists():
        for line in resource_log.read_text(encoding="utf-8").splitlines():
            try:
                samples.append(json.loads(line))
            except json.JSONDecodeError:
                continue
    summary["resource_sample_count"] = len(samples)

    def stat_for(field):
        vals = [s.get(field) for s in samples if isinstance(s.get(field), (int, float))]
        if not vals:
            return None
        return {"min": round(min(vals), 3), "max": round(max(vals), 3),
                "samples": len(vals)}

    summary["resource_summary"] = {
        "available_gib": stat_for("available_gib"),
        "swap_used_gib": stat_for("swap_used_gib"),
        "swap_delta_from_baseline_gib": stat_for("swap_delta_from_baseline_gib"),
        "memory_pressure_free_percent": stat_for("memory_pressure_free_percent"),
    }

    baseline_samples: list[dict] = []
    if baseline_log.exists():
        for line in baseline_log.read_text(encoding="utf-8").splitlines():
            try:
                baseline_samples.append(json.loads(line))
            except json.JSONDecodeError:
                continue
    if baseline_samples:
        sb = sorted(b["swap_used_gib"] for b in baseline_samples
                    if isinstance(b.get("swap_used_gib"), (int, float)))
        sa = sorted(b["available_gib"] for b in baseline_samples
                    if isinstance(b.get("available_gib"), (int, float)))
        summary["baseline"] = {
            "samples": len(baseline_samples),
            "swap_used_gib_psutil": {"min": min(sb), "max": max(sb)} if sb else None,
            "available_gib": {"min": min(sa), "max": max(sa)} if sa else None,
            "note": "baseline.jsonl sysctl output parsing failed; psutil used as substitute.",
        }

    # -------------------------------------------------------------------------
    # Per-clip audio existence + checksum verification. FAIL on hash mismatch,
    # do NOT increment verified_clip_count for bad hashes.
    # -------------------------------------------------------------------------
    audio_dir = paths["audio_dir"]
    verified_clips = 0
    missing_clips = []
    bad_hash_clips = []
    for c in clips:
        out = Path(c.get("output_path") or audio_dir / f"{c.get('case_id', 'unknown')}.wav")
        if not out.exists():
            missing_clips.append(str(out))
            continue
        if c.get("output_sha256"):
            sha = sha256_file(out)
            if sha != c["output_sha256"]:
                bad_hash_clips.append({"case_id": c.get("case_id"), "expected": c["output_sha256"], "actual": sha})
                continue  # do NOT count as verified
        verified_clips += 1
    summary["verified_clip_count"] = verified_clips
    summary["missing_clip_paths"] = missing_clips
    summary["checksum_mismatches"] = bad_hash_clips
    summary["checked_clip_count"] = len(clips)

    # -------------------------------------------------------------------------
    # Acceptance verdicts — must use the corrected fields.
    # first_attempt_completion: every expected case_id is present with ok=true.
    # -------------------------------------------------------------------------
    verdicts: dict[str, str] = {}
    expected_match = (not missing_case_ids) and not failed_ids
    verdicts["first_attempt_completion"] = _verdict(
        expected_match,
        f"all {len(expected_ids)} expected (excl. T5 padding) case_ids completed ok; no missing or failed",
        f"missing_case_ids={missing_case_ids}; failed_case_ids={failed_ids}",
    )
    if summary.get("weighted_rtf") is not None:
        verdicts["weighted_rtf"] = _verdict(
            summary["weighted_rtf"] <= ACCEPTANCE["weighted_rtf_max"],
            f"weighted_rtf={summary['weighted_rtf']} <= {ACCEPTANCE['weighted_rtf_max']}",
            f"weighted_rtf={summary['weighted_rtf']} > {ACCEPTANCE['weighted_rtf_max']}",
        )
    if summary.get("per_clip_rtf"):
        verdicts["per_clip_rtf_p95"] = _verdict(
            summary["per_clip_rtf"]["p95"] <= ACCEPTANCE["per_clip_rtf_p95_max"],
            f"p95={summary['per_clip_rtf']['p95']} <= {ACCEPTANCE['per_clip_rtf_p95_max']}",
            f"p95={summary['per_clip_rtf']['p95']} > {ACCEPTANCE['per_clip_rtf_p95_max']}",
        )
    # Per-role anchor slowdown (use the per-role field, not pooled median).
    anchor_threshold = ACCEPTANCE.get("anchor_rtf_slowdown_max", 0.30)
    for role, info in anchor_per_role.items():
        ratio = info.get("end_slowdown_ratio")
        if ratio is None:
            verdicts[f"anchor_end_{role}"] = "pending: missing start or end RTF"
            continue
        verdicts[f"anchor_end_{role}"] = _verdict(
            ratio <= anchor_threshold,
            f"{role} end_slowdown={ratio*100:.1f}% <= {anchor_threshold*100:.0f}%",
            f"{role} end_slowdown={ratio*100:.1f}% > {anchor_threshold*100:.0f}%",
        )
    if summary.get("asr_weighted_cer") is not None:
        verdicts["asr_weighted_cer"] = _verdict(
            summary["asr_weighted_cer"] <= ACCEPTANCE["weighted_cer_max"],
            f"weighted_cer={summary['asr_weighted_cer']*100:.4f}% <= {ACCEPTANCE['weighted_cer_max']*100:.0f}%",
            f"weighted_cer={summary['asr_weighted_cer']*100:.4f}% > {ACCEPTANCE['weighted_cer_max']*100:.0f}%",
        )
    summary["acceptance_verdicts"] = verdicts
    summary["acceptance_thresholds_proposed_not_measured"] = ACCEPTANCE

    # Fail closed on missing, duplicate, corrupt, or unproven attempts. The
    # historical display metrics above never substitute for this integrity gate.
    from fish_s2_evidence import audit
    strict_rows = []
    strict_errors = []
    for number, line in enumerate(fish_log.read_text().splitlines() if fish_log.exists() else [], 1):
        try:
            strict_rows.append(json.loads(line))
        except json.JSONDecodeError:
            strict_errors.append(f"malformed_log_line:{number}")
    endings = [x for x in strict_rows if x.get('event') == 'fish_finished']
    ending = endings[0] if len(endings) == 1 else None
    try:
        import yaml
        frozen = yaml.safe_load(matrix_yaml.read_text())
        strict_ids = [c['case_id'] for g in frozen['cases'].values() for c in g.get('clips', [])]
        padding_count = ending.get('t5_inserted', 0) if ending else 0
        if not isinstance(padding_count, int) or not 0 <= padding_count <= 120:
            raise ValueError('invalid padding count')
        strict_ids.extend(f'T5_padding_{i:03d}' for i in range(1, padding_count+1))
    except Exception as exc:
        strict_ids = []
        strict_errors.append('invalid_frozen_matrix:'+type(exc).__name__)
    integrity = audit(strict_ids,
                      [x for x in strict_rows if x.get('event') == 'fish_clip_finished'],
                      clips, ending, bool(fish_aborted_records), strict_errors)
    summary['integrity'] = integrity
    summary['verified_clip_count'] = integrity['verified_audio_count']
    verdicts['first_attempt_completion'] = _verdict(integrity['pass'],
        f"{integrity['expected_count']} unique scheduled jobs have one successful exit and valid bound WAV each",
        '; '.join(integrity['errors']))
    summary['fish_timing'] = {
        'pure_generation_seconds': generation_seconds,
        'worker_wall_seconds': ending.get('fish_wall_seconds') if ending else None,
        'subprocess_seconds': ending.get('active_seconds') if ending else None,
        'persistent_model_verified': False,
        'method': 'one model process per clip; duration does not prove persistent residency',
    }
    asr_names = [x.get('name') for x in asr_records_raw]
    asr_complete = len(asr_names) == len(set(asr_names)) and set(asr_names) == set(strict_ids)
    verdicts['asr_coverage'] = _verdict(asr_complete and bool(strict_ids),
        'one transcript per scheduled clip', 'missing, duplicate or unexpected ASR IDs')
    if not asr_complete:
        verdicts['asr_weighted_cer'] = 'pending: ASR coverage incomplete'
    summary['human_review'] = 'pending: qualitative feedback does not supply numeric or full-chapter acceptance'
    from fish_s2_evidence import asr_metrics
    detailed_asr = asr_metrics(asr_records_raw)
    summary['asr_per_clip'] = detailed_asr['per_clip']
    summary['asr_review_flag_count'] = sum(bool(x['review_flags']) for x in detailed_asr['per_clip'])
    summary['resource_summary']['mlx_peak_observed_gib'] = max((x.get('mlx_peak_gib',0) for x in clips), default=None)
    summary['resource_summary']['mlx_over_configured_12gib_count'] = sum(x.get('mlx_peak_gib',0)>12 for x in clips)
    summary['source_hashes'] = {str(p): sha256_file(p) for p in
        (fish_log, matrix_yaml, asr_json, Path(__file__), ROOT/'scripts/fish_s2_evidence.py') if p.exists()}
    summary_out = paths["project_results"] / "summary.json"
    write_json(summary_out, summary)
    print(f"Wrote {summary_out}")
    return 0 if integrity['pass'] else 2


def _percentile(values: Iterable[float], q: float) -> float:
    s = sorted(values)
    if not s:
        return 0.0
    if q <= 0:
        return s[0]
    if q >= 1:
        return s[-1]
    pos = q * (len(s) - 1)
    lo = int(pos)
    hi = min(lo + 1, len(s) - 1)
    frac = pos - lo
    return s[lo] + (s[hi] - s[lo]) * frac


def _verdict(condition: bool, ok_msg: str, fail_msg: str) -> str:
    return f"pass: {ok_msg}" if condition else f"FAIL: {fail_msg}"


# --------------------------------------------------------------------------- #
# main
# --------------------------------------------------------------------------- #

def main() -> int:
    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=textwrap.dedent("""\
            Workflow:
              1. python scripts/fish-s2-followup.py prepare --run-id <id>
              2. python scripts/fish-s2-followup.py check   --run-id <id>
              3. ./scripts/start-fish-s2-followup.sh <id>
              4. python scripts/fish-s2-followup.py status  --run-id <id>
              5. python scripts/fish-s2-followup.py analyze --run-id <id>
        """))
    sub = p.add_subparsers(dest="cmd", required=True)
    sp = sub.add_parser("prepare", help="freeze test matrix, allocate run dir")
    sp.add_argument("--run-id", required=True)
    sp.add_argument("--force", action="store_true",
                    help="delete existing results/<run-id> before preparing")
    sp.add_argument("--now", help="override timestamp (YYYYMMDD_HHMMSS) — for testing")

    sc = sub.add_parser("check", help="verify frozen manifest without loading models")
    sc.add_argument("--run-id", required=True)

    ss = sub.add_parser("status", help="print current status of a run")
    ss.add_argument("--run-id", required=True)

    sa = sub.add_parser("analyze", help="post-run summary")
    sa.add_argument("--run-id", required=True)

    args = p.parse_args()
    dispatch = {"prepare": cmd_prepare, "check": cmd_check,
                "status": cmd_status, "analyze": cmd_analyze}
    return dispatch[args.cmd](args)


if __name__ == "__main__":
    sys.exit(main())
