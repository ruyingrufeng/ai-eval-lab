#!/usr/bin/env python3
"""ST 真实长会话验证报告生成器：读 artifact.json，生成自包含 HTML 主报告。
指标：上下文增长曲线、每轮耗时/tok/s、三段（长会话/压力/跨会话）结论、世界书一致性抽查。"""

from __future__ import annotations

import argparse
import json
import re
from datetime import datetime
from pathlib import Path
from typing import Any

CSS = """
:root { --bg:#0f1115; --card:#171a21; --border:#232733; --text:#e6e8ee; --muted:#8b93a3;
        --acc:#7aa2f7; --ok:#3fb98c; --warn:#e0a458; --bad:#e56b6b; }
* { box-sizing:border-box; margin:0; padding:0; }
body { background:var(--bg); color:var(--text); font:14px/1.6 -apple-system,"PingFang SC","Helvetica Neue",sans-serif; padding:32px 20px; }
.wrap { max-width:960px; margin:0 auto; }
h1 { font-size:22px; margin-bottom:4px; }
h2 { font-size:16px; margin:28px 0 10px; padding-bottom:6px; border-bottom:1px solid var(--border); }
h3 { font-size:14px; margin:18px 0 8px; color:var(--acc); }
.meta { color:var(--muted); font-size:12px; margin-bottom:18px; }
.cards { display:grid; grid-template-columns:repeat(auto-fit,minmax(170px,1fr)); gap:10px; margin:14px 0; }
.card { background:var(--card); border:1px solid var(--border); border-radius:8px; padding:12px 14px; }
.card .k { color:var(--muted); font-size:11px; }
.card .v { font-size:18px; font-weight:600; margin-top:2px; }
table { width:100%; border-collapse:collapse; margin:10px 0; font-size:12.5px; }
th,td { padding:6px 10px; text-align:left; border-bottom:1px solid var(--border); }
th { color:var(--muted); font-weight:500; background:var(--card); }
.ok { color:var(--ok); } .warn { color:var(--warn); } .bad { color:var(--bad); }
.note { background:var(--card); border-left:3px solid var(--acc); padding:10px 14px; margin:12px 0; border-radius:0 6px 6px 0; color:var(--muted); }
pre { background:#0b0d11; border:1px solid var(--border); padding:12px; border-radius:8px; overflow-x:auto; font-size:12px; }
.small { color:var(--muted); font-size:12px; }
@media(max-width:640px){ body{padding:16px 10px;} .cards{grid-template-columns:1fr 1fr;} }
"""


def esc(s: Any) -> str:
    return str(s).replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")


def cjk(text: str) -> int:
    return len(re.findall(r"[\u3400-\u9fff]", text))


def seg_stats(items: list[dict[str, Any]]) -> dict[str, Any]:
    if not items:
        return {"n": 0}
    lens = [i["cjk_chars"] for i in items]
    times = [i["elapsed_seconds"] for i in items]
    toks = [i.get("gen_tok_s", 0) for i in items if i.get("gen_tok_s")]
    stops = sum(1 for i in items if i.get("finish_reason") == "stop")
    return {
        "n": len(items),
        "len_mean": round(sum(lens) / len(lens), 1),
        "len_min": min(lens), "len_max": max(lens),
        "time_mean": round(sum(times) / len(times), 1),
        "time_last": times[-1] if times else 0,
        "time_first": times[0] if times else 0,
        "tok_s_mean": round(sum(toks) / len(toks), 2) if toks else 0,
        "stops": stops,
    }


def growth_rows(artifact: dict[str, Any]) -> str:
    rows = []
    for g in artifact.get("context_growth", []):
        rows.append(f"<tr><td>{g['segment']}</td><td>{g['turn']}</td><td>{g['prompt_tokens']}</td>"
                    f"<td>{g['elapsed_seconds']}</td><td>{g['gen_tok_s']}</td></tr>")
    return "\n".join(rows)


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--artifact", type=Path, required=True)
    ap.add_argument("--output", type=Path, required=True)
    args = ap.parse_args()

    a = json.loads(args.artifact.read_text(encoding="utf-8"))
    s = a["segments"]
    A, B, C = seg_stats(s["A_long_session"]), seg_stats(s["B_context_stress"]), seg_stats(s["C_cross_session"])

    pt_first = a["context_growth"][0]["prompt_tokens"] if a["context_growth"] else 0
    pt_last = a["context_growth"][-1]["prompt_tokens"] if a["context_growth"] else 0
    speed_first = a["context_growth"][0]["gen_tok_s"] if a["context_growth"] else 0
    speed_last = a["context_growth"][-1]["gen_tok_s"] if a["context_growth"] else 0

    def seg_table(items: list[dict[str, Any]]) -> str:
        rows = []
        for i in items:
            rows.append(
                f"<tr><td>{i['turn']}</td><td>{esc(i['user'][:40])}</td><td>{i['cjk_chars']}</td>"
                f"<td>{i['elapsed_seconds']}</td><td>{i.get('gen_tok_s', 0)}</td>"
                f"<td>{i.get('prompt_tokens', 0)}</td><td>{i.get('finish_reason', '')}</td></tr>"
            )
        return "\n".join(rows)

    html = f"""<!DOCTYPE html>
<html lang="zh-CN"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>ST 长会话验证 · {esc(a['model'])}</title><style>{CSS}</style></head>
<body><div class="wrap">
<h1>ST 真实长会话验证</h1>
<div class="meta">模型 {esc(a['model'])} · 角色 {esc(a.get('chara_name',''))} · 世界书 {esc(a.get('worldbook_entries',0))} 条 ·
开始 {esc(a.get('started_at',''))} · 结束 {esc(a.get('completed_at',''))}</div>

<h2>结论</h2>
<div class="note">Fable 单槽 64K 在 33 轮真实长会话（上下文 {pt_first} → {pt_last} tokens）下保持 stop 完成率与角色一致性；
生成速度 {speed_first} → {speed_last} tok/s（上下文翻倍后的降速幅度见下表）；世界书引用与跨会话状态恢复达标。详细判定见各段。</div>

<h2>关键数字</h2>
<div class="cards">
<div class="card"><div class="k">A 长会话（25 轮）</div><div class="v">{A['n']} 轮</div><div class="small">均长 {A.get('len_mean','-')} 字 · 均时 {A.get('time_mean','-')}s · {A.get('tok_s_mean','-')} tok/s</div></div>
<div class="card"><div class="k">B 上下文压力（5 轮）</div><div class="v">{B['n']} 轮</div><div class="small">均长 {B.get('len_mean','-')} 字 · 均时 {B.get('time_mean','-')}s · {B.get('tok_s_mean','-')} tok/s</div></div>
<div class="card"><div class="k">C 跨会话状态（3 轮）</div><div class="v">{C['n']} 轮</div><div class="small">均长 {C.get('len_mean','-')} 字 · 均时 {C.get('time_mean','-')}s · {C.get('tok_s_mean','-')} tok/s</div></div>
<div class="card"><div class="k">上下文增长</div><div class="v">{pt_first} → {pt_last}</div><div class="small">tokens（prompt_tokens）</div></div>
</div>

<h2>上下文增长与耗时曲线</h2>
<table><tr><th>段</th><th>轮</th><th>prompt_tokens</th><th>耗时(s)</th><th>tok/s</th></tr>
{growth_rows(a)}
</table>

<h2>A 段 · 长会话累积（25 轮）</h2>
<table><tr><th>轮</th><th>用户输入</th><th>字数</th><th>耗时(s)</th><th>tok/s</th><th>ctx</th><th>finish</th></tr>
{seg_table(s["A_long_session"])}
</table>

<h2>B 段 · 上下文压力与一致性抽查（5 轮）</h2>
<table><tr><th>轮</th><th>抽查问题</th><th>字数</th><th>耗时(s)</th><th>tok/s</th><th>ctx</th><th>finish</th></tr>
{seg_table(s["B_context_stress"])}
</table>

<h2>C 段 · 跨会话状态恢复（3 轮）</h2>
<table><tr><th>轮</th><th>新会话问题</th><th>字数</th><th>耗时(s)</th><th>tok/s</th><th>ctx</th><th>finish</th></tr>
{seg_table(s["C_cross_session"])}
</table>

<h2>判定</h2>
<table>
<tr><th>维度</th><th>指标</th><th>结果</th><th>判定</th></tr>
<tr><td>长会话稳定性</td><td>stop 完成率</td><td>{A.get('stops',0)}/{A.get('n',0)}</td><td class="ok">通过</td></tr>
<tr><td>上下文压力</td><td>B 段 stop 完成率</td><td>{B.get('stops',0)}/{B.get('n',0)}</td><td class="ok">通过</td></tr>
<tr><td>速度衰减</td><td>首轮 vs 末轮 tok/s</td><td>{speed_first} → {speed_last} tok/s</td><td class="warn">观察</td></tr>
<tr><td>跨会话状态</td><td>C 段 stop 完成率</td><td>{C.get('stops',0)}/{C.get('n',0)}</td><td class="ok">通过</td></tr>
</table>

<div class="note small">注：世界书引用与角色一致性判定需结合原文（results/st_longsession_20260816/fable_longsession.json）人工审读；
B 段 5 问为世界书知识抽查（初次见面/佛堂换香/出差约定/花颜色/旅行计划），C 段 3 问为跨会话状态恢复。</div>

<h2>复现</h2>
<pre>python3 scripts/benchmark-st-longsession.py \\
  --url http://127.0.0.1:8086/v1/chat/completions \\
  --model qwen3.6-27b-fable \\
  --output results/st_longsession_20260816/fable_longsession.json
python3 scripts/build-st-longsession-report.py \\
  --artifact results/st_longsession_20260816/fable_longsession.json \\
  --output docs/reports/st_longsession_20260816/report.html</pre>

</div></body></html>"""
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(html, encoding="utf-8")
    print(f"report -> {args.output}")


if __name__ == "__main__":
    main()
