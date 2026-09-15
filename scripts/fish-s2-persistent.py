#!/usr/bin/env python3
"""Bounded persistent Fish supplement. Supervisor never imports MLX.
Use DEPLOY/.venv/bin/python scripts/fish-s2-persistent.py prepare|run RUN_ID.
run supervises one model process, then exits; ASR is a separate later phase.
"""
import argparse
import datetime as dt
import hashlib
import importlib.util
import json
import os
from pathlib import Path
import signal
import subprocess
import sys
import time
import urllib.request

ROOT = Path(__file__).resolve().parents[1]
DEPLOY = Path('/Users/jacky/Documents/Codex/2026-09-03/referenced-chatgpt-conversation-this-is-an/outputs/fish-s2-local')
PRIOR = ROOT / 'results/fish_s2_followup_20260903_142148'


def now():
    return dt.datetime.now().astimezone().isoformat()


def sha(p):
    return hashlib.sha256(Path(p).read_bytes()).hexdigest()


def write(p, obj):
    p.parent.mkdir(parents=True, exist_ok=True)
    tmp = p.with_suffix('.tmp')
    with tmp.open('w') as f:
        json.dump(obj, f, ensure_ascii=False, indent=2)
        f.flush()
        os.fsync(f.fileno())
    os.replace(tmp, p)


def append(p, obj):
    with p.open('a') as f:
        f.write(json.dumps({'time': now(), **obj}, ensure_ascii=False) + '\n')
        f.flush()
        os.fsync(f.fileno())


def prepare(rid):
    import yaml
    import shutil
    r = ROOT / 'results' / rid
    r.mkdir(parents=True, exist_ok=False)
    assets = DEPLOY / 'experiments' / rid
    (assets / 'audio').mkdir(parents=True, exist_ok=False)
    m = yaml.safe_load((PRIOR / 'config/test-matrix.yaml').read_text())
    refs = {}
    for c in m['cases']['T3']['clips']:
        role = c['role_id']
        if role not in refs:
            source = Path(c['reference_audio'])
            target = assets / source.name
            shutil.copy2(source, target)
            refs[role] = {'path': str(target), 'text': c['reference_text'], 'sha256': sha(target)}
    def convert(c, cid, group):
        return {'case_id': cid, 'group': group, 'text': c['text'], 'seed': c['seed'], 'voice': c['role_id'], 'max_new_tokens': 512}
    anchors = {pos: [convert(c, f'ANCHOR_{c["role_id"]}_{pos}', 'ANCHOR') for c in m['cases']['T4']['clips'] if c['position_in_run'] == pos] for pos in ('start', 'middle', 'end')}
    warmup = [dict(c, case_id='WARMUP_'+c['voice'], group='WARMUP') for c in anchors['start']]
    emotions = [convert(c, c['case_id'], 'T3') for c in m['cases']['T3']['clips']]
    chapter = m['cases']['T1']['clips']
    fillers = [convert(chapter[i % len(chapter)], f'FILL_{i+1:03d}', 'FILL') for i in range(90)]
    for c in warmup+emotions+fillers+sum(anchors.values(), []):
        c['input_hash'] = hashlib.sha256(c['text'].encode()).hexdigest()
    manifest = {'run_id': rid, 'mode': 'persistent_supplement', 'created_at': now(), 'assets': str(assets), 'references': refs, 'warmup': warmup, 'anchors': anchors, 'emotions': emotions, 'fillers': fillers, 'policy': {'active_generation_seconds': 1800, 'midpoint_active_seconds': 900, 'max_tasks': 120, 'max_wall_seconds': 5400, 'single_job_timeout_seconds': 180, 'baseline_seconds': 60, 'sample_seconds': 2, 'swap_abort_delta_gib': 2, 'swap_growth_60s_gib': 1, 'memory_free_stop_percent': 10}, 'source_tts_sha256': sha(DEPLOY/'scripts/tts.py'), 'model_lock': json.loads((DEPLOY/'model-lock.json').read_text())}
    write(r/'manifest.json', manifest)
    write(r/'status.json', {'state': 'prepared', 'run_id': rid, 'time': now()})
    print(r)


def worker(r):
    m = json.loads((r/'manifest.json').read_text())
    if sha(DEPLOY/'scripts/tts.py') != m['source_tts_sha256']:
        raise ValueError('TTS source changed since preparation')
    for ref in m['references'].values():
        if sha(ref['path']) != ref['sha256']:
            raise ValueError('Reference hash mismatch')
    spec = importlib.util.spec_from_file_location('fish_deployed', DEPLOY/'scripts/tts.py')
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    runner = None
    active = 0.0
    completed = []
    log = r/'generation.jsonl'
    def job(c):
        nonlocal active
        output = Path(m['assets'])/'audio'/f'{c["case_id"]}.wav'
        write(r/'current-job.json', {'case_id': c['case_id'], 'start_monotonic': time.monotonic(), 'time': now()})
        append(r/'events.jsonl', {'event': 'attempt_started', **c})
        runner.generate(c['case_id'], c['text'], output, seed=c['seed'], max_tokens=c['max_new_tokens'], voice=c['voice'])
        generated = next(x for x in reversed([json.loads(l) for l in log.read_text().splitlines()]) if x.get('event') == 'generated')
        if generated['hit_token_limit'] or generated['clipped_fraction'] > .0001:
            raise ValueError('Token cap or clipping: '+c['case_id'])
        if c['group'] != 'WARMUP':
            active += generated['generation_seconds']
        completed.append(c['case_id'])
        append(r/'events.jsonl', {'event': 'attempt_finished', 'case_id': c['case_id'], 'group': c['group'], 'exit_code': 0, 'output': str(output), 'output_sha256': sha(output), 'generation_seconds': generated['generation_seconds'], 'active_seconds': active})
        write(r/'progress.json', {'completed': completed, 'active_seconds': active, 'time': now()})
        write(r/'current-job.json', {'case_id': None, 'time': now()})
    try:
        runner = mod.Runner(DEPLOY/'models/fish-s2-pro-int8', log)
        for role, ref in m['references'].items():
            runner.voice(role, Path(ref['path']), ref['text'])
        for c in m['warmup']+m['anchors']['start']+m['emotions']:
            job(c)
        middle = False
        for c in m['fillers']:
            if active >= m['policy']['midpoint_active_seconds'] and not middle:
                for anchor in m['anchors']['middle']:
                    job(anchor)
                middle = True
            if active >= m['policy']['active_generation_seconds']:
                break
            job(c)
        if not middle:
            for c in m['anchors']['middle']:
                job(c)
        for c in m['anchors']['end']:
            job(c)
        write(r/'worker-result.json', {'ok': True, 'completed': completed, 'active_seconds': active, 'insufficient_duration': active < 1800, 'pid': os.getpid(), 'time': now()})
    except BaseException as exc:
        import traceback
        append(r/'events.jsonl', {'event': 'worker_failed', 'error': repr(exc), 'traceback': traceback.format_exc()})
        write(r/'worker-result.json', {'ok': False, 'error': repr(exc), 'completed': completed, 'active_seconds': active, 'time': now()})
        raise
    finally:
        if runner:
            runner.close()


def sample():
    import psutil
    import re
    vm = psutil.virtual_memory()
    sw = psutil.swap_memory()
    mp = subprocess.check_output(['memory_pressure', '-Q'], text=True, timeout=4)
    pct = re.search(r'free percentage:\s*(\d+)%', mp)
    if not pct:
        raise ValueError('memory_pressure missing')
    with urllib.request.urlopen('http://127.0.0.1:8086/models', timeout=3) as resp:
        models = json.load(resp)['data']
    state = {x['id']: x['status']['value'] for x in models}
    vms = subprocess.check_output(['vm_stat'], text=True, timeout=3)
    processes = []
    for p in psutil.process_iter(['pid','name','memory_info','cpu_times']):
        try:
            info = p.info['memory_info']
            if info is None:
                continue
            rss = info.rss
            if rss > 1024**3:
                processes.append({'pid': p.pid, 'name': p.info['name'], 'rss_gib': rss/1024**3, 'cpu_user_seconds': p.info['cpu_times'].user if p.info['cpu_times'] else None})
        except (psutil.NoSuchProcess, psutil.AccessDenied):
            continue
    return {'time': now(), 'monotonic': time.monotonic(), 'memory_pressure_free_percent': int(pct[1]), 'memory_pressure_raw': mp, 'available_gib': vm.available/1024**3, 'wired_gib': vm.wired/1024**3, 'swap_used_gib': sw.used/1024**3, 'vm_stat': vms, 'models': state, 'large_rss_processes': processes, 'disk_free_gib': psutil.disk_usage(DEPLOY).free/1024**3}


def supervise(r):
    import psutil
    m = json.loads((r/'manifest.json').read_text())
    state = json.loads((r/'status.json').read_text())['state']
    if state != 'prepared':
        raise ValueError('Use a new run ID; no implicit rerun/overwrite')
    write(r/'status.json', {'state': 'baseline', 'time': now()})
    samples = []
    proc = None
    baseline = None
    start = time.monotonic()
    miss = low = 0
    last_thermal = 0
    try:
        while True:
            tick = time.monotonic()
            try:
                s = sample()
                s['phase'] = 'baseline' if proc is None else 'fish'
                if proc and proc.poll() is None:
                    s['worker_rss_gib'] = psutil.Process(proc.pid).memory_info().rss/1024**3
                if tick-last_thermal >= 30:
                    s['thermal'] = subprocess.run(['pmset','-g','therm'],capture_output=True,text=True,timeout=3).stdout
                    last_thermal = tick
                append(r/'resources.jsonl', s)
                samples.append(s)
                miss = 0
            except Exception as exc:
                append(r/'sampling-errors.jsonl', {'error': repr(exc)})
                miss += 1
                if miss >= 3:
                    raise RuntimeError('resource_sampling_failed')
                time.sleep(2)
                continue
            if any(v not in ('sleeping', 'unloaded') for v in s['models'].values()):
                raise RuntimeError('external_model_loaded')
            low = low+1 if s['memory_pressure_free_percent'] < 10 else 0
            if low >= 3 or s['disk_free_gib'] < 20:
                raise RuntimeError('resource_stop')
            if baseline is not None and s['swap_used_gib']-baseline > 2:
                raise RuntimeError('swap_delta_stop')
            recent = [x['swap_used_gib'] for x in samples if tick-x['monotonic'] <= 60]
            if s['swap_used_gib']-min(recent) > 1:
                raise RuntimeError('swap_growth_stop')
            if tick-start > 5400:
                raise RuntimeError('wall_timeout')
            if proc is None and tick-start >= 60:
                baseline = s['swap_used_gib']
                write(r/'baseline.json', {'swap_used_gib': baseline, 'samples': len(samples), 'last_sample': s})
                handle = (r/'worker-console.log').open('w')
                proc = subprocess.Popen([sys.executable, __file__, 'worker', r.name], stdout=handle, stderr=subprocess.STDOUT, start_new_session=True)
                write(r/'status.json', {'state': 'running', 'pid': proc.pid, 'supervisor_pid': os.getpid(), 'time': now()})
            elif proc is not None:
                code = proc.poll()
                if code is not None:
                    result = json.loads((r/'worker-result.json').read_text()) if (r/'worker-result.json').exists() else {}
                    if code != 0 or not result.get('ok'):
                        raise RuntimeError('worker_failed_exit_'+str(code))
                    write(r/'status.json', {'state': 'fish_done', 'exit_code': code, 'time': now(), 'supervisor_pid': os.getpid()})
                    return
                job = json.loads((r/'current-job.json').read_text()) if (r/'current-job.json').exists() else {}
                if job.get('case_id') and tick-job['start_monotonic'] > 180:
                    raise RuntimeError('single_job_timeout')
            write(r/'heartbeat.json', {'time': now(), 'phase': 'baseline' if proc is None else 'fish'})
            time.sleep(max(.1, 2-(time.monotonic()-tick)))
    except BaseException as exc:
        if proc and proc.poll() is None:
            os.killpg(proc.pid, signal.SIGTERM)
            try:
                proc.wait(timeout=15)
            except subprocess.TimeoutExpired:
                os.killpg(proc.pid, signal.SIGKILL)
                proc.wait()
        write(r/'status.json', {'state': 'failed', 'reason': repr(exc), 'time': now(), 'exit_code': proc.returncode if proc else None})
        raise


if __name__ == '__main__':
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('action', choices=['prepare','run','worker'])
    p.add_argument('run_id')
    a = p.parse_args()
    if '/' in a.run_id or '..' in a.run_id:
        p.error('Invalid run ID')
    if a.action == 'prepare':
        prepare(a.run_id)
    elif a.action == 'worker':
        worker(ROOT/'results'/a.run_id)
    else:
        supervise(ROOT/'results'/a.run_id)
