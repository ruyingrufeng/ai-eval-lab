#!/usr/bin/env python3
"""真实角色卡 A/B 盲选报告生成器。输入两个模型 JSON，输出隐藏模型名的 HTML。
敏感原文（成年分支逐轮）不嵌入 HTML，只显示长度/一致性指标。"""

from __future__ import annotations

import argparse
import json
import re
from pathlib import Path
from datetime import datetime

def cjk(text: str) -> int:
    return len(re.findall(r"[\u3400-\u9fff]", text))

def esc(s: str) -> str:
    return s.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")

def load(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))

def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--a", type=Path, required=True, help="模型 A JSON")
    ap.add_argument("--b", type=Path, required=True, help="模型 B JSON")
    ap.add_argument("--out", type=Path, required=True, help="输出 HTML 路径")
    ap.add_argument("--a-name", default="模型 A")
    ap.add_argument("--b-name", default="模型 B")
    args = ap.parse_args()

    a, b = load(args.a), load(args.b)

    def stats(data: dict) -> dict:
        normal = data.get("normal", [])
        adult = data.get("adult", [])
        return {
            "normal_len": [r["cjk_chars"] for r in normal],
            "normal_time": [r["elapsed_seconds"] for r in normal],
            "normal_finish": [r.get("finish_reason") for r in normal],
            "adult_len": [r["cjk_chars"] for r in adult],
            "adult_time": [r["elapsed_seconds"] for r in adult],
            "adult_finish": [r.get("finish_reason") for r in adult],
        }

    sa, sb = stats(a), stats(b)

    def mean(xs: list[float]) -> float:
        return round(sum(xs) / len(xs), 1) if xs else 0.0

    # 普通轮指标
    na, nb = sa["normal_len"], sb["normal_len"]
    rows_n = ""
    for i in range(max(len(na), len(nb))):
        la = na[i] if i < len(na) else None
        lb = nb[i] if i < len(nb) else None
        ta = round(sa["normal_time"][i], 1) if i < len(sa["normal_time"]) else None
        tb = round(sb["normal_time"][i], 1) if i < len(sb["normal_time"]) else None
        fa = sa["normal_finish"][i] if i < len(sa["normal_finish"]) else None
        fb = sb["normal_finish"][i] if i < len(sb["normal_finish"]) else None
        rows_n += f"<tr><td>{i+1}</td><td>{la or '-'}</td><td>{ta or '-'}s</td><td>{fa or '-'}</td><td>{lb or '-'}</td><td>{tb or '-'}s</td><td>{fb or '-'}</td></tr>"

    # 成年轮指标（只放长度/耗时，不放原文）
    aa, ab = sa["adult_len"], sb["adult_len"]
    rows_a = ""
    for i in range(max(len(aa), len(ab))):
        la = aa[i] if i < len(aa) else None
        lb = ab[i] if i < len(ab) else None
        ta = round(sa["adult_time"][i], 1) if i < len(sa["adult_time"]) else None
        tb = round(sb["adult_time"][i], 1) if i < len(sb["adult_time"]) else None
        fa = sa["adult_finish"][i] if i < len(sa["adult_finish"]) else None
        fb = sb["adult_finish"][i] if i < len(sb["adult_finish"]) else None
        rows_a += f"<tr><td>{i+1}</td><td>{la or '-'}</td><td>{ta or '-'}s</td><td>{fa or '-'}</td><td>{lb or '-'}</td><td>{tb or '-'}s</td><td>{fb or '-'}</td></tr>"

    html = f"""<!DOCTYPE html>
<html lang="zh-CN">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>真实角色卡 A/B 盲选报告 · 媚雪 20 轮配对</title>
<style>
body {{ font-family: -apple-system, "PingFang SC", sans-serif; margin: 0; background: #f6f7f9; color: #1c1e21; }}
.container {{ max-width: 960px; margin: 0 auto; padding: 32px 20px 64px; }}
h1 {{ font-size: 22px; margin: 0 0 6px; }}
.meta {{ color: #6b7280; font-size: 13px; margin-bottom: 24px; }}
h3 {{ font-size: 16px; margin: 28px 0 10px; border-left: 3px solid #7c3aed; padding-left: 10px; }}
table {{ border-collapse: collapse; width: 100%; font-size: 13px; background: #fff; border-radius: 8px; overflow: hidden; }}
th, td {{ border: 1px solid #e5e7eb; padding: 6px 8px; text-align: center; }}
th {{ background: #f3f0ff; }}
.cards {{ display: grid; grid-template-columns: 1fr 1fr; gap: 16px; }}
.card {{ background: #fff; border-radius: 10px; padding: 16px; box-shadow: 0 1px 3px rgba(0,0,0,.08); }}
.card h4 {{ margin: 0 0 10px; font-size: 15px; }}
.kpi {{ font-size: 12px; color: #4b5563; line-height: 1.7; }}
.kpi b {{ color: #111827; }}
.verdict {{ background: #fff; border: 1px solid #e5e7eb; border-radius: 10px; padding: 16px 20px; margin-top: 20px; }}
code {{ background: #f1f2f4; padding: 1px 5px; border-radius: 4px; font-size: 12px; }}
@media (max-width: 640px) {{ .cards {{ grid-template-columns: 1fr; }} }}
</style>
</head>
<body>
<div class="container">
<h1>真实角色卡 A/B 盲选报告</h1>
<div class="meta">角色卡：媚雪（数字伴侣）· 世界书 15 条 · 普通 15 轮 + 成年自愿连续性 5 轮<br>
生成时间：{datetime.now().astimezone().strftime('%Y-%m-%d %H:%M %Z')} · 模型名已隐藏，由用户盲选文风</div>

<h3>总览</h3>
<div class="cards">
<div class="card"><h4>{esc(args.a_name)}</h4>
<div class="kpi">普通轮均长：<b>{mean(na)} 字</b>（目标 90–260）<br>
普通轮均耗时：<b>{mean(sa['normal_time'])} s</b><br>
普通轮 finish=stop：<b>{sa['normal_finish'].count('stop')}/{len(sa['normal_finish'])}</b><br>
成年轮均长：<b>{mean(aa)} 字</b> · 均耗时 <b>{mean(sa['adult_time'])} s</b><br>
成年轮 finish=stop：<b>{sa['adult_finish'].count('stop')}/{len(sa['adult_finish'])}</b></div>
</div>
<div class="card"><h4>{esc(args.b_name)}</h4>
<div class="kpi">普通轮均长：<b>{mean(nb)} 字</b>（目标 90–260）<br>
普通轮均耗时：<b>{mean(sb['normal_time'])} s</b><br>
普通轮 finish=stop：<b>{sb['normal_finish'].count('stop')}/{len(sb['normal_finish'])}</b><br>
成年轮均长：<b>{mean(ab)} 字</b> · 均耗时 <b>{mean(sb['adult_time'])} s</b><br>
成年轮 finish=stop：<b>{sb['adult_finish'].count('stop')}/{len(sb['adult_finish'])}</b></div>
</div>
</div>

<h3>普通轮逐轮长度与耗时（字数 / 秒 / finish）</h3>
<table>
<tr><th>轮</th><th colspan="3">{esc(args.a_name)}</th><th colspan="3">{esc(args.b_name)}</th></tr>
<tr><th></th><th>字数</th><th>耗时</th><th>finish</th><th>字数</th><th>耗时</th><th>finish</th></tr>
{rows_n}
</table>

<h3>成年自愿连续性轮（仅指标，原文保留在本地 JSON）</h3>
<table>
<tr><th>轮</th><th colspan="3">{esc(args.a_name)}</th><th colspan="3">{esc(args.b_name)}</th></tr>
<tr><th></th><th>字数</th><th>耗时</th><th>finish</th><th>字数</th><th>耗时</th><th>finish</th></tr>
{rows_a}
</table>

<div class="verdict">
<h3 style="margin-top:0">盲选说明</h3>
<p style="font-size:14px;line-height:1.8">字数与耗时只提供参考，不构成结论。请打开两侧本地 JSON（<code>{args.a}</code> / <code>{args.b}</code>）逐轮阅读原文后，从<b>文风、角色声音、设定保持、长度纪律</b>四个维度投票。投票结果决定是否进入生产切换/双预设路由讨论。</p>
</div>
</div>
</body>
</html>"""

    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(html, encoding="utf-8")
    print(f"OK: {args.out}")

if __name__ == "__main__":
    main()
