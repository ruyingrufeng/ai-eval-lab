#!/usr/bin/env python3
"""Validate and render the independent-reference F5/Fish emotional A/B."""
import datetime as dt,hashlib,html,json,math,random,runpy,shutil,wave
from pathlib import Path
import numpy as np
ROOT=Path(__file__).resolve().parents[1];DEPLOY=Path('/Users/jacky/Documents/Codex/2026-09-03/referenced-chatgpt-conversation-this-is-an/outputs/f5-tts-local');RID='tts_emotion_reference_ab_20260904';runs={'F5':ROOT/'results/f5_tts_emotion_ab_f5_20260904_0900','Fish S2':ROOT/'results/f5_tts_emotion_ab_fish_20260904_0902'}
manifest=json.loads((ROOT/'benchmarks/f5_tts_emotion_reference_ab_20260904.json').read_text());expected=[c['id'] for c in manifest['cases']];assert len(expected)==len(set(expected))==6
engines={}
for engine,r in runs.items():
 status=json.loads((r/'status.json').read_text());worker=json.loads((r/'worker-result.json').read_text());rows=[json.loads(x) for x in (r/'events.jsonl').read_text().splitlines() if json.loads(x).get('event')=='generated']
 assert status['state']=='runnable' and status['exit_code']==0 and worker['ok'] and worker['completed']==expected and [x['id'] for x in rows]==expected
 for x in rows:
  p=Path(x['path']);assert p.is_file() and hashlib.sha256(p.read_bytes()).hexdigest()==x['sha256']
  with wave.open(str(p)) as w:
   assert w.getnchannels()==1 and w.getsampwidth()==2 and w.getframerate() in (24000,44100);n=w.getnframes();pcm=w.readframes(n);assert n and len(pcm)==2*n
   v=np.frombuffer(pcm,dtype='<i2').astype(float)/32768;assert np.sqrt(np.mean(v*v))>.001 and np.mean(np.abs(v)>=.9999)<=.001
  assert x['generation_seconds']>0 and x['duration_seconds']>0
 asr=json.loads((r/'asr.json').read_text());ast=json.loads((r/'asr-status.json').read_text());assert ast['exit_code']==0 and [x['name'] for x in asr]==expected
 am=runpy.run_path(str(ROOT/'scripts/fish_s2_evidence.py'))['asr_metrics'](asr)
 resources=[json.loads(x) for x in (r/'resources.jsonl').read_text().splitlines()];op=[x for x in resources if x['phase']=='generation'];base=json.loads((r/'baseline.json').read_text())
 exact=sum(x['edits']==0 for x in am['per_clip'])
 summary={'clips':len(rows),'audio_seconds':sum(x['duration_seconds'] for x in rows),'generation_seconds':sum(x['generation_seconds'] for x in rows),'weighted_rtf':sum(x['generation_seconds'] for x in rows)/sum(x['duration_seconds'] for x in rows),'mlx_peak_gib':max(x['mlx_peak_gib'] for x in rows),'rss_max_gib':max(x['rss_gib'] for x in op if x.get('rss_gib') is not None),'pressure_free_min':min(x['free_percent'] for x in op),'pressure_free_max':max(x['free_percent'] for x in op),'swap_peak_delta_gib':max(x['swap_gib'] for x in op)-base['swap_gib'],'external_models_all_idle':all(all(v in ('sleeping','unloaded') for v in x['models'].values()) for x in resources),'asr':am,'content_exact_clips':exact,'content_gate':'pass' if exact==len(rows) and am['weighted_cer']<=.08 else 'FAIL','rows':rows,'asr_rows':asr,'source_hashes':{str(p):hashlib.sha256(p.read_bytes()).hexdigest() for p in [r/'manifest.json',r/'events.jsonl',r/'resources.jsonl',r/'status.json',r/'worker-result.json',r/'asr.json',r/'asr-status.json']}}
 if engine=='F5':summary['model_load_count']=sum(x.get('event')=='model_loaded' for x in [json.loads(y) for y in (r/'events.jsonl').read_text().splitlines()]);summary['reference_encode_count']='references loaded once in worker memory'
 else:
  gl=[json.loads(y) for y in (r/'generation.jsonl').read_text().splitlines()];summary['model_load_count']=sum(x.get('event')=='model_loaded' for x in gl);summary['reference_encode_count']=sum(x.get('event')=='reference_encoded' for x in gl)
 assert summary['model_load_count']==1
 engines[engine]=summary
prov=json.loads((DEPLOY/'reference-assets/ravdess/provenance.json').read_text());archive=DEPLOY/'reference-assets/ravdess'/prov['archive']['file'];assert archive.stat().st_size==prov['archive']['bytes'] and hashlib.md5(archive.read_bytes()).hexdigest()==prov['archive']['md5']
for e,r in manifest['references'].items():assert hashlib.sha256(Path(r['path']).read_bytes()).hexdigest()==r['sha256']==prov['derived_references'][e]['sha256']
result=ROOT/'results'/RID;result.mkdir(exist_ok=True);feedback=json.loads((result/'user-feedback.json').read_text())
summary={'schema_version':1,'run_id':RID,'analyzed_at':dt.datetime.now().astimezone().isoformat(),'expected_design':'same RAVDESS actor 02; neutral/happy/sad; same paired source statements, same Chinese target and seeds; both engines','reference_provenance':prov,'engines':engines,'human_emotion_review':feedback,'automatic_claim':'Only integrity, ASR content and performance are automated; no automatic emotion pass/fail.','limitations':['English emotional references drive Chinese output, so cross-lingual accent/content is a confound.','RAVDESS strong happy/sad versus normal neutral; intensity is not exactly matched.','Reference loudness was not matched, so volume changes confound emotion judgments.','One speaker, one target sentence and two seeds; no long text or novel scene.'],'source_hashes':{str(p):hashlib.sha256(p.read_bytes()).hexdigest() for p in [ROOT/'benchmarks/f5_tts_emotion_reference_ab_20260904.json',ROOT/'scripts/f5-tts-local.py',ROOT/'scripts/fish-s2-emotion-ab.py',ROOT/'scripts/f5-tts-asr.py',Path(__file__),DEPLOY/'reference-assets/ravdess/provenance.json',result/'user-feedback.json']}}
(result/'summary.json').write_text(json.dumps(summary,ensure_ascii=False,indent=2)+'\n')
metrics=[]
for e,s in engines.items():metrics.extend([{'label':e+' RTF','value':f'{s["weighted_rtf"]:.3f}×','note':f'{s["generation_seconds"]:.2f}s / {s["audio_seconds"]:.2f}s'},{'label':e+' CER','value':f'{s["asr"]["weighted_cer"]:.2%}','note':f'{s["asr"]["edits_total"]}/{s["asr"]["refs_total"]}；自动内容筛查'}])
rows=[]
for e,s in engines.items():rows.append([e,s['clips'],f'{s["mlx_peak_gib"]:.3f} GiB',f'{s["rss_max_gib"]:.3f} GiB',f'{s["pressure_free_min"]}%–{s["pressure_free_max"]}%',f'{s["swap_peak_delta_gib"]:.3f} GiB',s['model_load_count'],s['reference_encode_count']])
artifact={'schema_version':2,'id':RID,'as_of':dt.date.today().isoformat(),'title':'F5-TTS 与 Fish S2：英文参考失败记录','gate':'runnable','gate_label':'runnable · 中文适用性失败，仅保留失败证据','summary':f'12/12输出文件完整，但用户试听确认存在英文、音量不一致和明显外国人说中文的口音；本轮不用于中文模型推荐。F5另有1段串入参考英文。','metrics':metrics,'sections':[{'id':'review','title':'用户试听结论','paragraphs':[feedback['verbatim'],feedback['judgement']], 'bullets':feedback['findings']},{'id':'design','title':'原测试设计','paragraphs':['RAVDESS演员02（女性）的英文中性、开心、悲伤参考；未做统一响度处理。','F5与Fish各生成3种参考情绪 × 2个seed；目标中文均为“你回来了。我一直在这里等你。”。']},{'id':'integrity','title':'自动检查','table':{'columns':['模型','片段','MLX峰值','RSS采样峰值','pressure free','swap峰值增量','模型加载','参考处理'],'rows':rows},'paragraphs':['文件与性能证据仍有效；它们只能证明可以运行，不能证明中文听感合格。']},{'id':'content','title':'文字回检','table':{'columns':['模型','内容门槛','精确片段','加权CER','编辑数/字符','需复核片段'],'rows':[[e,s['content_gate'],f'{s["content_exact_clips"]}/{s["clips"]}',f'{s["asr"]["weighted_cer"]:.2%}',f'{s["asr"]["edits_total"]}/{s["asr"]["refs_total"]}',', '.join(x['name'] for x in s['asr']['per_clip'] if x['review_flags']) or '无'] for e,s in engines.items()]},'paragraphs':['F5 的 sad_123 在目标中文前串入参考英文，内容门槛失败。']},{'id':'limits','title':'失败原因','bullets':summary['limitations']},{'id':'source','title':'来源与许可','paragraphs':['RAVDESS DOI 10.5281/zenodo.1188976，CC BY-NC-SA 4.0；仅本机非商业评测，保留署名。'],'links':[{'label':'RAVDESS 官方 Zenodo','url':'https://zenodo.org/records/1188976'}]}],'evidence':summary}
report=ROOT/'docs/reports'/RID;report.mkdir(parents=True,exist_ok=True);(report/'artifact.json').write_text(json.dumps(artifact,ensure_ascii=False,indent=2)+'\n');(report/'report.html').write_text(runpy.run_path(str(ROOT/'scripts/render-evaluation-record.py'))['render'](artifact));(report/'SOURCE_NOTES.md').write_text('证据来自RAVDESS官方归档、本机两个串行运行、ASR及用户试听反馈。本轮中文适用性失败。\n')
out=DEPLOY/'results'/RID;out.mkdir(parents=True,exist_ok=True);(out/'audio').mkdir(exist_ok=True);(out/'references').mkdir(exist_ok=True)
for f in ['artifact.json','report.html','SOURCE_NOTES.md']:shutil.copy2(report/f,out/f)
shutil.copy2(result/'summary.json',out/'summary.json');shutil.copy2(DEPLOY/'reference-assets/ravdess/ATTRIBUTION.md',out/'ATTRIBUTION.md')
for em,r in manifest['references'].items():shutil.copy2(r['path'],out/'references'/f'{em}.wav')
mapping=[]
for e,s in engines.items():
 for row in s['rows']:
  target=out/'audio'/f'{e.lower().replace(" ","-")}_{row["id"]}.wav';shutil.copy2(row['path'],target);mapping.append({'model':e,'emotion':row['reference_emotion'],'seed':row['seed'],'file':'audio/'+target.name})
random.Random(20260904).shuffle(mapping);(out/'mapping.json').write_text(json.dumps(mapping,ensure_ascii=False,indent=2)+'\n')
e=html.escape;page=['<!doctype html><html lang="zh-CN"><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><title>情绪参考盲听</title><style>body{max-width:900px;margin:32px auto;padding:0 18px;background:#f4f3f9;color:#252337;font:17px/1.7 system-ui}section{background:#fff;padding:18px;margin:18px 0;border-radius:14px}audio{width:100%}details{margin-top:8px}summary{cursor:pointer;font-weight:600}.clip{border-top:1px solid #ddd;padding:14px 0}</style><h1>独立情绪参考 A/B 盲听</h1><p>目标台词始终相同：你回来了。我一直在这里等你。先听原参考，随后在不展开答案时判断每段情绪和模型。</p><section><h2>同一演员的原参考</h2>']
for em,label in [('neutral','中性'),('happy','开心（强）'),('sad','悲伤（强）')]:page.append(f'<p>{label}</p><audio controls preload="none" src="references/{em}.wav"></audio>')
page.append('</section><section><h2>12段随机盲听</h2>')
for i,x in enumerate(mapping,1):page.append(f'<div class="clip"><strong>样本 {i:02d}</strong><audio controls preload="none" src="{e(x["file"])}"></audio><details><summary>听完再展开答案</summary><p>模型：{e(x["model"])}；参考情绪：{e(x["emotion"])}；seed：{x["seed"]}</p></details></div>')
page.append('</section><p>建议记录：听到的情绪、强度1–5、是否同一人、自然度1–5、内容问题。<a href="report.html">查看技术报告</a></p></html>');(out/'listening.html').write_text('\n'.join(page));print(out)
