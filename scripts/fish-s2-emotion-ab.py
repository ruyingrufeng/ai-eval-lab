#!/usr/bin/env python3
"""Run the same independent emotional references through Fish S2 in one process."""
import argparse,datetime as dt,hashlib,json,os,signal,subprocess,sys,time,runpy
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1];DEPLOY=Path('/Users/jacky/Documents/Codex/2026-09-03/referenced-chatgpt-conversation-this-is-an/outputs/fish-s2-local')
def now():return dt.datetime.now().astimezone().isoformat()
def sha(p):return hashlib.sha256(Path(p).read_bytes()).hexdigest()
def write(p,x):
 t=p.with_suffix('.tmp');t.write_text(json.dumps(x,ensure_ascii=False,indent=2)+'\n');t.replace(p)
def append(p,x):
 with p.open('a') as f:f.write(json.dumps({'time':now(),**x},ensure_ascii=False)+'\n');f.flush()
def worker(manifest,out):
 m=json.loads(manifest.read_text());spec=__import__('importlib.util').util.spec_from_file_location('fish',DEPLOY/'scripts/tts.py');mod=__import__('importlib.util').util.module_from_spec(spec);spec.loader.exec_module(mod);runner=None;done=[]
 try:
  runner=mod.Runner(DEPLOY/'models/fish-s2-pro-int8',out/'generation.jsonl')
  for e,r in m['references'].items():assert sha(r['path'])==r['sha256'];runner.voice(e,Path(r['path']),r['text'])
  for c in m['cases']:
   write(out/'current-job.json',{'id':c['id'],'started':time.monotonic()});start=time.monotonic();target=out/'audio'/f'{c["id"]}.wav';runner.generate(c['id'],c['text'],target,seed=c['seed'],max_tokens=512,voice=c['voice']);seconds=time.monotonic()-start
   row=next(x for x in reversed([json.loads(l) for l in (out/'generation.jsonl').read_text().splitlines()]) if x.get('event')=='generated')
   if row['hit_token_limit'] or row['clipped_fraction']>.001:raise ValueError(c['id'])
   append(out/'events.jsonl',{'event':'generated',**c,'path':str(target),'sha256':sha(target),'duration_seconds':row['audio_seconds'],'generation_seconds':row['generation_seconds'],'wall_seconds':seconds,'rtf':row['rtf'],'mlx_peak_gib':row['mlx_peak_gib'],'rms':row['rms'],'clipped_fraction':row['clipped_fraction']});done.append(c['id'])
  write(out/'worker-result.json',{'ok':True,'completed':done})
 finally:
  if runner:runner.close()
def supervise(manifest,out):
 sample=runpy.run_path(str(ROOT/'scripts/f5-tts-local.py'))['sample'];m=json.loads(manifest.read_text());out.mkdir(exist_ok=False);(out/'audio').mkdir();write(out/'manifest.json',m);samples=[];proc=None;handle=None
 try:
  for _ in range(3):
   s=sample();append(out/'resources.jsonl',dict(s,phase='baseline'));samples.append(s)
   if any(v not in ('sleeping','unloaded') for v in s['models'].values()):raise RuntimeError('external LLM active')
   time.sleep(2)
  baseline=samples[-1];write(out/'baseline.json',baseline);handle=(out/'worker.log').open('w');proc=subprocess.Popen([sys.executable,__file__,'worker','--manifest',str(manifest),'--out',str(out)],stdout=handle,stderr=subprocess.STDOUT,start_new_session=True);start=time.monotonic()
  while proc.poll() is None:
   s=sample(proc.pid);append(out/'resources.jsonl',dict(s,phase='generation'))
   if s['free_percent']<10 or s['swap_gib']-baseline['swap_gib']>2 or any(v not in ('sleeping','unloaded') for v in s['models'].values()):raise RuntimeError('resource stop')
   if time.monotonic()-start>900:raise TimeoutError('batch timeout')
   cur=json.loads((out/'current-job.json').read_text()) if (out/'current-job.json').exists() else {}
   if cur.get('id') and time.monotonic()-cur['started']>180:raise TimeoutError('clip timeout')
   time.sleep(2)
  result=json.loads((out/'worker-result.json').read_text()) if (out/'worker-result.json').exists() else {}
  if proc.returncode or result.get('completed')!=[x['id'] for x in m['cases']]:raise RuntimeError('worker incomplete')
  write(out/'status.json',{'state':'runnable','exit_code':0,'human_review':'pending','time':now()})
 except BaseException as e:
  if proc and proc.poll() is None:
   os.killpg(proc.pid,signal.SIGTERM)
   try:proc.wait(5)
   except subprocess.TimeoutExpired:os.killpg(proc.pid,signal.SIGKILL);proc.wait()
  write(out/'status.json',{'state':'failed','error':repr(e),'exit_code':proc.returncode if proc else None});raise
 finally:
  if handle:handle.close()
if __name__=='__main__':
 p=argparse.ArgumentParser();p.add_argument('action',choices=['run','worker']);p.add_argument('--manifest',type=Path,required=True);p.add_argument('--out',type=Path,required=True);a=p.parse_args();(supervise if a.action=='run' else worker)(a.manifest.resolve(),a.out.resolve())
