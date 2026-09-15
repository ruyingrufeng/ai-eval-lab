#!/usr/bin/env python3
"""Separate, bounded local ASR phase after the persistent Fish worker exits."""
import argparse
import datetime as dt
import json
import os
from pathlib import Path
import signal
import subprocess
import sys
import time

ROOT=Path(__file__).resolve().parents[1]
DEPLOY=Path('/Users/jacky/Documents/Codex/2026-09-03/referenced-chatgpt-conversation-this-is-an/outputs/fish-s2-local')

def write(path,obj):
    tmp=path.with_suffix('.tmp');tmp.write_text(json.dumps(obj,ensure_ascii=False,indent=2)+'\n');os.replace(tmp,path)

def worker(run):
    import mlx.core as mx
    import mlx_speech
    mx.set_cache_limit(256*1024**2);mx.set_memory_limit(8*1024**3)
    rows=[json.loads(l) for l in (run/'generation.jsonl').read_text().splitlines() if json.loads(l).get('event')=='generated']
    model=mlx_speech.asr.load(str(DEPLOY/'models/qwen3-asr-int8'))
    results=[]
    for r in rows:
        write(run/'asr-current.json',{'name':r['name'],'monotonic':time.monotonic()})
        t=time.monotonic();text=model.generate(r['output'],language='Chinese',max_new_tokens=256).text
        results.append({'name':r['name'],'expected':r['text'],'transcript':text,'asr_seconds':time.monotonic()-t})
        write(run/'asr.json',results)
    write(run/'asr-current.json',{'name':None})

def run_asr(run):
    import runpy
    sample=runpy.run_path(str(ROOT/'scripts/fish-s2-persistent.py'))['sample']
    state=json.loads((run/'status.json').read_text())
    if state['state']!='fish_done' or (run/'asr.json').exists():
        raise RuntimeError('Fish must have exited successfully; no overwrite of ASR attempts')
    baseline=sample();proc=None;start=time.monotonic();low=0;max_seconds=1200
    try:
        handle=(run/'asr-console.log').open('w')
        proc=subprocess.Popen([sys.executable,__file__,run.name,'--worker'],stdout=handle,stderr=subprocess.STDOUT,start_new_session=True)
        while proc.poll() is None:
            snap=sample()
            with (run/'asr-resources.jsonl').open('a') as f:f.write(json.dumps(snap)+'\n')
            low=low+1 if snap['memory_pressure_free_percent']<10 else 0
            if low>=3 or snap['swap_used_gib']-baseline['swap_used_gib']>2 or any(v not in ('sleeping','unloaded') for v in snap['models'].values()):
                raise RuntimeError('ASR resource or external load stop')
            if time.monotonic()-start>max_seconds:raise TimeoutError('ASR batch timeout')
            current=json.loads((run/'asr-current.json').read_text()) if (run/'asr-current.json').exists() else {}
            if current.get('name') and time.monotonic()-current['monotonic']>120:raise TimeoutError('ASR clip timeout')
            time.sleep(2)
        if proc.returncode!=0:raise RuntimeError('ASR worker failed')
        write(run/'asr-status.json',{'state':'done','exit_code':0,'seconds':time.monotonic()-start,'time':dt.datetime.now().astimezone().isoformat()})
    except BaseException as exc:
        if proc and proc.poll() is None:
            os.killpg(proc.pid,signal.SIGTERM)
            try:proc.wait(timeout=15)
            except subprocess.TimeoutExpired:os.killpg(proc.pid,signal.SIGKILL);proc.wait()
        write(run/'asr-status.json',{'state':'failed','error':repr(exc),'exit_code':proc.returncode if proc else None})
        raise

if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('run_id');p.add_argument('--worker',action='store_true');a=p.parse_args()
    (worker if a.worker else run_asr)(ROOT/'results'/a.run_id)
