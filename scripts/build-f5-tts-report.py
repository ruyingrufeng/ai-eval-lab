#!/usr/bin/env python3
"""Bind F5 smoke artifacts to successful worker exit and actual WAV/ASR data."""
import argparse,datetime as dt,hashlib,html,json,math,runpy,shutil,wave
from pathlib import Path
import numpy as np
ROOT=Path(__file__).resolve().parents[1]
p=argparse.ArgumentParser();p.add_argument('run_id');a=p.parse_args();r=ROOT/'results'/a.run_id
m=json.loads((r/'manifest.json').read_text());status=json.loads((r/'status.json').read_text());worker=json.loads((r/'worker-result.json').read_text())
raw=[json.loads(l) for l in (r/'events.jsonl').read_text().splitlines()];rows=[e for e in raw if e['event']=='generated'];expected=[c['id'] for c in m['cases']]
assert expected and len(set(expected))==len(expected)
assert status['exit_code']==0 and worker['ok'] and worker['completed']==expected and [c['id'] for c in rows]==expected
for e in rows:
    path=Path(e['path']);assert hashlib.sha256(path.read_bytes()).hexdigest()==e['sha256']
    with wave.open(str(path)) as w:
        assert (w.getframerate(),w.getnchannels(),w.getsampwidth())==(24000,1,2)
        n=w.getnframes();pcm=w.readframes(n);assert n>0 and len(pcm)==n*2
        assert abs(n/24000-e['duration_seconds'])<1e-9
        values=np.frombuffer(pcm,dtype='<i2').astype(float)/32768
        assert np.sqrt(np.mean(values**2))>=.001 and np.mean(np.abs(values)>=.9999)<=.001
    assert e['generation_seconds']>0 and math.isfinite(e['rtf'])
measured=[e for e in rows if e['group']!='warmup'];seconds=sum(e['generation_seconds'] for e in measured);duration=sum(e['duration_seconds'] for e in measured)
asr=json.loads((r/'asr.json').read_text());asr_status=json.loads((r/'asr-status.json').read_text());assert asr_status['exit_code']==0 and [e['name'] for e in asr]==expected
asrm=runpy.run_path(str(ROOT/'scripts/fish_s2_evidence.py'))['asr_metrics'](asr)
resources=[json.loads(l) for l in (r/'resources.jsonl').read_text().splitlines()];operating=[s for s in resources if s['phase']=='generation'];baseline=json.loads((r/'baseline.json').read_text())
loads=[e for e in raw if e['event']=='model_loaded'];assert len(loads)==1
res={k:{'min':min(s[k] for s in operating if s.get(k) is not None),'max':max(s[k] for s in operating if s.get(k) is not None)} for k in ['free_percent','available_gib','wired_gib','swap_gib','rss_gib']}
res.update(mlx_peak_gib=max(e['mlx_peak_gib'] for e in rows),swap_peak_delta_gib=max(s['swap_gib'] for s in operating)-baseline['swap_gib'],sample_count=len(resources),external_models_all_idle=all(all(v in ('unloaded','sleeping') for v in s['models'].values()) for s in resources))
summary={'run_id':r.name,'generated_count':len(rows),'measured_count':len(measured),'generation_seconds':seconds,'audio_seconds':duration,'weighted_rtf':seconds/duration,'load':loads[0],'asr':asrm,'resources':res,'human_review':'pending','emotion_reference_control':'not tested: expressive references from the same voice unavailable','model_lock':json.loads((Path(m['deployment'])/'model-lock.json').read_text()),'source_hashes':{str(q):hashlib.sha256(q.read_bytes()).hexdigest() for q in [r/'manifest.json',r/'events.jsonl',r/'resources.jsonl',r/'asr.json',r/'asr-status.json',r/'status.json',Path(__file__)]}}
(r/'summary.json').write_text(json.dumps(summary,ensure_ascii=False,indent=2)+'\n')
# Scene is an explicit sequential assembly of three measured model outputs.
scene=r/'audio/scene.wav';chunks=[]
for idx,e in enumerate(x for x in rows if x['group']=='scene'):
    with wave.open(e['path']) as w:
        if idx:chunks.append(bytes(6000*2))
        chunks.append(w.readframes(w.getnframes()))
with wave.open(str(scene),'wb') as w:w.setnchannels(1);w.setsampwidth(2);w.setframerate(24000);w.writeframes(b''.join(chunks))
with wave.open(str(scene)) as w:assert w.readframes(w.getnframes())==b''.join(chunks)
cer=asrm['weighted_cer'];artifact={'schema_version':2,'id':r.name,'as_of':dt.date.today().isoformat(),'title':'F5-TTS MLX 中文初测','gate':'runnable','gate_label':'runnable · 中文生成已跑通，听感待评','summary':f'{len(rows)}/{len(expected)} 段生成与音频校验通过；不含预热的 RTF {seconds/duration:.3f}，自动转写 CER {cer:.2%}。本轮是语境与声线试听，尚未验证同一音色的参考情绪控制。','metrics':[{'label':'音频成功','value':f'{len(rows)}/{len(expected)}','note':'模型单次加载；含1段预热'},{'label':'加权 RTF','value':f'{seconds/duration:.3f}×','note':'纯生成时间 / 音频时长，不含预热与加载'},{'label':'自动 CER','value':f'{cer:.2%}','note':f'{asrm["edits_total"]}/{asrm["refs_total"]}，包括预热；不是人工验收'},{'label':'MLX 峰值','value':f'{res["mlx_peak_gib"]:.2f} GiB','note':'不等于进程RSS或整机内存'}],'sections':[
{'id':'scope','title':'这轮能回答什么','paragraphs':['使用 lucasnewman/f5-tts-mlx 的 model_v1.safetensors 未量化权重；不将文件名等同于官方 F5TTS_v1_Base。实际版本与哈希见下方证据。','三条参考均来自此前 Fish 合成音频，已转为24kHz单声道；不是对真人克隆相似度的验收。','同一平静参考 + 中性/开心/悲伤文本，各两个seed，只测试语境影响。没有情绪指令接口，不把 [sad] 等标签当成受支持控制。','三角色由固定参考逐句生成并拼接，不含自动小说角色识别或情节导演。','缺少同一声线的明显情绪参考；参考驱动的情绪控制、长篇稳定性、完整章节、真人相似度均未验收。保持 runnable，不推荐替换现有语音路线。']},
{'id':'method','title':'方法与兼容性','paragraphs':['Python 3.12 独立虚拟环境；f5-tts-mlx 0.2.6 / MLX 0.32.2 / vocos-mlx 0.0.7。32步 Euler、CFG 2、sway -1、seed 42/123。使用UTF-8字数与中文标点估计时长；参考+输出限制30秒。','加载器只适配本地权重路径；神经网络计算未修改。绕过上游仅识别英文标点的分句方法，显式逐段生成，避免漏掉中文尾句。','Hugging Face直连下载缓慢，终止自有下载进程后改为分块镜像；最终两份权重均对照官方固定revision的SHA256校验。下载与模型加载/预热均不计入生成RTF。','首轮范围小，不与Fish不同样本、不同模型配置的总RTF作严格A/B。']},
{'id':'resources','title':'系统资源','table':{'columns':['指标','实测'],'rows':[[k,json.dumps(v,ensure_ascii=False)] for k,v in res.items()]},'paragraphs':['系统pressure/free、swap、进程RSS、MLX分配分别记录。12GiB是运行器设置，不当作整机硬上限。原始vm_stat保存于resources.jsonl。']},
{'id':'clips','title':'片段与内容回检','table':{'columns':['片段','秒','生成秒','RTF','ASR差异'],'rows':[[e['id'],round(e['duration_seconds'],3),round(e['generation_seconds'],3),round(e['rtf'],3),next(x['transcript'] for x in asr if x['name']==e['id'])] for e in rows]},'paragraphs':['CER保留同音字差异，去标点与空格；数值筛查不判断情绪、声纹或自然度。当前无用户听评分数。']},
{'id':'sources','title':'来源与复现','links':[{'label':'MLX实现与说明','url':'https://github.com/lucasnewman/f5-tts-mlx'},{'label':'官方多风格推理说明','url':'https://github.com/SWivid/F5-TTS/tree/main/src/f5_tts/infer'},{'label':'原始F5-TTS项目与模型许可','url':'https://github.com/SWivid/F5-TTS'}],'paragraphs':['代码MIT；原始预训练模型项目声明CC-BY-NC，转换仓库MIT标记不能自动覆盖原始权重限制。','summary.json → artifact.json → 自包含HTML；静态及数据绑定检查，不宣称完成浏览器视觉验收。']}], 'evidence':summary}
report=ROOT/'docs/reports'/r.name;report.mkdir(parents=True,exist_ok=True)
(report/'artifact.json').write_text(json.dumps(artifact,ensure_ascii=False,indent=2)+'\n');(report/'report.html').write_text(runpy.run_path(str(ROOT/'scripts/render-evaluation-record.py'))['render'](artifact))
(report/'SOURCE_NOTES.md').write_text('来源：原始运行manifest、events、resources、ASR及模型哈希。监听与情绪效果待人工反馈。音频只留本机，不纳入仓库。\n')
out=Path(m['deployment'])/'results'/r.name;out.mkdir(parents=True,exist_ok=True);(out/'audio').mkdir(exist_ok=True);(out/'references').mkdir(exist_ok=True)
for name in ['report.html','artifact.json','SOURCE_NOTES.md']:shutil.copy2(report/name,out/name)
for name in ['summary.json','asr.json','manifest.json']:shutil.copy2(r/name,out/name)
for f in (r/'audio').glob('*.wav'):shutil.copy2(f,out/'audio'/f.name)
for name,ref in m['references'].items():shutil.copy2(ref['path'],out/'references'/f'{name}.wav')
e=html.escape;page=['<!doctype html><html lang="zh-CN"><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><title>F5-TTS 试听</title><style>body{max-width:850px;margin:32px auto;padding:0 18px;background:#f7f6fb;color:#242234;font:17px/1.7 system-ui}section{padding:18px;margin:20px 0;background:white;border-radius:14px}audio{width:100%}summary{cursor:pointer}</style><h1>F5-TTS 中文试听</h1><p>先听三角色短场景，再比较同一音色的不同语境。开心与悲伤是文本语境，不是已生效的情绪指令。请判断实际听感。</p><section><h2>三角色短场景</h2><audio controls preload="none" src="audio/scene.wav"></audio><p>旁白 → A → B；片段间隔0.25秒。</p></section>']
for voice in m['references']:
    page.append(f'<section><h2>声线 {e(voice)} · 原参考与克隆</h2><p>原参考（Fish合成）</p><audio controls preload="none" src="references/{e(voice)}.wav"></audio><p>F5输出：你终于回来了，我一直在这里等你。</p><audio controls preload="none" src="audio/voice_{e(voice)}.wav"></audio></section>')
for seed in [42,123]:
    page.append(f'<section><h2>同一声线 A · 不同语境 · seed {seed}</h2>')
    for c in [x for x in m['cases'] if x['group']=='semantic_context' and x['seed']==seed]:page.append(f'<p>{e(c["text"])}</p><audio controls preload="none" src="audio/{e(c["id"])}.wav"></audio>')
    page.append('</section>')
page.append('<p>本页无自动评分。情绪变化、声音一致性、自然度与漏字请分别判断。<a href="report.html">查看报告</a></p></html>');(out/'listening.html').write_text('\n'.join(page))
print(json.dumps({'run':r.name,'rtf':seconds/duration,'cer':cer,'resources':res,'outputs':str(out)},ensure_ascii=False,indent=2))
