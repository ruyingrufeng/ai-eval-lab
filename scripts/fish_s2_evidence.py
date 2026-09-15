"""Fail-closed evidence checks shared by Fish analysis and regression fixtures."""
from array import array
from collections import Counter
import hashlib
import math
from pathlib import Path
import wave
import re
import unicodedata


def clean_text(s):
    s=re.sub(r'<\|[^>]+\|>|\[[^]]*\]', '', s or '')
    return ''.join(c.lower() for c in unicodedata.normalize('NFKC',s)
                   if not c.isspace() and not unicodedata.category(c).startswith(('P','S')))


def edit_distance(a,b):
    row=list(range(len(b)+1))
    for i,x in enumerate(a,1):
        new=[i]
        for j,y in enumerate(b,1):new.append(min(new[-1]+1,row[j]+1,row[j-1]+(x!=y)))
        row=new
    return row[-1]


def asr_metrics(rows):
    details=[]
    for r in rows:
        target, actual = clean_text(r.get('expected')),clean_text(r.get('transcript'))
        edits=edit_distance(target,actual);chars=len(target)
        ratio=len(actual)/chars if chars else None
        tail = len(target)>=10 and target[-10:] not in actual
        gt=Counter(target[i:i+8] for i in range(max(0,len(target)-7)))
        ga=Counter(actual[i:i+8] for i in range(max(0,len(actual)-7)))
        repeated=any(count>max(1,gt[gram]) for gram,count in ga.items())
        cer=edits/chars if chars else None
        flags=[]
        if cer is None or cer>.15:flags.append('cer')
        if ratio is None or not .85<=ratio<=1.15:flags.append('length_ratio')
        if tail:flags.append('tail_mismatch')
        if repeated:flags.append('unexpected_repetition')
        details.append({'name':r.get('name'),'ref_chars':chars,'edits':edits,'cer':cer,'length_ratio':ratio,'review_flags':flags})
    total_edits=sum(x['edits'] for x in details);total_chars=sum(x['ref_chars'] for x in details)
    return {'edits_total':total_edits,'refs_total':total_chars,'weighted_cer':total_edits/total_chars if total_chars else None,'per_clip':details}


def inspect_audio(path, expected_hash):
    errors = []
    p = Path(path)
    if not p.is_file():
        return {'ok': False, 'errors': ['missing_audio']}
    actual = hashlib.sha256(p.read_bytes()).hexdigest()
    if not expected_hash or actual != expected_hash:
        errors.append('missing_or_mismatched_hash')
    try:
        with wave.open(str(p), 'rb') as w:
            rate, channels, width, frames = w.getframerate(), w.getnchannels(), w.getsampwidth(), w.getnframes()
            pcm = w.readframes(frames)
        if rate != 44100 or channels != 1 or width != 2 or not frames or len(pcm) != frames*channels*width:
            errors.append('invalid_or_truncated_pcm')
        vals = array('h', pcm) if width == 2 else array('h')
        import sys
        if sys.byteorder != 'little':
            vals.byteswap()
        rms = math.sqrt(sum((x/32768)**2 for x in vals)/len(vals)) if vals else 0
        clipped = sum(x in (-32768,32767) for x in vals)/len(vals) if vals else 1
        if rms < 1e-5:
            errors.append('silent_audio')
        if clipped > .0001:
            errors.append('clipped_audio')
        return {'ok': not errors, 'errors': errors, 'sha256': actual, 'seconds': frames/rate, 'sample_rate': rate, 'rms': rms, 'clipped_fraction': clipped}
    except Exception as exc:
        return {'ok': False, 'errors': errors+['unreadable_audio:'+type(exc).__name__]}


def audit(expected_ids, attempts, generated, final, aborted=False, parse_errors=None):
    """Each scheduled ID needs exactly one successful exit and one valid WAV.
    A generated row alone never proves that its process finished successfully.
    """
    errors = list(parse_errors or [])
    expected = set(expected_ids)
    if not expected or len(expected) != len(expected_ids):
        errors.append('invalid_expected_set')
    if aborted:
        errors.append('aborted')
    if not final:
        errors.append('missing_final_event')
    ac = Counter(x.get('case_id') for x in attempts)
    gc = Counter(x.get('case_id') for x in generated)
    missing = sorted(expected-set(gc))
    unexpected = sorted(str(x) for x in (set(ac)|set(gc))-expected)
    if missing:
        errors.append('missing_generated_ids')
    if unexpected:
        errors.append('unexpected_ids')
    for cid in expected:
        if ac[cid] != 1 or gc[cid] != 1:
            errors.append('attempt_or_generation_count:'+cid)
    for x in attempts:
        if x.get('exit_code') != 0 or x.get('ok') is not True:
            errors.append('failed_or_unproven_exit:'+str(x.get('case_id')))
    if final and (final.get('completed') != len(expected) or final.get('failed') != 0):
        errors.append('final_count_mismatch')
    audio = {}
    for x in generated:
        cid = x.get('case_id')
        if x.get('exit_status') not in ('ok','success'):
            errors.append('failed_or_unproven_generated_status:'+str(cid))
        if x.get('hit_token_limit') is not False:
            errors.append('token_cap_or_unknown:'+str(cid))
        for field in ('generation_seconds','audio_seconds','rtf'):
            value = x.get(field)
            if not isinstance(value,(int,float)) or not math.isfinite(value) or value <= 0:
                errors.append('invalid_'+field+':'+str(cid))
        info = inspect_audio(x.get('output_path') or x.get('output') or '', x.get('output_sha256'))
        audio[cid] = info
        if not info['ok']:
            errors.append('invalid_audio:'+str(cid))
        if info.get('seconds') and isinstance(x.get('audio_seconds'),(int,float)) and abs(info['seconds']-x['audio_seconds']) > .01:
            errors.append('duration_mismatch:'+str(cid))
    return {'pass': not errors, 'errors': sorted(set(errors)), 'expected_count':len(expected), 'attempt_count':len(attempts), 'generated_count':len(generated), 'missing_ids':missing, 'unexpected_ids':unexpected, 'verified_audio_count':sum(x['ok'] for x in audio.values()), 'audio':audio}
