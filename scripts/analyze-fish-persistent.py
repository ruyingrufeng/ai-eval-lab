#!/usr/bin/env python3
"""Analyze the persistent supplement with shared strict evidence gates."""
import argparse
import datetime as dt
import hashlib
import json
import re
from pathlib import Path
from fish_s2_evidence import audit, asr_metrics

ROOT=Path(__file__).resolve().parents[1]

def read_rows(path):
    return [json.loads(l) for l in path.read_text().splitlines()] if path.exists() else []

def quantile(x,q):
    if not x:return None
    x=sorted(x);p=(len(x)-1)*q;i=int(p);return x[i]+(x[min(i+1,len(x)-1)]-x[i])*(p-i)

def analyze(run):
    m=json.loads((run/'manifest.json').read_text());raw=read_rows(run/'generation.jsonl');events=read_rows(run/'events.jsonl')
    w=json.loads((run/'worker-result.json').read_text()) if (run/'worker-result.json').exists() else {}
    state=json.loads((run/'status.json').read_text())
    finished=[x for x in events if x.get('event')=='attempt_finished']
    starts=[x for x in events if x.get('event')=='attempt_started']
    lookup={x['case_id']:x for x in finished}
    generated=[]
    for x in raw:
        if x.get('event')!='generated':continue
        t=lookup.get(x['name'],{})
        generated.append(dict(x,case_id=x['name'],group=t.get('group'),output_path=x['output'],output_sha256=t.get('output_sha256'),exit_status='ok' if t.get('exit_code')==0 else 'fail'))
    filler_count=sum(x['group']=='FILL' for x in finished)
    scheduled=m['warmup']+m['emotions']+sum(m['anchors'].values(),[])+m['fillers'][:filler_count]
    expected=[x['case_id'] for x in scheduled]
    attempts=[dict(x,ok=x['exit_code']==0) for x in finished]
    errors=[]
    if [x['case_id'] for x in starts]!=[x['case_id'] for x in finished]:errors.append('attempt_start_finish_order_mismatch')
    if set(w.get('completed',[]))!=set(expected):errors.append('worker_manifest_mismatch')
    if state.get('state')!='fish_done' or state.get('exit_code')!=0:errors.append('supervisor_not_successful')
    final={'completed':len(w.get('completed',[])),'failed':0} if w.get('ok') else None
    integrity=audit(expected,attempts,generated,final,not w.get('ok'),errors)
    measure=[x for x in generated if x['group']!='WARMUP']
    seconds=sum(x['generation_seconds'] for x in measure);duration=sum(x['audio_seconds'] for x in measure)
    asr=json.loads((run/'asr.json').read_text()) if (run/'asr.json').exists() else []
    asrm=asr_metrics(asr);names=[x.get('name') for x in asr]
    asr_status=json.loads((run/'asr-status.json').read_text()) if (run/'asr-status.json').exists() else {}
    asr_complete=len(names)==len(set(names)) and set(names)==set(expected) and asr_status.get('exit_code')==0
    anchors={}
    for role in m['references']:
        values={pos:next((x for x in generated if x['case_id']==f'ANCHOR_{role}_{pos}'),{}) for pos in ['start','middle','end']}
        entry={pos+'_rtf':v.get('rtf') for pos,v in values.items()}
        if entry['start_rtf']:
            for pos in ['middle','end']:
                entry[pos+'_slowdown_ratio']=entry[pos+'_rtf']/entry['start_rtf']-1 if entry[pos+'_rtf'] else None
        anchors[role]=entry
    resources=read_rows(run/'resources.jsonl');baseline=json.loads((run/'baseline.json').read_text())
    def stats(k):
        vals=[x[k] for x in resources if isinstance(x.get(k),(int,float))]
        return {'min':min(vals),'max':max(vals),'samples':len(vals)} if vals else None
    load_count=sum(x.get('event')=='model_loaded' for x in raw);ref_count=sum(x.get('event')=='reference_encoded' for x in raw)
    operating=[x for x in resources if x.get('phase')=='fish']
    swap_delta=max(x['swap_used_gib'] for x in operating)-baseline['swap_used_gib']
    vm_rows=[]
    for snap in resources:
        text=snap.get('vm_stat','');match=re.search(r'page size of (\d+) bytes',text)
        page_size=int(match[1]) if match else None
        values={}
        for line in text.splitlines():
            pair=re.fullmatch(r'([^:]+):\s*(\d+)\.',line.strip())
            if pair:values[pair[1]]=int(pair[2])
        if page_size and 'Pages occupied by compressor' in values:
            vm_rows.append({'compressed_gib':values['Pages occupied by compressor']*page_size/1024**3,'pageouts':values.get('Pageouts'),'page_size':page_size})
    p95=quantile([x['rtf'] for x in measure],.95)
    def verdict(ok,description):return ('pass: ' if ok else 'FAIL: ')+description
    gates={'first_attempt_completion':verdict(integrity['pass'],f'{integrity["verified_audio_count"]}/{len(expected)} WAV bound to successful attempts'),
        'weighted_rtf':verdict(bool(duration) and seconds/duration<=3,f'observed {seconds/duration:.4f}; limit 3'),
        'per_clip_rtf_p95':verdict(p95 is not None and p95<=5,f'{p95} <= 5'),
        'persistent_30min':verdict(load_count==1 and ref_count==3 and seconds>=1800,'one model load, three reference encodings, >=1800 active seconds excluding warmup'),
        'swap_delta':verdict(swap_delta<=1,f'{swap_delta:.3f} GiB <= 1 GiB'),
        'asr_coverage':verdict(asr_complete,'one ASR result per generated clip and successful ASR worker exit'),
        'asr_weighted_cer':verdict(asrm['weighted_cer'] is not None and asrm['weighted_cer']<=.08,f'{asrm["weighted_cer"]} <= .08') if asr_complete else 'pending: ASR coverage incomplete',
        'human_review':'pending: new voices/emotions and content flags need human review'}
    for role,entry in anchors.items():
        ratio=entry.get('end_slowdown_ratio');gates['anchor_end_'+role]=verdict(ratio is not None and ratio<=.3,f'{ratio*100:+.1f}% <= 30%') if ratio is not None else 'pending: missing anchor'
    timestamps=[dt.datetime.fromisoformat(x['time']) for x in raw if x.get('time')]
    wall=(max(timestamps)-min(timestamps)).total_seconds() if timestamps else None
    summary={'schema_version':2,'run_id':run.name,'analyzed_at':dt.datetime.now().astimezone().isoformat(),'mode':m['mode'],'clip_count':len(generated),'failed_clip_count':len(expected)-integrity['verified_audio_count'],'integrity':integrity,'audio_seconds_total':duration,'generation_seconds_total':seconds,'weighted_rtf':seconds/duration if duration else None,'per_clip_rtf':{'p50':quantile([x['rtf'] for x in measure],.5),'p95':p95,'samples':len(measure)},'anchor_per_role_rtf':anchors,'fish_timing':{'pure_generation_seconds':seconds,'worker_wall_seconds':wall,'persistent_model_verified':load_count==1 and ref_count==3 and integrity['pass'],'method':f'One worker PID {w.get("pid")}; {load_count} model load; {ref_count} reference encodings; warmup excluded from speed/time thresholds'},'asr_weighted_cer':asrm['weighted_cer'],'asr_weighted_cer_numerator':asrm['edits_total'],'asr_weighted_cer_denominator':asrm['refs_total'],'asr_clip_count':len(asr),'asr_cleaning_method':'Strip control tags, NFKC, lowercase, remove punctuation/symbols/space; preserve homophones.','asr_per_clip':asrm['per_clip'],'acceptance_verdicts':gates,'resource_summary':{'memory_pressure_free_percent':stats('memory_pressure_free_percent'),'available_gib':stats('available_gib'),'wired_gib':stats('wired_gib'),'swap_used_gib':stats('swap_used_gib'),'swap_delta_from_baseline_gib':swap_delta,'mlx_peak_gib':max(x['mlx_peak_gib'] for x in generated),'baseline_models':baseline['last_sample']['models'],'external_models_all_idle':all(all(v in ('sleeping','unloaded') for v in x['models'].values()) for x in resources),'sample_count':len(resources)},'source_hashes':{str(p):hashlib.sha256(p.read_bytes()).hexdigest() for p in [run/'manifest.json',run/'events.jsonl',run/'generation.jsonl',run/'resources.jsonl',run/'asr.json',Path(__file__)] if p.exists()}}
    if vm_rows:
        summary['resource_summary']['compressed_gib']={'min':min(x['compressed_gib'] for x in vm_rows),'max':max(x['compressed_gib'] for x in vm_rows),'samples':len(vm_rows)}
        summary['resource_summary']['pageout_delta']=vm_rows[-1]['pageouts']-vm_rows[0]['pageouts'] if vm_rows[0]['pageouts'] is not None and vm_rows[-1]['pageouts'] is not None else None
    summary['resource_summary']['thermal_observation']='pmset raw observations saved; GPU temperature/frequency not measured, do not attribute slowdown to heat alone'
    summary['prior_infrastructure_attempt']={'run':'fish_s2_persistent_20260903_1853','outcome':'baseline sampler stopped before model load; transient missing process memory_info fixed; original failure retained'}
    for source in [ROOT/'scripts/fish_s2_evidence.py',ROOT/'scripts/fish-s2-persistent.py',ROOT/'scripts/fish-s2-asr-batch.py']:
        summary['source_hashes'][str(source)]=hashlib.sha256(source.read_bytes()).hexdigest()
    feedback_path = run/'user-feedback.json'
    if feedback_path.exists():
        feedback = json.loads(feedback_path.read_text())
        summary['human_feedback'] = feedback
        summary['source_hashes'][str(feedback_path)] = hashlib.sha256(feedback_path.read_bytes()).hexdigest()
        if any(item.get('dimension') == 'emotion_distinguishability' and item.get('verdict') == 'fail' for item in feedback.get('feedback', [])):
            gates['emotion_distinguishability'] = 'FAIL: 用户试听反馈同一音色缺乏可辨情绪变化；限本轮配置与所听样本'
            gates['human_review'] = 'partial: 情绪需求未通过；逐段声线、自然度与内容复核未完成'
    (run/'summary.json').write_text(json.dumps(summary,ensure_ascii=False,indent=2)+'\n')
    print(json.dumps({'run':run.name,'gates':gates},ensure_ascii=False,indent=2))
    return 0 if integrity['pass'] else 2

if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('run_id');a=p.parse_args();raise SystemExit(analyze(ROOT/'results'/a.run_id))
