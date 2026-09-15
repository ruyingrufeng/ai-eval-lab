#!/usr/bin/env python3
"""Render an evaluation artifact to a standalone, dependency-free HTML report."""
import argparse
import html
import json
from pathlib import Path

CSS = """
:root{color-scheme:light;--ink:#27233b;--muted:#625e74;--line:#dfdaed;--accent:#5a4bd1}
*{box-sizing:border-box}body{margin:0;background:linear-gradient(130deg,#f1eefb,#fff6f9);color:var(--ink);font:16px/1.7 -apple-system,BlinkMacSystemFont,'PingFang SC',sans-serif}
main{max-width:1080px;margin:auto;padding:48px 24px 72px}header{border-top:6px solid var(--accent);padding-top:24px}h1{font-size:clamp(28px,4vw,42px);line-height:1.25;margin:12px 0}h2{font-size:23px;line-height:1.4;margin:0 0 16px}p{margin:10px 0}.meta{font-size:14px;color:var(--muted)}.badge{display:inline-block;background:#efe9ff;color:#5141b6;padding:5px 12px;border-radius:30px;font-size:14px;font-weight:650}.lead{font-size:19px;max-width:880px}.cards{display:grid;grid-template-columns:repeat(4,1fr);gap:14px;margin:28px 0}.card,section{background:rgba(255,255,255,.91);border:1px solid var(--line);border-radius:16px;box-shadow:0 8px 24px #35275d08}.card{padding:18px}.card strong{display:block;font-size:28px;color:var(--accent)}.card small{display:block;color:var(--muted);font-size:13px}section{padding:24px;margin:20px 0}.quote{border-left:4px solid #e85a8e;padding:8px 20px;background:#fff4f8;font-size:22px;margin:16px 0}.scroll{max-width:100%;overflow-x:auto}table{width:100%;border-collapse:collapse;font-size:14px}th,td{text-align:left;padding:10px;border-bottom:1px solid var(--line);vertical-align:top}th{background:#f4f1fc;white-space:nowrap}td:first-child{min-width:130px}pre{padding:16px;background:#26233a;color:#f5f1ff;border-radius:9px;overflow:auto;font-size:13px;line-height:1.6}code{font-family:ui-monospace,monospace;overflow-wrap:anywhere}a{color:var(--accent);overflow-wrap:anywhere}li{margin:7px 0}.path{overflow-wrap:anywhere;font-size:13px}footer{color:var(--muted);font-size:13px;margin-top:32px}details{margin:12px 0}summary{cursor:pointer;font-weight:600}@media(max-width:650px){main{padding:24px 14px 40px}.cards{grid-template-columns:repeat(2,minmax(0,1fr));gap:10px}.card{padding:14px}.card strong{font-size:23px}section{padding:18px}.lead{font-size:17px}table{min-width:650px}.quote{font-size:19px}}
@media print{body{background:white}main{padding:0}.card,section{box-shadow:none;break-inside:avoid}.scroll{overflow:visible}pre{white-space:pre-wrap}}
"""


def render(data):
    e = lambda x: html.escape(str(x))
    out = ['<!doctype html><html lang="zh-CN"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">',
           f'<title>{e(data["title"])}</title><style>{CSS}</style></head><body><main>',
           f'<header><div class="meta">本地内容工具与模型实验室 · {e(data["as_of"])} · M5 / 32GB</div><h1>{e(data["title"])}</h1>',
           f'<span class="badge">{e(data["gate_label"])}</span><p class="lead">{e(data["summary"])}</p></header><div class="cards">']
    for item in data['metrics']:
        out.append(f'<div class="card"><div>{e(item["label"])}</div><strong>{e(item["value"])}</strong><small>{e(item["note"])}</small></div>')
    out.append('</div>')
    for section in data['sections']:
        out.append(f'<section id="{e(section["id"])}"><h2>{e(section["title"])}</h2>')
        for para in section.get('paragraphs', []):
            out.append(f'<p>{e(para)}</p>')
        if 'quote' in section:
            out.append(f'<blockquote class="quote">{e(section["quote"])}</blockquote>')
        if section.get('bullets'):
            out.append('<ul>'+''.join(f'<li>{e(x)}</li>' for x in section['bullets'])+'</ul>')
        if section.get('table'):
            tab = section['table']
            out.append('<div class="scroll" tabindex="0" aria-label="可横向滚动的数据表"><table><thead><tr>'+''.join(f'<th>{e(c)}</th>' for c in tab['columns'])+'</tr></thead><tbody>')
            out.extend('<tr>'+''.join(f'<td>{e(c)}</td>' for c in row)+'</tr>' for row in tab['rows'])
            out.append('</tbody></table></div>')
        for command in section.get('commands', []):
            out.append(f'<pre><code>{e(command)}</code></pre>')
        for link in section.get('links', []):
            out.append(f'<p><a href="{e(link["url"])}">{e(link["label"])}</a></p>')
        out.append('</section>')
    out.append('<footer>由 artifact.json 统一生成。数值、结论与限制来自同一数据源；无远程脚本、字体或媒体依赖。原始音频与模型留在部署目录。</footer>')
    # Embed the same machine-readable artifact; never interpolate it as executable JS.
    payload = json.dumps(data, ensure_ascii=False).replace('<', '\\u003c')
    out.append(f'<script type="application/json" id="artifact">{payload}</script></main></body></html>')
    return '\n'.join(out)


if __name__ == '__main__':
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('artifact', type=Path)
    p.add_argument('output', type=Path)
    a = p.parse_args()
    a.output.write_text(render(json.loads(a.artifact.read_text())), encoding='utf-8')
    print(a.output)
