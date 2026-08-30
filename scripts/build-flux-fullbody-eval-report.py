#!/usr/bin/env python3
"""Build a self-contained HTML report for the Flux full-body method evaluation."""

from __future__ import annotations

import base64
import html
from pathlib import Path

PROJECT = Path(__file__).resolve().parents[1]
ROOT = PROJECT / "results/aesthetic/20260813-flux-fullbody-methods"

ROWS = [
    ("A · 基准提示词", "a_baseline_prompt", "31415", "通过", "全身完整；脚下留白偏紧；自然度好。", "8.6"),
    ("A · 基准提示词", "a_baseline_prompt", "27182", "通过", "全身完整；自然侧身；身份与参考有偏移。", "8.5"),
    ("B · 强化全身提示词", "b_enhanced_prompt", "31415", "通过", "全身完整；边缘余量略优；与 A 差异很小。", "8.8"),
    ("B · 强化全身提示词", "b_enhanced_prompt", "27182", "通过", "全身完整；自然度好；与 A 基本等效。", "8.7"),
    ("C · 强化提示词 + OpenPose", "c_enhanced_flux_openpose", "31415", "通过", "构图最稳定；站姿准确；人物略显拘谨。", "8.7"),
    ("C · 强化提示词 + OpenPose", "c_enhanced_flux_openpose", "27182", "有瑕疵", "构图稳定，但右脚后方出现多余脚部伪影，身份漂移较明显。", "7.0"),
]


def data_uri(path: Path) -> str:
    return "data:image/png;base64," + base64.b64encode(path.read_bytes()).decode("ascii")


def main() -> None:
    cards = []
    for method, folder, seed, status, note, score in ROWS:
        image = ROOT / folder / f"seed_{seed}.png"
        badge = "warn" if status != "通过" else "pass"
        cards.append(f"""
        <article class="card">
          <img src="{data_uri(image)}" alt="{html.escape(method)} seed {seed}">
          <div class="body">
            <div class="line"><strong>{html.escape(method)}</strong><span class="badge {badge}">{status}</span></div>
            <div class="meta">Seed {seed} · 综合 {score}/10</div>
            <p>{html.escape(note)}</p>
          </div>
        </article>""")

    page = f"""<!doctype html>
<html lang="zh-CN"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<title>Flux 全身像方法首轮评测</title>
<style>
:root{{--bg:#f4f3ef;--ink:#20231f;--muted:#6b7169;--green:#176b4d;--line:#dedfd9;--card:#fff;--amber:#a65f00}}
*{{box-sizing:border-box}} body{{margin:0;background:var(--bg);color:var(--ink);font:16px/1.55 -apple-system,BlinkMacSystemFont,"Segoe UI",sans-serif}}
main{{max-width:1180px;margin:auto;padding:54px 28px 72px}} h1{{font-size:38px;line-height:1.15;margin:0 0 12px}} h2{{margin:46px 0 18px;font-size:24px}} .lead{{max-width:850px;color:var(--muted);font-size:18px}}
.verdict{{margin:30px 0 8px;padding:24px 26px;background:#e4f0e9;border-left:5px solid var(--green);border-radius:10px}} .verdict strong{{font-size:21px}}
.metrics{{display:grid;grid-template-columns:repeat(4,1fr);gap:12px;margin:26px 0}} .metric{{background:var(--card);padding:18px;border:1px solid var(--line);border-radius:10px}} .metric b{{display:block;font-size:25px;color:var(--green)}} .metric span{{color:var(--muted);font-size:14px}}
.grid{{display:grid;grid-template-columns:repeat(3,1fr);gap:18px}} .card{{background:var(--card);border:1px solid var(--line);border-radius:12px;overflow:hidden}} .card img{{display:block;width:100%;aspect-ratio:3/4;object-fit:cover}} .body{{padding:15px 16px 18px}} .line{{display:flex;gap:10px;align-items:flex-start;justify-content:space-between}} .meta,.body p{{color:var(--muted);font-size:14px}} .body p{{margin:7px 0 0}} .badge{{font-size:12px;white-space:nowrap;padding:2px 7px;border-radius:999px}} .pass{{color:var(--green);background:#dff1e8}} .warn{{color:var(--amber);background:#fff0d5}}
table{{width:100%;border-collapse:collapse;background:#fff;border:1px solid var(--line)}} th,td{{text-align:left;padding:13px;border-bottom:1px solid var(--line)}} th{{background:#eceee9}} .rec{{display:grid;grid-template-columns:1fr 1fr;gap:18px}} .panel{{background:#fff;border:1px solid var(--line);border-radius:10px;padding:20px}} .panel h3{{margin-top:0}} code{{background:#eceee9;padding:2px 5px;border-radius:4px}} footer{{margin-top:44px;color:var(--muted);font-size:13px}}
@media(max-width:800px){{.grid,.metrics,.rec{{grid-template-columns:1fr}}h1{{font-size:31px}}main{{padding:32px 16px}}}}
</style></head><body><main>
<p style="color:var(--green);font-weight:700">工具评测 · 2026-08-13</p>
<h1>Flux 全身像最佳用法：首轮评测</h1>
<p class="lead">同一 Flux 工作流、同一身份参考、两组共享种子，对比基准提示词、强化全身提示词、强化提示词加 Flux OpenPose ControlNet。目标是判断 Flux 能否独立生成全身像，以及 OpenPose 是否应进入默认流程。</p>
<div class="verdict"><strong>结论：Flux 可以生成全身像；OpenPose 不应默认启用。</strong><br>默认使用强化全身提示词（B）。只有在姿态、人物占比或站位必须精确复现时，才按需启用 OpenPose（C）。</div>
<section class="metrics"><div class="metric"><b>6 / 6</b><span>完整全身构图</span></div><div class="metric"><b>4 / 4</b><span>纯提示词全身成功</span></div><div class="metric"><b>1 / 2</b><span>OpenPose 无明显瑕疵</span></div><div class="metric"><b>≈ 42 分钟</b><span>6 张实测纯生成耗时</span></div></section>
<h2>逐图结果</h2><div class="grid">{''.join(cards)}</div>
<h2>方法对比</h2>
<table><thead><tr><th>方法</th><th>全身稳定性</th><th>自然度 / 身份</th><th>额外成本</th><th>定位</th></tr></thead><tbody>
<tr><td>A 基准提示词</td><td>2/2</td><td>好</td><td>无</td><td>快速探索可用</td></tr>
<tr><td><strong>B 强化提示词</strong></td><td><strong>2/2</strong></td><td><strong>好</strong></td><td><strong>无</strong></td><td><strong>默认推荐</strong></td></tr>
<tr><td>C + OpenPose</td><td>2/2</td><td>身份略降；1 张脚部伪影</td><td>4.29 GB 模型 + 骨架准备</td><td>精确构图时按需使用</td></tr>
</tbody></table>
<h2>建议工作流</h2><div class="rec">
<div class="panel"><h3>默认：强化提示词</h3><p>明确写入：<code>strict full-length</code>、<code>hair to soles</code>、<code>both complete feet</code>、<code>camera pulled far back</code>、<code>floor below boots</code>、<code>margin above head</code>、<code>no crop</code>。</p><p>本轮中无需 OpenPose 已达到 100% 全身成功率，且自然度、身份延续更好。</p></div>
<div class="panel"><h3>按需：Flux OpenPose</h3><p>适用于固定站姿、连续镜头一致姿态、版式要求人物必须处于指定区域。当前推荐参数：强度 <code>0.9</code>，结束比例 <code>0.65</code>。</p><p>骨架图必须先匹配输出画幅并预留头顶、脚下边距；同时必须检查多肢、脚部和身份漂移。</p></div></div>
<h2>决策</h2><p><strong>保留 Flux OpenPose ControlNet，但作为可选模块，不加入默认生成链。</strong> RealVisXL 继续维持“从默认工作流移除、模型文件和脚本暂留”的状态。下一轮应扩大到 8–12 个种子，并加入复杂动作，专门验证 OpenPose 的收益边界。</p>
<footer>模型：Shakker-Labs FLUX.1-dev ControlNet Union Pro 2.0 · 输出 768×1024 · 20 steps · 两组共享种子 31415 / 27182。报告图片全部内嵌，可离线打开。</footer>
</main></body></html>"""
    (ROOT / "report.html").write_text(page, encoding="utf-8")
    print(ROOT / "report.html")


if __name__ == "__main__":
    main()
