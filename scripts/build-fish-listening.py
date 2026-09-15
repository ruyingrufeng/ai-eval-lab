#!/usr/bin/env python3
"""Create a local listening pack with native audio controls and blank ratings."""
import argparse
import csv
import hashlib
import html
import json
from pathlib import Path
import random
import shutil

ROOT=Path(__file__).resolve().parents[1]
OUTPUT=Path('/Users/jacky/Documents/Codex/2026-09-03/referenced-chatgpt-conversation-this-is-an/outputs/fish-s2-continued')
OLD=ROOT/'results/fish_s2_followup_20260903_142148'

def build(rid):
    run=ROOT/'results'/rid;dest=OUTPUT/rid;audio=dest/'audio';audio.mkdir(parents=True,exist_ok=True)
    raw=[json.loads(l) for l in (run/'generation.jsonl').read_text().splitlines()]
    generated={r['name']:r for r in raw if r.get('event')=='generated'}
    groups=[]
    rng=random.Random(426)
    for seed in [42,123]:
        for role in ['narrator','A','B']:
            names=[f'T3_{role}_{emotion}_seed{seed}' for emotion in ['neutral','excited','sad']]
            rng.shuffle(names)
            groups.append(('比较情绪差异',f'声音组 {role} · 第 {1 if seed==42 else 2} 组：相同台词、相同参考，比较三种演绎是否可辨。',names))
    for role in ['narrator','A','B']:
        names=[f'ANCHOR_{role}_{pos}' for pos in ['start','middle','end']]
        rng.shuffle(names)
        groups.append(('比较声音一致性',f'声音组 {role}：同一台词在运行前、中、后生成，比较是否换人、变调或劣化。',names))
    if (run/'summary.json').exists():
        summary=json.loads((run/'summary.json').read_text())
        flagged=[r['name'] for r in summary.get('asr_per_clip',[]) if r.get('review_flags') and r['name'] in generated]
        if flagged:groups.append(('核对文字完整性','自动回检发现差异，不代表音频一定错误。请核对漏读、重复和结尾。',flagged))
    mapping=[];cards=[];count=0
    e=html.escape
    for title,purpose,names in groups:
        parts=[]
        for name in names:
            if name not in generated:continue
            count+=1;g=generated[name];src=Path(g['output']);target=audio/f'{count:03d}.wav';shutil.copy2(src,target)
            digest=hashlib.sha256(target.read_bytes()).hexdigest()
            if digest!=hashlib.sha256(src.read_bytes()).hexdigest():raise ValueError('Copy mismatch')
            mapping.append({'id':f'{count:03d}','case_id':name,'source':str(src),'sha256':digest})
            options='<option value="">未评分</option>'+''.join(f'<option>{n}</option>' for n in range(1,6))
            parts.append(f'<article data-case="{e(name)}"><h3>试听 {count:03d}</h3><audio controls preload="none" src="audio/{count:03d}.wav"></audio><p><label>听到的情绪 <select class="emotion"><option value="">未选择</option><option>平淡</option><option>兴奋</option><option>悲伤</option><option>无法判断</option></select></label></p><label>清晰度 <select class="clarity">{options}</select></label> <label>自然度 <select class="natural">{options}</select></label><p><input class="notes" placeholder="可选：漏句、声音变化或其他发现" aria-label="试听备注"></p><details><summary>听完后查看设置和台词</summary><p>{e(name)}</p><p>{e(g["text"])}</p></details></article>')
        cards.append(f'<section><h2>{e(title)}</h2><p>{e(purpose)}</p><div class="grid">'+''.join(parts)+'</div></section>')
    chapter=next((OLD/'assembled').glob('chapter_*.wav'))
    shutil.copy2(chapter,audio/'chapter.wav')
    (dest/'mapping.json').write_text(json.dumps(mapping,ensure_ascii=False,indent=2)+'\n')
    with (dest/'listening_review.csv').open('w') as f:
        w=csv.writer(f);w.writerow(['case_id','perceived_emotion','intelligibility_1to5','naturalness_1to5','notes']);w.writerows([x['case_id'],'','','',''] for x in mapping)
    css='body{margin:0;background:#f5f4f0;color:#26342e;font:17px/1.6 system-ui,sans-serif}main{max-width:1050px;margin:auto;padding:32px 20px}h1{font-size:32px}section{margin:30px 0}.grid{display:grid;grid-template-columns:repeat(auto-fit,minmax(260px,1fr));gap:16px}article,.chapter{background:white;padding:18px;border:1px solid #d7ded7;border-radius:12px}audio{width:100%}input{box-sizing:border-box;width:100%;padding:9px}select,button{font:inherit;padding:6px}button{background:#245d43;color:white;border:0;border-radius:7px;padding:10px 18px}details{font-size:14px;color:#555}footer{margin:32px 0;color:#555}label{font-size:15px}'
    js="""document.querySelector('#export').onclick=()=>{let rows=[['case_id','perceived_emotion','intelligibility_1to5','naturalness_1to5','notes']];document.querySelectorAll('article').forEach(a=>rows.push([a.dataset.case,a.querySelector('.emotion').value,a.querySelector('.clarity').value,a.querySelector('.natural').value,a.querySelector('.notes').value]));let csv='\\ufeff'+rows.map(r=>r.map(v=>'"'+String(v).replaceAll('"','""')+'"').join(',')).join('\\r\\n');let u=URL.createObjectURL(new Blob([csv],{type:'text/csv;charset=utf-8'}));let a=document.createElement('a');a.href=u;a.download='listening_review.csv';a.click();setTimeout(()=>URL.revokeObjectURL(u),1000)};"""
    doc=f'<!doctype html><html lang="zh-CN"><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><title>Fish 本地补测试听</title><style>{css}</style><main><h1>Fish 本地补测试听</h1><p>先听同一声音组三条短音频，判断情绪有没有差异。评分完全可选，不会预填；页面不上传数据。填写后请导出，关闭页面不会自动保存。</p><button id="export">导出我的试听记录</button><section class="chapter"><h2>完整章节 · 约 4 分 32 秒</h2><p>复用上一轮 21 段，已核对顺序与间隔。请听漏句、重复、角色切换和停顿是否自然。</p><audio controls preload="none" src="audio/chapter.wav"></audio></section>'+''.join(cards)+f'<footer>本轮编号：{e(rid)}。旧轮 A 声音的反馈不代替本轮试听。声音时长和响度变化不能自动证明情绪有效。</footer></main><script>{js}</script></html>'
    (dest/'listening.html').write_text(doc)
    print(dest/'listening.html')

if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('run_id');a=p.parse_args();build(a.run_id)
