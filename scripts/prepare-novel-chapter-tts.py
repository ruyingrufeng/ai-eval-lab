#!/usr/bin/env python3
"""Create a private multi-role TTS manifest from one Markdown chapter."""
import argparse
import datetime as dt
import hashlib
import json
import re
from pathlib import Path

DEPLOY = Path('/Users/jacky/Documents/Codex/2026-09-03/referenced-chatgpt-conversation-this-is-an/outputs/f5-tts-local')


def sha(path): return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def main():
    ap=argparse.ArgumentParser();ap.add_argument('--source',type=Path,required=True);ap.add_argument('--chapter',required=True);ap.add_argument('--out',type=Path,required=True);ap.add_argument('--female-quote-indices',default='');ap.add_argument('--narrative-quote-indices',default='');a=ap.parse_args()
    source=a.source.resolve();text=source.read_text(encoding='utf-8');pattern=rf'(?ms)^## {re.escape(a.chapter)}\s*\n(.*?)(?=^---\s*$|^##\s+|\Z)';m=re.search(pattern,text)
    if not m: raise RuntimeError('chapter not found')
    chapter=m.group(1).strip();female={int(x) for x in a.female_quote_indices.split(',') if x};narrative={int(x) for x in a.narrative_quote_indices.split(',') if x}
    male=json.loads((DEPLOY/'reference-assets/mcae-spps-actor01/provenance.json').read_text());female_ref=json.loads((DEPLOY/'reference-assets/mcae-spps/provenance.json').read_text())
    refs={'narrator':{'path':male['selection']['neutral']['derived_path'],'sha256':male['selection']['neutral']['derived_sha256'],'text':male['reference_text']},'male_anger':{'path':male['selection']['anger']['derived_path'],'sha256':male['selection']['anger']['derived_sha256'],'text':male['reference_text']},'female_sad':{'path':female_ref['selection']['sad']['derived_path'],'sha256':female_ref['selection']['sad']['derived_sha256'],'text':female_ref['reference_text']}}
    for x in refs.values():
        if sha(x['path'])!=x['sha256']:raise RuntimeError('reference hash')
    pieces=[];quote_index=0
    paragraphs=[x.strip() for x in re.split(r'\n\s*\n',chapter) if x.strip()]
    for paragraph in paragraphs:
        cursor=0
        for q in re.finditer(r'“([^”]+)”',paragraph,re.S):
            before=paragraph[cursor:q.start()].strip()
            if before: pieces.append({'voice':'narrator','role':'旁白','text':before,'paragraph_end':False})
            content=q.group(1).strip()
            if quote_index in narrative: voice,role='narrator','旁白'
            elif quote_index in female: voice,role='female_sad','零'
            else: voice,role='male_anger','主人'
            pieces.append({'voice':voice,'role':role,'text':content,'paragraph_end':False,'quote_index':quote_index});quote_index+=1;cursor=q.end()
        rest=paragraph[cursor:].strip()
        if rest: pieces.append({'voice':'narrator','role':'旁白','text':rest,'paragraph_end':False})
        if pieces: pieces[-1]['paragraph_end']=True
    cases=[]
    for piece in pieces:
        clean=re.sub(r'\s+',' ',piece['text']).strip()
        if not clean: continue
        if cases and cases[-1]['voice']==piece['voice'] and len(cases[-1]['text'])+len(clean)<=110 and not cases[-1].get('paragraph_end'):
            cases[-1]['text']+='。'+clean;cases[-1]['paragraph_end']=piece['paragraph_end'];cases[-1]['pause_after_ms']=260 if piece['paragraph_end'] else 80
        else:
            cases.append({'id':f'segment_{len(cases)+1:03d}','voice':piece['voice'],'role':piece['role'],'text':clean,'seed':1000+len(cases)+1,'group':'novel_chapter','paragraph_end':piece['paragraph_end'],'pause_after_ms':260 if piece['paragraph_end'] else 80})
    payload={'schema_version':2,'deployment':str(DEPLOY),'created_at':dt.datetime.now().astimezone().isoformat(),'private_source':{'path':str(source),'sha256':sha(source),'chapter':a.chapter,'source_chars':len(chapter),'line_start':text[:m.start(1)].count('\n')+1,'line_end':text[:m.end(1)].count('\n')+1},'references':refs,'cases':cases,'settings':{'content_storage':'gitignored_results_only','roles':['旁白','主人','零'],'assembly_pause_ms':'80 within paragraph; 260 after paragraph','manual_review':'pending'}}
    a.out.parent.mkdir(parents=True,exist_ok=True);a.out.write_text(json.dumps(payload,ensure_ascii=False,indent=2)+'\n')
    print(json.dumps({'source_chars':len(chapter),'segments':len(cases),'role_counts':{r:sum(x['role']==r for x in cases) for r in ['旁白','主人','零']},'rendered_chars':sum(len(x['text']) for x in cases),'quote_count':quote_index},ensure_ascii=False))


if __name__=='__main__':main()
