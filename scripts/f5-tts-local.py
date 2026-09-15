#!/usr/bin/env python3
"""Offline, pinned F5 MLX runner; one model load per manifest, bounded supervisor."""
import argparse,datetime as dt,hashlib,json,os,re,signal,subprocess,sys,time,urllib.request
from pathlib import Path

def now(): return dt.datetime.now().astimezone().isoformat()
def sha(p):
    with Path(p).open('rb') as f:return hashlib.file_digest(f,'sha256').hexdigest()
def write(p,data):
    tmp=p.with_suffix('.tmp');tmp.write_text(json.dumps(data,ensure_ascii=False,indent=2)+'\n');tmp.replace(p)
def append(p,data):
    with p.open('a') as f:f.write(json.dumps({'time':now(),**data},ensure_ascii=False)+'\n');f.flush()

def sample(pid=None):
    import psutil
    v=psutil.virtual_memory();s=psutil.swap_memory()
    raw=subprocess.check_output(['memory_pressure','-Q'],text=True,timeout=4)
    pct=re.search(r'free percentage:\s*(\d+)%',raw)
    if not pct:raise ValueError('missing pressure sample')
    with urllib.request.urlopen('http://127.0.0.1:8086/models',timeout=3) as resp:
        states={m['id']:m['status']['value'] for m in json.load(resp)['data']}
    rss=None
    if pid:
        try:rss=psutil.Process(pid).memory_info().rss/1024**3
        except psutil.NoSuchProcess:pass
    return {'time':now(),'monotonic':time.monotonic(),'free_percent':int(pct[1]),'available_gib':v.available/1024**3,'wired_gib':v.wired/1024**3,'swap_gib':s.used/1024**3,'rss_gib':rss,'models':states,'pressure_raw':raw,'vm_stat':subprocess.check_output(['vm_stat'],text=True,timeout=4)}

def worker(manifest,out):
    os.environ['HF_HUB_OFFLINE']='1'
    os.environ['HF_HUB_DISABLE_TELEMETRY']='1'
    import mlx.core as mx,numpy as np,soundfile as sf
    import f5_tts_mlx.cfm as cfm
    from vocos_mlx import Vocos
    from f5_tts_mlx.utils import convert_char_to_pinyin
    m=json.loads(manifest.read_text());home=Path(m['deployment'])
    lock=json.loads((home/'model-lock.json').read_text())
    for key,spec in lock['models'].items():
        for f in spec['files']:
            assert sha(home/'models'/key/f['file'])==f['sha256'],f['file']
    for r in m['references'].values():assert sha(r['path'])==r['sha256']
    mx.set_default_device(mx.gpu);mx.set_cache_limit(256*1024**2);mx.set_memory_limit(12*1024**3)
    # Only replace hardcoded remote locators during loading; model math is unmodified.
    fetch,vc=cfm.fetch_from_hub,cfm.Vocos
    class LocalVocos:
        @classmethod
        def from_pretrained(cls,unused):return Vocos.from_pretrained(str(home/'models/vocos'))
    cfm.fetch_from_hub=lambda *a,**kw:home/'models/f5';cfm.Vocos=LocalVocos
    start=time.perf_counter()
    try:model=cfm.F5TTS.from_pretrained('local-pinned')
    finally:cfm.fetch_from_hub,cfm.Vocos=fetch,vc
    mx.eval(model.parameters())
    append(out/'events.jsonl',{'event':'model_loaded','seconds':time.perf_counter()-start,'device':str(mx.default_device()),'mlx_active_gib':mx.get_active_memory()/1024**3,'pid':os.getpid()})
    refs={}
    for k,r in m['references'].items():
        a,sr=sf.read(r['path'],dtype='float32');assert sr==24000 and a.ndim==1 and 0<len(a)<=12*sr
        rms=float(np.sqrt(np.mean(a*a)));assert rms>.001
        if rms<.1:a=a*.1/rms
        refs[k]=mx.array(a)
    completed=[]
    for c in m['cases']:
        write(out/'current-job.json',{'id':c['id'],'started':time.monotonic()})
        ref=m['references'][c['voice']];a=refs[c['voice']];text=c['text']
        # Explicit Chinese-aware duration heuristic, not learned duration predictor.
        def textlen(t):return len(t.encode('utf8'))+3*len(re.findall(r'。，、；：？！',t))
        frames=len(a)//256+int((len(a)//256)*textlen(text)/textlen(ref['text'])/c.get('speed',1))
        if not 0<frames*256/24000<=30:raise ValueError('Reference plus generation exceeds 30 seconds')
        tokens=convert_char_to_pinyin([ref['text']+' '+text])
        mx.reset_peak_memory();start=time.perf_counter()
        wave,trajectory=model.sample(a[None,:],text=tokens,duration=frames,steps=c.get('steps',32),method='euler',cfg_strength=2.,sway_sampling_coef=-1.,seed=c['seed'])
        wave=wave[len(a):];mx.eval(wave);seconds=time.perf_counter()-start
        pcm=np.asarray(wave,dtype=np.float32)
        if not len(pcm) or not np.isfinite(pcm).all():raise ValueError('Invalid audio')
        path=out/'audio'/f'{c["id"]}.wav';sf.write(path,pcm,24000,subtype='PCM_16')
        saved,sr=sf.read(path,dtype='float32');duration=len(saved)/sr
        row={**c,'event':'generated','path':str(path),'sha256':sha(path),'duration_seconds':duration,'generation_seconds':seconds,'rtf':seconds/duration,'mlx_peak_gib':mx.get_peak_memory()/1024**3,'rms':float(np.sqrt(np.mean(saved*saved))),'clipped_fraction':float(np.mean(np.abs(saved)>=.9999)),'peak':float(np.max(np.abs(saved))),'total_duration_frames':frames}
        append(out/'events.jsonl',row);completed.append(c['id']);print(json.dumps(row,ensure_ascii=False),flush=True)
        del trajectory,wave;mx.clear_cache()
        if row['rms']<.001 or row['clipped_fraction']>.001:raise ValueError('Silence or clipping')
    write(out/'worker-result.json',{'ok':True,'completed':completed,'time':now()})

def run(manifest,out):
    out.mkdir(parents=True,exist_ok=False);(out/'audio').mkdir()
    m=json.loads(manifest.read_text());write(out/'manifest.json',m)
    write(out/'runner-source.json',{'path':str(Path(__file__).resolve()),'sha256':sha(__file__)})
    proc=None;console=None;start=time.monotonic();baseline=None;miss=0;low=0
    try:
        for _ in range(3):
            s=sample();append(out/'resources.jsonl',dict(s,phase='baseline'))
            if any(v not in ('sleeping','unloaded') for v in s['models'].values()):raise RuntimeError('External LLM active; leave it untouched')
            baseline=s;time.sleep(2)
        write(out/'baseline.json',baseline)
        console=(out/'worker.log').open('w')
        proc=subprocess.Popen([sys.executable,__file__,'worker','--manifest',str(manifest),'--out',str(out)],stdout=console,stderr=subprocess.STDOUT,start_new_session=True)
        write(out/'status.json',{'state':'running','pid':proc.pid,'time':now()})
        while proc.poll() is None:
            try:s=sample(proc.pid);append(out/'resources.jsonl',dict(s,phase='generation'));miss=0
            except Exception as exc:
                append(out/'monitor-errors.jsonl',{'error':repr(exc)});miss+=1
                if miss>=3:raise RuntimeError('Three resource sampling failures')
                time.sleep(2);continue
            low=low+1 if s['free_percent']<10 else 0
            if low>=3 or s['swap_gib']-baseline['swap_gib']>2:raise RuntimeError('Memory stop')
            if any(v not in ('sleeping','unloaded') for v in s['models'].values()):raise RuntimeError('External LLM became active')
            job=out/'current-job.json'
            if job.exists() and time.monotonic()-json.loads(job.read_text())['started']>240:raise RuntimeError('Clip timeout')
            if time.monotonic()-start>1800:raise RuntimeError('Run timeout')
            time.sleep(2)
        result=json.loads((out/'worker-result.json').read_text()) if (out/'worker-result.json').exists() else {}
        if proc.returncode!=0 or result.get('completed')!=[c['id'] for c in m['cases']]:raise RuntimeError(f'Worker failed: exit {proc.returncode}')
        write(out/'status.json',{'state':'runnable','exit_code':proc.returncode,'time':now(),'human_review':'pending'})
    except BaseException as exc:
        if proc and proc.poll() is None:
            os.killpg(proc.pid,signal.SIGTERM)
            try:proc.wait(timeout=5)
            except subprocess.TimeoutExpired:os.killpg(proc.pid,signal.SIGKILL);proc.wait()
        write(out/'status.json',{'state':'failed','error':repr(exc),'exit_code':proc.returncode if proc else None,'time':now()});raise
    finally:
        if console:console.close()

if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('action',choices=['run','worker']);p.add_argument('--manifest',type=Path,required=True);p.add_argument('--out',type=Path,required=True);a=p.parse_args()
    (run if a.action=='run' else worker)(a.manifest.resolve(),a.out.resolve())
