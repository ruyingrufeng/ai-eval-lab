#!/usr/bin/env python3
"""Prepare Mandarin male narrator/dialogue references without novel content."""
import datetime as dt
import json
import runpy
import subprocess
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
BASE = runpy.run_path(str(ROOT / 'scripts/prepare-mcae-spps-references.py'))
DEPLOY = BASE['DEPLOY']
ASSET = DEPLOY / 'reference-assets/mcae-spps-actor01'
OUT = DEPLOY / 'references/mcae-spps-actor01'
CODES = BASE['CODES']
TRANSCRIPTS = BASE['TRANSCRIPTS']
FOLDERS = {'neutral': '692bcb2ef34fb73b1476fcf3', 'anger': '692be148ee5c3ab747957431'}
DIGITS = {'neutral': '1', 'anger': '3'}


def main():
    original = ASSET / 'selected-originals'; original.mkdir(parents=True, exist_ok=True); OUT.mkdir(parents=True, exist_ok=True)
    selection = {}
    for emotion, folder in FOLDERS.items():
        entries = []
        for code in CODES:
            name = f'1{DIGITS[emotion]}{code}.wav'
            item = BASE['osf_file'](folder, name); path = original / name
            expected = item['attributes']['extra']['hashes']['sha256']
            BASE['download'](item['links']['download'], path, expected)
            if BASE['sha256'](path) != expected: raise RuntimeError(name)
            entries.append({'name':name,'sentence_code':code,'bytes':path.stat().st_size,'sha256':expected,'url':item['links']['download']})
        concat = ASSET / f'{emotion}-concat.txt'
        concat.write_text('\n'.join("file '" + str((original/x['name']).resolve()).replace("'", "'\\''") + "'" for x in entries) + '\n')
        joined = ASSET / f'{emotion}-joined.wav'
        subprocess.run(['ffmpeg','-hide_banner','-loglevel','error','-y','-f','concat','-safe','0','-i',str(concat),'-c:a','pcm_s24le',str(joined)],check=True)
        target = OUT / f'{emotion}.wav'; passes = BASE['loudnorm'](joined,target); measured = BASE['measure'](target)
        if abs(measured['integrated_lufs'] + 23) > .15:
            corrected=OUT/f'{emotion}.corrected.wav';gain=-23-measured['integrated_lufs']
            subprocess.run(['ffmpeg','-hide_banner','-loglevel','error','-y','-i',str(target),'-af',f'volume={gain}dB','-c:a','pcm_s16le',str(corrected)],check=True);corrected.replace(target);measured=BASE['measure'](target)
        if abs(measured['integrated_lufs'] + 23) > .15: raise RuntimeError(measured)
        selection[emotion]={'files':entries,'derived_path':str(target),'derived_sha256':BASE['sha256'](target),'measurement':measured,'loudnorm':passes}
    data={'schema_version':1,'dataset':'MCAE-SPPS','source':'https://osf.io/9jyzc','license':'CC-BY-NC-4.0','actor':'01（男性普通话演员）','reference_text':'。'.join(TRANSCRIPTS[c] for c in CODES)+'。','processing':'同句序列串接；双遍 EBU R128 到 -23 LUFS；24 kHz 单声道 PCM16。','selection':selection,'created_at':dt.datetime.now().astimezone().isoformat()}
    (ASSET/'provenance.json').write_text(json.dumps(data,ensure_ascii=False,indent=2)+'\n');print(json.dumps(data,ensure_ascii=False,indent=2))


if __name__ == '__main__': main()
