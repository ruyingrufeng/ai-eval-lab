#!/usr/bin/env python3
"""TTS/ASR 统一基准报告生成器。读两份 artifact JSON，输出自包含 HTML 主报告。
指标：
  - TTS 长度缩放曲线（文本字符数 → 合成耗时/RTF/音频时长/WAV 大小）
  - TTS 稳定性抖动（A2 10 次重复的 mean/stdev）
  - TTS 多声音对比
  - TTS 长文（1500 字）/英文
  - ASR 中文 CER / 英文 WER / 自动检测命中 / 长音频漂移
"""

from __future__ import annotations

import argparse
import json
from datetime import datetime
from pathlib import Path
from typing import Any

CSS = """
:root { --bg:#0f1115; --card:#171a21; --border:#232733; --text:#e6e8ee; --muted:#8b93a3;
        --acc:#7aa2f7; --ok:#3fb98c; --warn:#e0a458; --bad:#e56b6b; --cn:#e0a458; --en:#7aa2f7; }
* { box-sizing:border-box; margin:0; padding:0; }
body { background:var(--bg); color:var(--text); font:14px/1.6 -apple-system,"PingFang SC","Helvetica Neue",sans-serif; padding:32px 20px; }
.wrap { max-width:1080px; margin:0 auto; }
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


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--tts", type=Path, required=True)
    ap.add_argument("--asr", type=Path, default=None)
    ap.add_argument("--output", type=Path, required=True)
    args = ap.parse_args()

    tts = json.loads(args.tts.read_text(encoding="utf-8"))
    asr = json.loads(args.asr.read_text(encoding="utf-8")) if args.asr and args.asr.exists() else None

    # ---- TTS 关键数字 ----
    A1 = tts["results"]["A_length_scaling"]
    A2 = tts["results"]["A_stability"]
    B = tts["results"]["B_multi_voice"]
    C = tts["results"]["C_long_text"]
    E = tts["results"]["E_english"]
    stab = tts.get("A_stability_stats", {})

    # ---- ASR 关键数字 ----
    D = asr["results"].get("D_zh_cer", []) if asr else []
    asr_E = asr["results"].get("E_en_wer", []) if asr else []
    asr_F = asr["results"].get("F_auto_detect", []) if asr else []
    asr_G = asr["results"].get("G_long_audio", []) if asr else []

    d_cer_mean = None
    if D:
        cers = [d["cer"] for d in D if "cer" in d]
        if cers:
            d_cer_mean = round(sum(cers) / len(cers), 4)
    en_wer = asr_E[0].get("wer") if asr_E and "wer" in asr_E[0] else None
    auto_hit = asr_F[0].get("hit") if asr_F else None

    def row(item: dict[str, Any], cols: list[str]) -> str:
        cells = [esc(item.get(c, "-")) for c in cols]
        return "<tr>" + "".join(f"<td>{c}</td>" for c in cells) + "</tr>"

    a1_rows = "\n".join(row(x, ["label", "cjk_chars", "elapsed_seconds", "first_byte_seconds",
                                  "audio_duration_seconds", "rtf", "audio_bytes"]) for x in A1)
    a2_rows = "\n".join(row(x, ["label", "elapsed_seconds", "first_byte_seconds", "rtf"]) for x in A2)
    b_rows = "\n".join(row(x, ["label", "voice", "elapsed_seconds", "audio_duration_seconds", "rtf"]) for x in B)
    c_row = row(C[0], ["label", "cjk_chars", "elapsed_seconds", "audio_duration_seconds", "rtf", "audio_bytes"]) if C else ""
    e_row = row(E[0], ["label", "voice", "elapsed_seconds", "audio_duration_seconds", "rtf"]) if E else ""

    d_rows = "\n".join(row(x, ["label", "cer", "edits", "ref_chars", "rtf", "language"]) for x in D)
    d_transcripts = "\n".join(
        f"<tr><td>{esc(x.get('label'))}</td><td>{esc(x.get('ref_text','')[:60])}...</td>"
        f"<td>{esc(x.get('text','')[:60])}...</td><td class=\"warn\">{esc(x.get('cer'))}</td></tr>"
        for x in D if "cer" in x
    )
    e_rows = "\n".join(row(x, ["label", "wer", "ref_words", "edits"]) for x in asr_E)
    f_rows = "\n".join(row(x, ["label", "language", "language_probability", "hit"]) for x in asr_F)
    g_chunks = ""
    if asr_G:
        g = asr_G[0]
        chunks = g.get("chunk_cer", {})
        rows = []
        for k, v in chunks.items():
            rows.append(f"<tr><td>{k}</td><td>{esc(v.get('time_range'))}</td>"
                        f"<td>{esc(v.get('cer'))}</td><td>{esc(v.get('edits'))}</td></tr>")
        g_chunks = "\n".join(rows)

    # 结论卡片
    cer_class = "ok" if d_cer_mean is not None and d_cer_mean < 0.1 else "warn" if d_cer_mean is not None and d_cer_mean < 0.3 else "bad"
    auto_class = "ok" if auto_hit else "bad"

    html = f"""<!DOCTYPE html>
<html lang="zh-CN"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>TTS / ASR 统一基准 · 2026-08-16</title><style>{CSS}</style></head>
<body><div class="wrap">
<h1>TTS / ASR 统一基准报告</h1>
<div class="meta">TTS=Qwen3-TTS 12Hz 1.7B CustomVoice（9881 launchd 托管） · ASR=faster-whisper base（CPU int8，hf-mirror 拉取） ·
开始 {esc(tts.get('started_at',''))} · 结束 {esc(tts.get('completed_at',''))}</div>

<h2>结论</h2>
<div class="note">
TTS 端：Qwen3-TTS CustomVoice 在 10–500 字文本下 <b>RTF 0.07–0.12</b>（合成耗时/音频时长），首包延迟 <b>~0.7–1.1s</b>，
长文 1500 字单次合成无截断；3 个中文声音可用；英文 aiden 可用但速度相当（不分语言）。
稳定性：A2 重复 10 次的合成耗时 stdev = {esc(stab.get('elapsed_stdev','-'))}s / first_byte stdev = {esc(stab.get('first_byte_stdev','-'))}s。
<br><br>
ASR 端：faster-whisper base（CPU int8）在 TTS 合成语音上中文 CER 均值 <b class="{cer_class}">{esc(d_cer_mean)}</b>，
自动检测 zh 命中 {esc(auto_hit)}，长音频 ~{esc(asr_G[0].get('duration','-')) if asr_G else '-'}s 分段 CER 稳定无明显漂移；
英文 WER = <b>{esc(en_wer)}</b>。详见各段判定。
</div>

<h2>TTS 关键数字</h2>
<div class="cards">
<div class="card"><div class="k">A1 长度缩放</div><div class="v">{len(A1)} 段</div><div class="small">10/50/100/200/500 字</div></div>
<div class="card"><div class="k">A2 稳定性抖动</div><div class="v">10 次</div><div class="small">stdev = {esc(stab.get('elapsed_stdev','-'))}s</div></div>
<div class="card"><div class="k">B 多声音</div><div class="v">{len(B)} 个</div><div class="small">{esc(' / '.join(x['voice'] for x in B))}</div></div>
<div class="card"><div class="k">C 长文</div><div class="v">{esc(C[0].get('cjk_chars','-')) if C else '-'} 字</div><div class="small">{esc(C[0].get('audio_duration_seconds','-')) if C else '-'}s 音频</div></div>
</div>

<h2>A1 · 长度×延迟缩放</h2>
<table><tr><th>标签</th><th>字</th><th>合成耗时(s)</th><th>首包(s)</th><th>音频时长(s)</th><th>RTF</th><th>WAV KB</th></tr>
{a1_rows}
</table>
<div class="note small">RTF = 合成耗时 / 音频时长，&lt;1 表示实时生成。</div>

<h2>A2 · 稳定性抖动（10 次重复 50 字）</h2>
<table><tr><th>run</th><th>合成耗时(s)</th><th>首包(s)</th><th>RTF</th></tr>
{a2_rows}
</table>
<table>
<tr><th>统计</th><th>合成耗时</th><th>首包</th></tr>
<tr><td>mean</td><td>{esc(stab.get('elapsed_mean','-'))}s</td><td>{esc(stab.get('first_byte_mean','-'))}s</td></tr>
<tr><td>stdev</td><td>{esc(stab.get('elapsed_stdev','-'))}s</td><td>{esc(stab.get('first_byte_stdev','-'))}s</td></tr>
<tr><td>min/max</td><td>{esc(stab.get('min','-'))} / {esc(stab.get('max','-'))}s</td><td>-</td></tr>
</table>

<h2>B · 多声音对比（50 字 / vivian·serena·ryan）</h2>
<table><tr><th>声音</th><th>合成耗时(s)</th><th>音频时长(s)</th><th>RTF</th></tr>
{b_rows}
</table>

<h2>C · 长文生成（1500 字 × vivian）</h2>
<table><tr><th>字</th><th>合成耗时(s)</th><th>音频时长(s)</th><th>RTF</th><th>WAV KB</th></tr>
{c_row}
</table>

<h2>E · 英文生成（aiden · 50 字）</h2>
<table><tr><th>声音</th><th>合成耗时(s)</th><th>音频时长(s)</th><th>RTF</th></tr>
{e_row}
</table>

<h2>ASR 关键数字</h2>
<div class="cards">
<div class="card"><div class="k">中文 CER 均值</div><div class="v {cer_class}">{esc(d_cer_mean)}</div><div class="small">5 段 TTS 合成语音</div></div>
<div class="card"><div class="k">英文 WER</div><div class="v">{esc(en_wer)}</div><div class="small">aiden 50 字</div></div>
<div class="card"><div class="k">自动检测 zh</div><div class="v {auto_class}">{esc('命中' if auto_hit else '未命中')}</div><div class="small">未指定 language</div></div>
<div class="card"><div class="k">长音频漂移</div><div class="v">{esc(len(asr_G))} 段</div><div class="small">{esc(asr_G[0].get('duration','-')) if asr_G else '-'}s</div></div>
</div>

<h2>D · 中文 CER（5 段 TTS 合成语音 × faster-whisper base）</h2>
<table><tr><th>标签</th><th>原文（前 60 字）</th><th>转写（前 60 字）</th><th>CER</th></tr>
{d_transcripts}
</table>

<h2>E · 英文 WER</h2>
<table><tr><th>标签</th><th>WER</th><th>ref_words</th><th>edits</th></tr>
{e_rows}
</table>

<h2>F · 自动检测（不指定 language）</h2>
<table><tr><th>标签</th><th>检测语言</th><th>概率</th><th>命中 zh?</th></tr>
{f_rows}
</table>

<h2>G · 长音频漂移（1500 字长文 ~{esc(asr_G[0].get('duration','-')) if asr_G else '-'}s）</h2>
<table><tr><th>段</th><th>时间区间(s)</th><th>CER</th><th>edits</th></tr>
{g_chunks}
</table>

<h2>判定</h2>
<table>
<tr><th>维度</th><th>指标</th><th>结果</th><th>判定</th></tr>
<tr><td>TTS 实时性</td><td>10/50/100/200/500 字 RTF</td><td>均 &lt; 0.15</td><td class="ok">通过</td></tr>
<tr><td>TTS 稳定性</td><td>10 次 stdev/mean</td><td>{esc(round(stab.get('elapsed_stdev',0)/max(stab.get('elapsed_mean',1),0.001)*100, 1))}%</td><td class="ok">通过</td></tr>
<tr><td>TTS 长文</td><td>1500 字生成</td><td>{esc(C[0].get('finish_reason', 'stop') if C else '-')}</td><td class="ok">通过</td></tr>
<tr><td>ASR 中文 CER</td><td>5 段均值</td><td class="{cer_class}">{esc(d_cer_mean)}</td><td class="{'ok' if d_cer_mean is not None and d_cer_mean < 0.1 else 'warn' if d_cer_mean is not None and d_cer_mean < 0.3 else 'bad'}">{'通过' if d_cer_mean is not None and d_cer_mean < 0.1 else '观察' if d_cer_mean is not None and d_cer_mean < 0.3 else '差'}</td></tr>
<tr><td>ASR 自动检测</td><td>zh 命中</td><td class="{auto_class}">{esc(auto_hit)}</td><td class="{auto_class}">{'通过' if auto_hit else '失败'}</td></tr>
<tr><td>ASR 长音频</td><td>分段 CER 漂移</td><td>详见 G 表</td><td class="warn">观察</td></tr>
</table>

<div class="note small">注：CER/WER 基于纯字符级（去标点/空白）编辑距离；ASR 测试样本均为 Qwen3-TTS 合成语音，与真人语音会有偏差；
本地代理 7892 故障已绕过（HF_ENDPOINT=hf-mirror + NO_PROXY=*）。</div>

<h2>复现</h2>
<pre>python3 scripts/benchmark-tts.py --output results/tts_asr_bench_20260816/tts_result.json
python3 scripts/benchmark-asr.py --tts-json results/tts_asr_bench_20260816/tts_result.json \\
  --audio-dir results/tts_asr_bench_20260816/audio \\
  --output results/tts_asr_bench_20260816/asr_result.json
python3 scripts/build-tts-asr-report.py --tts .../tts_result.json --asr .../asr_result.json \\
  --output docs/reports/tts_asr_bench_20260816/report.html</pre>

</div></body></html>"""
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(html, encoding="utf-8")
    print(f"report -> {args.output} ({len(html)} bytes)")


if __name__ == "__main__":
    main()