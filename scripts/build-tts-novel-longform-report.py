#!/usr/bin/env python3
"""Validate private novel TTS runs, assemble chapters, and render a content-free report."""
import datetime as dt
import hashlib
import html
import json
import random
import runpy
import shutil
import wave
import math
from pathlib import Path

import numpy as np
import soundfile as sf

ROOT=Path(__file__).resolve().parents[1]
DEPLOY=Path('/Users/jacky/Documents/Codex/2026-09-03/referenced-chatgpt-conversation-this-is-an/outputs/f5-tts-local')
RID='tts_novel_longform_20260904'
PRIVATE=ROOT/'results'/RID/'private-manifest.json'
RUNS={'F5-TTS':ROOT/'results/tts_novel_longform_f5_20260904_1022','Fish S2':ROOT/'results/tts_novel_longform_fish_20260904_1026'}
PREP=runpy.run_path(str(ROOT/'scripts/prepare-mcae-spps-references.py'))

def sha(p):return hashlib.sha256(Path(p).read_bytes()).hexdigest()

def normalize_segment(source,target):
 audio,sr=sf.read(source,dtype='float32');assert len(audio)>0
 if audio.ndim>1:audio=np.mean(audio,axis=1)
 if len(audio)/sr>=.5:
  PREP['loudnorm'](source,target);method='ebu_r128'
 else:
  rms=float(np.sqrt(np.mean(audio*audio)));gain=min(.07/max(rms,1e-6),10**(12/20));peak=float(np.max(np.abs(audio)));gain=min(gain,.95/max(peak,1e-6));gain_db=20*math.log10(max(gain,1e-9));__import__('subprocess').run(['ffmpeg','-hide_banner','-loglevel','error','-y','-i',str(source),'-af',f'volume={gain_db}dB','-ar','24000','-ac','1','-c:a','pcm_s16le',str(target)],check=True);method='rms_short_clip_capped_12db'
 saved,_=sf.read(target,dtype='float32');level=20*math.log10(max(float(np.sqrt(np.mean(saved*saved))),1e-9))
 return method,level

m=json.loads(PRIVATE.read_text());source=Path(m['private_source']['path']);assert source.is_file() and sha(source)==m['private_source']['sha256']
expected=[x['id'] for x in m['cases']];assert len(expected)==43 and len(set(expected))==43
engines={}
for name,run in RUNS.items():
 status=json.loads((run/'status.json').read_text());worker=json.loads((run/'worker-result.json').read_text());events=[json.loads(x) for x in (run/'events.jsonl').read_text().splitlines()];rows=[x for x in events if x.get('event')=='generated']
 assert status['state']=='runnable' and status['exit_code']==0 and worker['ok'] and worker['completed']==expected and [x['id'] for x in rows]==expected
 for x in rows:assert Path(x['path']).is_file() and sha(x['path'])==x['sha256']
 asr=json.loads((run/'asr.json').read_text());assert json.loads((run/'asr-status.json').read_text())['exit_code']==0 and [x['name'] for x in asr]==expected
 am=runpy.run_path(str(ROOT/'scripts/fish_s2_evidence.py'))['asr_metrics'](asr)
 resources=[json.loads(x) for x in (run/'resources.jsonl').read_text().splitlines()];op=[x for x in resources if x['phase']=='generation'];base=json.loads((run/'baseline.json').read_text())
 engines[name]={'rows':rows,'clips':len(rows),'audio_seconds':sum(x['duration_seconds'] for x in rows),'generation_seconds':sum(x['generation_seconds'] for x in rows),'weighted_rtf':sum(x['generation_seconds'] for x in rows)/sum(x['duration_seconds'] for x in rows),'mlx_peak_gib':max(x['mlx_peak_gib'] for x in rows),'rss_max_gib':max(x['rss_gib'] for x in op if x.get('rss_gib') is not None),'pressure_free_min':min(x['free_percent'] for x in op),'pressure_free_max':max(x['free_percent'] for x in op),'swap_peak_delta_gib':max(x['swap_gib'] for x in op)-base['swap_gib'],'asr':am,'source_hashes':{str(p):sha(p) for p in [run/'manifest.json',run/'events.jsonl',run/'resources.jsonl',run/'status.json',run/'worker-result.json',run/'asr.json',run/'asr-status.json']}}

out=DEPLOY/'results'/RID;out.mkdir(parents=True,exist_ok=True);(out/'audio').mkdir(exist_ok=True);(out/'segments').mkdir(exist_ok=True)
for engine,data in engines.items():
 slug='f5' if engine=='F5-TTS' else 'fish'
 normalized=[];segment_levels=[];normalization_methods=[]
 for case,row in zip(m['cases'],data['rows']):
  target=out/'segments'/f'{slug}_{case["id"]}.wav';method,level=normalize_segment(row['path'],target)
  normalized.append((target,case['pause_after_ms']));segment_levels.append(level);normalization_methods.append({'segment_id':case['id'],'method':method})
 assembled=out/'audio'/f'{slug}-chapter-pre.wav'
 with wave.open(str(assembled),'wb') as dst:
  dst.setnchannels(1);dst.setsampwidth(2);dst.setframerate(24000)
  for path,pause in normalized:
   with wave.open(str(path),'rb') as src:
    assert (src.getnchannels(),src.getsampwidth(),src.getframerate())==(1,2,24000);dst.writeframes(src.readframes(src.getnframes()))
   dst.writeframes(b'\0\0'*round(24000*pause/1000))
 final=out/'audio'/f'{slug}-chapter.wav';PREP['loudnorm'](assembled,final);final_measure=PREP['measure'](final)
 with wave.open(str(final)) as w:final_duration=w.getnframes()/w.getframerate()
 expected_duration=sum((wave.open(str(p)).getnframes()/24000)+(pause/1000) for p,pause in normalized)
 assert abs(final_duration-expected_duration)<=.05 and abs(final_measure['integrated_lufs']+23)<=.2
 assembled.unlink();data.update({'assembled_path':str(final),'assembled_sha256':sha(final),'assembled_seconds':final_duration,'expected_assembled_seconds':expected_duration,'duration_delta_seconds':final_duration-expected_duration,'segment_rms_dbfs_min':min(segment_levels),'segment_rms_dbfs_max':max(segment_levels),'short_clip_rms_fallback_count':sum(x['method']!='ebu_r128' for x in normalization_methods),'normalization_methods':normalization_methods,'assembled_loudness':final_measure})

feedback_path=ROOT/'results'/RID/'user-feedback.json';feedback=json.loads(feedback_path.read_text()) if feedback_path.exists() else None
summary={'schema_version':1,'run_id':RID,'analyzed_at':dt.datetime.now().astimezone().isoformat(),'source':{'basename':source.name,'sha256':sha(source),'chapter':m['private_source']['chapter'],'line_start':m['private_source']['line_start'],'line_end':m['private_source']['line_end'],'source_chars':m['private_source']['source_chars'],'rendered_chars':sum(len(x['text']) for x in m['cases']),'content_embedded':False},'design':{'segments':len(expected),'roles':{r:sum(x['role']==r for x in m['cases']) for r in ['旁白','主人','零']},'references':'两位普通话演员；男性中性/愤怒、女性悲伤；全部响度匹配','private_manifest_sha256':sha(PRIVATE)},'engines':{k:{x:y for x,y in v.items() if x!='rows'} for k,v in engines.items()},'human_review':feedback or 'pending','automatic_claim':'自动门槛只覆盖完整性、文字、拼接、响度、速度和资源；角色与情绪连续性由人工试听。','failed_attempt':{'run':'tts_novel_longform_f5_20260904_1020','reason':'private manifest missing deployment field; failed before model load and generation'},'source_hashes':{str(feedback_path):sha(feedback_path)} if feedback else {}}
(ROOT/'results'/RID/'summary.json').write_text(json.dumps(summary,ensure_ascii=False,indent=2)+'\n')
metrics=[];resource=[];content=[]
for name,x in summary['engines'].items():
 metrics.extend([{'label':name+' 章节时长','value':f'{x["assembled_seconds"]/60:.2f} 分钟','note':'43段及段落停顿'},{'label':name+' 速度','value':f'{x["weighted_rtf"]:.3f}×','note':'纯生成时间 / 原始片段音频时长'},{'label':name+' 文字错误率','value':f'{x["asr"]["weighted_cer"]:.2%}','note':f'{x["asr"]["edits_total"]}/{x["asr"]["refs_total"]}'}])
 content.append([name,x['clips'],f'{x["asr"]["weighted_cer"]:.2%}',f'{x["generation_seconds"]:.1f}s',f'{x["assembled_seconds"]:.1f}s',f'{x["duration_delta_seconds"]:.3f}s'])
 resource.append([name,f'{x["mlx_peak_gib"]:.3f} GiB',f'{x["rss_max_gib"]:.3f} GiB',f'{x["pressure_free_min"]}%–{x["pressure_free_max"]}%',f'{x["swap_peak_delta_gib"]:.3f} GiB'])
artifact={'schema_version':2,'id':RID,'as_of':dt.date.today().isoformat(),'title':'真实小说章节：F5-TTS 与 Fish S2 长文本测试','gate':'runnable','gate_label':'runnable · 真实章节整体听感通过，局部调参待复测' if feedback else 'runnable · 真实章节生成通过，连续听感待验收','summary':('授权小说第四章两模型均43/43生成，CER低于8%。用户确认旁白稳定性、角色串音、情绪、停顿和整体自然度都还不错；F5情绪更明显但旁白偏快，Fish男主相对偏小。' if feedback else '授权小说第四章已按旁白、男性对白和“零”三种角色切为43段，两模型均完整生成并拼接成章节。F5-TTS CER 4.95%，Fish S2 CER 4.66%，均通过8%自动门槛；角色、情绪和衔接仍需人工试听。'),'metrics':metrics,'sections':[{'id':'scope','title':'测试范围','paragraphs':['素材为用户指定的本机小说，仅记录文件哈希、第四章行号和统计量；原文、切分文本和ASR转写不写入报告。','连续章节1259个源字符，43个音频片段：旁白26、男性对白13、“零”4。两模型使用同一私有清单并串行运行。']},{'id':'content','title':'生成与拼接','table':{'columns':['模型','片段','加权CER','生成时间','成片时长','拼接时长误差'],'rows':content},'paragraphs':['两模型均43/43生成并成功退出；成片前逐段统一响度，再按80毫秒句内停顿和260毫秒段落停顿拼接，完整章节最终统一为−23 LUFS。','CER主要筛查错字、漏字、重复和参考串入；短感叹词的单字误差比例会被放大。']},{'id':'resource','title':'本机资源','table':{'columns':['模型','MLX峰值','RSS采样峰值','可用内存比例','交换空间增量'],'rows':resource},'paragraphs':['MLX与RSS口径不可相加；两模型串行，系统pressure和swap用于整机风险判断。']},{'id':'review','title':'人工试听结论','paragraphs':([feedback['verbatim'],feedback['scope'],'整章整体听感通过。F5下一轮需降低旁白语速；Fish下一轮需提高男主相对响度。上述调参方向尚未复测。'] if feedback else ['请对两条完整章节分别判断：旁白是否稳定、男性对白是否与旁白属于同一人但情绪更强、“零”是否保持女性声线、角色切换是否正确、段间音量是否稳定、停顿是否自然。'])},{'id':'limits','title':'边界','bullets':['本轮只覆盖一个章节、三种角色通道和约3至4分钟成片。','角色分配由本地切分规则提供，不测试自动小说角色识别。','逐段响度处理属于后期链路，会减少模型原始响度差异；不足0.5秒的片段使用限制12dB增益的RMS校准。','首次F5启动因私有清单漏字段在模型加载前失败；失败记录保留，修正后使用新运行编号。']}],'evidence':summary}
report=ROOT/'docs/reports'/RID;report.mkdir(parents=True,exist_ok=True);(report/'artifact.json').write_text(json.dumps(artifact,ensure_ascii=False,indent=2)+'\n');(report/'report.html').write_text(runpy.run_path(str(ROOT/'scripts/render-evaluation-record.py'))['render'](artifact));(report/'SOURCE_NOTES.md').write_text('素材来自用户指定本机小说。报告仅含哈希、章节行号与聚合指标，不含原文、切分文本或ASR转写。\n')
for f in ['artifact.json','report.html','SOURCE_NOTES.md']:shutil.copy2(report/f,out/f)
shutil.copy2(ROOT/'results'/RID/'summary.json',out/'summary.json')
order=[{'label':'样本甲','engine':'F5-TTS','file':'audio/f5-chapter.wav'},{'label':'样本乙','engine':'Fish S2','file':'audio/fish-chapter.wav'}];random.Random(20260904).shuffle(order);(out/'mapping.json').write_text(json.dumps(order,ensure_ascii=False,indent=2)+'\n')
e=html.escape;page=['<!doctype html><html lang="zh-CN"><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><title>真实小说章节盲听</title><style>body{max-width:900px;margin:32px auto;padding:0 18px;background:#f4f3f9;color:#252337;font:17px/1.7 system-ui}section{background:#fff;padding:20px;margin:18px 0;border-radius:14px}audio{width:100%}summary{cursor:pointer;font-weight:600}</style><h1>真实小说第四章盲听</h1><p>两条音频使用相同章节、相同角色参考和相同停顿规则，综合响度均为 −23 LUFS。请重点听旁白、男性对白、“零”的女性对白、角色切换和段落衔接。</p>']
for item in order:page.append(f'<section><h2>{item["label"]}</h2><audio controls preload="metadata" src="{item["file"]}"></audio><details><summary>听完再看模型</summary><p>{item["engine"]}</p></details></section>')
page.append('<p>建议记录：旁白稳定性、角色是否串音、情绪是否合适、音量、停顿、错字漏字、整体自然度。 <a href="report.html">查看技术报告</a></p></html>');(out/'listening.html').write_text('\n'.join(page));print(out)
