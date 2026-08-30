#!/usr/bin/env python3
"""Create a self-contained report for the Flux identity-lock evaluation."""
from __future__ import annotations
import base64, html, json
from pathlib import Path

PROJECT=Path(__file__).resolve().parents[1]
ROOT=PROJECT/'results/aesthetic/20260813-flux-identity-lock'
REF=PROJECT/'results/aesthetic/20260812-blind/flux/seed_0007.png'
SIM={x['name']:x['similarity'] for x in json.loads((ROOT/'final_similarity.json').read_text())}

def uri(p): return 'data:image/png;base64,'+base64.b64encode(Path(p).read_bytes()).decode()
def card(title,path,key,note,best=False):
    return f'''<article class="card {'best' if best else ''}"><img src="{uri(path)}"><div><b>{html.escape(title)}</b><strong>{SIM[key]:.3f}</strong><p>{html.escape(note)}</p></div></article>'''

cards=[]
for w in ('0.85','1.00','1.15'):
 for s in (31415,27182):
  notes={'0.85':'身份约束偏弱','1.00':'单阶段最佳平衡','1.15':'跨 seed 明显失稳'}
  cards.append(card(f'权重 {w} · Seed {s}',ROOT/f'weight_{w}'/f'seed_{s}.png',f'w{w}_{s}',notes[w],w=='1.00'))
for s in (31415,27182): cards.append(card(f'二阶段修脸 · Seed {s}',ROOT/'two_stage_face'/f'seed_{s}.png',f'two_stage_{s}','相似度稳定提升，但尚未达到同一人验收线',True))

page=f'''<!doctype html><html lang="zh-CN"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><title>Flux 身份锁定专项评测</title><style>
:root{{--p:#6c5ce7;--pink:#fd79a8;--ink:#242235;--muted:#69667a;--line:#e5e0ef}}*{{box-sizing:border-box}}body{{margin:0;background:linear-gradient(145deg,#faf8ff,#fff5f8);color:var(--ink);font:17px/1.6 -apple-system,BlinkMacSystemFont,"Segoe UI",sans-serif}}main{{max-width:1180px;margin:auto;padding:48px 28px 70px}}h1{{font-size:38px;line-height:1.15;margin:5px 0 12px}}h2{{margin-top:42px}}.lead{{color:var(--muted);max-width:850px}}.verdict{{padding:22px 25px;margin:28px 0;background:rgba(255,255,255,.86);border:1px solid var(--line);border-left:5px solid var(--p);border-radius:14px}}.metrics{{display:grid;grid-template-columns:repeat(4,1fr);gap:12px}}.metric{{padding:17px;background:#fff;border:1px solid var(--line);border-radius:12px}}.metric b{{display:block;font-size:25px;color:var(--p)}}.metric span{{font-size:14px;color:var(--muted)}}.grid{{display:grid;grid-template-columns:repeat(4,1fr);gap:15px}}.card{{background:#fff;border:1px solid var(--line);border-radius:13px;overflow:hidden}}.card.best{{box-shadow:0 0 0 2px rgba(108,92,231,.22)}}.card img{{width:100%;aspect-ratio:3/4;object-fit:cover;display:block}}.card div{{padding:13px}}.card strong{{float:right;color:var(--p)}}.card p{{font-size:14px;color:var(--muted);margin:6px 0 0}}table{{width:100%;border-collapse:collapse;background:#fff}}th,td{{padding:12px;border:1px solid var(--line);text-align:left}}th{{background:#f0ecfa}}.next{{padding:20px;background:#fff;border-radius:12px;border:1px solid var(--line)}}code{{background:#eeeaf7;padding:2px 5px;border-radius:4px}}@media(max-width:850px){{.grid,.metrics{{grid-template-columns:1fr 1fr}}}}@media(max-width:520px){{.grid,.metrics{{grid-template-columns:1fr}}}}
</style></head><body><main><p style="color:var(--p);font-weight:700">工具评测 · 2026-08-13</p><h1>Flux 身份锁定专项：加权无效，二阶段有效但未过线</h1><p class="lead">固定模型、提示词、参考图与两个共享种子，对比 IP-Adapter 权重 0.85 / 1.0 / 1.15，并测试“先出全身，再自动检测并局部重绘人脸”的两阶段方案。相似度使用本机 InsightFace antelopev2 对参考图计算。</p>
<div class="verdict"><b>结论：单阶段推荐权重 1.0，但仍不能稳定锁定同一人。二阶段局部修脸是当前更好的方向，两个种子均提升，不过平均 0.339 仍不足以宣布身份通过。</b></div>
<section class="metrics"><div class="metric"><b>0.225</b><span>权重 0.85 平均</span></div><div class="metric"><b>0.279</b><span>权重 1.0 平均</span></div><div class="metric"><b>0.219</b><span>权重 1.15 平均</span></div><div class="metric"><b>0.339</b><span>二阶段修脸平均</span></div></section>
<h2>逐图结果</h2><div class="grid">{''.join(cards)}</div>
<h2>方法判断</h2><table><thead><tr><th>方法</th><th>两种子相似度</th><th>平均</th><th>判断</th></tr></thead><tbody><tr><td>IP-Adapter 0.85</td><td>0.214 / 0.237</td><td>0.225</td><td>约束偏弱</td></tr><tr><td><b>IP-Adapter 1.0</b></td><td>0.276 / 0.283</td><td><b>0.279</b></td><td>单阶段最佳，稳定但不够像</td></tr><tr><td>IP-Adapter 1.15</td><td>0.273 / 0.165</td><td>0.219</td><td>高权重导致失稳，不推荐</td></tr><tr><td><b>二阶段局部修脸</b></td><td>0.332 / 0.345</td><td><b>0.339</b></td><td>两张都提升，方向正确，仍未过线</td></tr></tbody></table>
<h2>根因与下一步</h2><div class="next"><p>原始参考是一张侧脸全身场景图，人脸只占约 63×90 像素。Flux IP-Adapter 接收整图后，大量条件被服装、椅子和植物分走；增加权重会同时强化这些非身份信息，并不能可靠锁脸。</p><p><b>下一步不应继续调权重。</b>应先建立高质量身份母版：正脸、3/4 脸、侧脸各一张，脸部至少 512×512、光照中性、无遮挡。然后再测试二阶段修脸或专用换脸模型。若必须继续使用当前母版，当前生产临时方案为：全身生成权重 <code>1.0</code>，再用裁切参考脸执行 12 steps、denoise <code>0.38</code> 的局部修脸，并逐图人工验收。</p></div>
<p style="color:var(--muted);font-size:13px;margin-top:38px">本轮正式新增 8 张：权重对照 6 张，二阶段 2 张。报告图片全部内嵌，可离线打开。</p></main></body></html>'''
(ROOT/'report.html').write_text(page)
print(ROOT/'report.html')
