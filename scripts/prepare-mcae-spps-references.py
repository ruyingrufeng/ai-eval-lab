#!/usr/bin/env python3
"""Download a minimal Mandarin emotional reference set and loudness-match it."""
import datetime as dt
import hashlib
import json
import re
import subprocess
import time
import urllib.parse
import urllib.request
from pathlib import Path

DEPLOY = Path('/Users/jacky/Documents/Codex/2026-09-03/referenced-chatgpt-conversation-this-is-an/outputs/f5-tts-local')
ASSET = DEPLOY / 'reference-assets/mcae-spps'
OUT = DEPLOY / 'references/mcae-spps-actor04'
FOLDERS = {
    'neutral': '692bcb2ef34fb73b1476fcf3',
    'happy': '692bc22893d9ae7a2c9571b1',
    'sad': '692bd42f8060f1a294b54a0e',
}
EMOTION_DIGIT = {'neutral': '1', 'happy': '2', 'sad': '5'}
CODES = ['005', '069', '017', '051', '024', '013']
TRANSCRIPTS = {
    '005': '我站在广场上', '069': '我们想听听', '017': '我来回答',
    '051': '我们有个计划', '024': '我是主持人', '013': '我回来了',
}
TARGET_LUFS = -23.0


def sha256(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def osf_file(folder, name):
    query = urllib.parse.urlencode({'filter[name]': name, 'page[size]': 10})
    url = f'https://api.osf.io/v2/nodes/9jyzc/files/osfstorage/{folder}/?{query}'
    with urllib.request.urlopen(url, timeout=60) as response:
        data = json.load(response)['data']
    if len(data) != 1 or data[0]['attributes']['name'] != name:
        raise RuntimeError(f'OSF lookup mismatch: {name}')
    return data[0]


def download(url, path, expected):
    if path.exists() and sha256(path) == expected:
        return
    temporary = path.with_suffix('.part')
    for attempt in range(5):
        try:
            with urllib.request.urlopen(url, timeout=120) as response, temporary.open('wb') as target:
                while block := response.read(1024 * 1024):
                    target.write(block)
            if sha256(temporary) != expected:
                raise RuntimeError(f'download hash mismatch: {path.name}')
            temporary.replace(path)
            return
        except Exception:
            if attempt == 4:
                raise
            time.sleep(2 ** attempt)


def loudnorm(source, target):
    common = ['ffmpeg', '-hide_banner', '-nostats', '-y', '-i', str(source), '-ar', '24000', '-ac', '1']
    first = subprocess.run(common + ['-af', f'loudnorm=I={TARGET_LUFS}:LRA=7:TP=-2:print_format=json', '-f', 'null', '-'], text=True, capture_output=True, check=True)
    match = re.findall(r'\{\s*"input_i".*?\}', first.stderr, re.S)
    if not match:
        raise RuntimeError('loudnorm first pass JSON missing')
    measured = json.loads(match[-1])
    filt = (f'loudnorm=I={TARGET_LUFS}:LRA=7:TP=-2:'
            f'measured_I={measured["input_i"]}:measured_LRA={measured["input_lra"]}:'
            f'measured_TP={measured["input_tp"]}:measured_thresh={measured["input_thresh"]}:'
            f'offset={measured["target_offset"]}:linear=true:print_format=json')
    second = subprocess.run(common + ['-af', filt, '-c:a', 'pcm_s16le', str(target)], text=True, capture_output=True, check=True)
    match2 = re.findall(r'\{\s*"input_i".*?\}', second.stderr, re.S)
    return {'first_pass': measured, 'second_pass': json.loads(match2[-1]) if match2 else None}


def measure(path):
    p = subprocess.run(['ffmpeg', '-hide_banner', '-nostats', '-i', str(path), '-filter_complex', 'ebur128=peak=true', '-f', 'null', '-'], text=True, capture_output=True, check=True)
    summary = p.stderr.rsplit('Summary:', 1)[-1]
    vals = re.findall(r'I:\s*(-?[\d.]+) LUFS.*?Peak:\s*(-?[\d.]+) dBFS', summary, re.S)
    if not vals:
        raise RuntimeError(f'EBU measurement missing: {path}')
    return {'integrated_lufs': float(vals[-1][0]), 'true_peak_dbfs': float(vals[-1][1])}


def main():
    original = ASSET / 'selected-originals'
    original.mkdir(parents=True, exist_ok=True)
    OUT.mkdir(parents=True, exist_ok=True)
    selection = {}
    for emotion, folder in FOLDERS.items():
        entries = []
        for code in CODES:
            name = f'4{EMOTION_DIGIT[emotion]}{code}.wav'
            item = osf_file(folder, name)
            path = original / name
            expected = item['attributes']['extra']['hashes']['sha256']
            download(item['links']['download'], path, expected)
            if sha256(path) != expected:
                raise RuntimeError(f'hash mismatch: {name}')
            entries.append({'name': name, 'sentence_code': code, 'text': TRANSCRIPTS[code], 'bytes': path.stat().st_size, 'sha256': expected, 'url': item['links']['download']})
        concat = ASSET / f'{emotion}-concat.txt'
        concat.write_text('\n'.join("file '" + str((original / x['name']).resolve()).replace("'", "'\\''") + "'" for x in entries) + '\n')
        joined = ASSET / f'{emotion}-joined.wav'
        subprocess.run(['ffmpeg', '-hide_banner', '-loglevel', 'error', '-y', '-f', 'concat', '-safe', '0', '-i', str(concat), '-c:a', 'pcm_s24le', str(joined)], check=True)
        target = OUT / f'{emotion}.wav'
        passes = loudnorm(joined, target)
        selection[emotion] = {'files': entries, 'derived_path': str(target), 'derived_sha256': sha256(target), 'measurement': measure(target), 'loudnorm': passes}
    reference_text = '。'.join(TRANSCRIPTS[c] for c in CODES) + '。'
    provenance = {
        'schema_version': 1, 'dataset': 'MCAE-SPPS', 'doi': '10.17605/OSF.IO/9JYZC',
        'source': 'https://osf.io/9jyzc', 'license': 'CC-BY-NC-4.0',
        'actor': '04（女性普通话演员）', 'sentence_codes': CODES,
        'reference_text': reference_text, 'processing': '同一演员、同一句序列；原始文件串接后双遍 EBU R128 响度匹配，24 kHz、单声道、PCM16。',
        'target_lufs': TARGET_LUFS, 'selection': selection,
        'created_at': dt.datetime.now().astimezone().isoformat(),
        'use': '仅用于本机非商业模型评测。',
    }
    (ASSET / 'provenance.json').write_text(json.dumps(provenance, ensure_ascii=False, indent=2) + '\n')
    (ASSET / 'ATTRIBUTION.md').write_text('# MCAE-SPPS 参考音频署名\n\n来源：MCAE-SPPS，DOI 10.17605/OSF.IO/9JYZC，CC BY-NC 4.0。仅用于本机非商业评测。派生参考经过串接、重采样和响度匹配。\n')
    print(json.dumps(provenance, ensure_ascii=False, indent=2))


if __name__ == '__main__':
    main()
