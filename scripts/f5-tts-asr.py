#!/usr/bin/env python3
"""Optional local ASR in the existing Fish environment, only after F5 exits."""
import argparse,json,os,signal,subprocess,sys,time,runpy
from pathlib import Path
FISH=Path('/Users/jacky/Documents/Codex/2026-09-03/referenced-chatgpt-conversation-this-is-an/outputs/fish-s2-local')
p=argparse.ArgumentParser();p.add_argument('run',type=Path);p.add_argument('--worker',action='store_true');p.add_argument('--runner',type=Path,required=True);a=p.parse_args();r=a.run.resolve()
helpers=runpy.run_path(str(a.runner));write=helpers['write'];sample=helpers['sample'];append=helpers['append']
if a.worker:
    import mlx.core as mx,mlx_speech
    mx.set_cache_limit(256*1024**2);mx.set_memory_limit(8*1024**3)
    model=mlx_speech.asr.load(str(FISH/'models/qwen3-asr-int8'))
    rows=[]
    for e in [json.loads(l) for l in (r/'events.jsonl').read_text().splitlines() if json.loads(l).get('event')=='generated']:
        start=time.monotonic();txt=model.generate(e['path'],language='Chinese',max_new_tokens=256).text
        rows.append({'name':e['id'],'expected':e['text'],'transcript':txt,'asr_seconds':time.monotonic()-start})
        write(r/'asr.json',rows)
    sys.exit(0)
if json.loads((r/'status.json').read_text())['state']!='runnable' or (r/'asr.json').exists():raise RuntimeError('Need completed F5 run with no prior ASR')
baseline=sample();proc=None
try:
    start=time.monotonic()
    with (r/'asr.log').open('w') as log:
        proc=subprocess.Popen([str(FISH/'.venv/bin/python'),__file__,str(r),'--worker','--runner',str(a.runner.resolve())],stdout=log,stderr=subprocess.STDOUT,start_new_session=True)
        while proc.poll() is None:
            s=sample(proc.pid);append(r/'asr-resources.jsonl',s)
            if s['swap_gib']-baseline['swap_gib']>2 or s['free_percent']<10 or any(v not in ('unloaded','sleeping') for v in s['models'].values()):raise RuntimeError('Resource stop')
            if time.monotonic()-start>300:raise RuntimeError('ASR timeout')
            time.sleep(2)
    rows=json.loads((r/'asr.json').read_text()) if (r/'asr.json').exists() else []
    expected=[e['id'] for e in json.loads((r/'manifest.json').read_text())['cases']]
    if proc.returncode or [e['name'] for e in rows]!=expected:raise RuntimeError('ASR incomplete')
    write(r/'asr-status.json',{'exit_code':0,'count':len(rows),'wall_seconds':time.monotonic()-start})
except BaseException as exc:
    if proc and proc.poll() is None:
        os.killpg(proc.pid,signal.SIGTERM)
        try:proc.wait(timeout=5)
        except subprocess.TimeoutExpired:os.killpg(proc.pid,signal.SIGKILL);proc.wait()
    write(r/'asr-status.json',{'error':repr(exc),'exit_code':proc.returncode if proc else None});raise
