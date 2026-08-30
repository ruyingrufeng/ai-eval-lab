#!/usr/bin/env python3
"""Apply the installed inswapper model to the two Flux full-body identity test images."""
from __future__ import annotations
import json, os
from datetime import datetime
from pathlib import Path
import cv2
import insightface
from insightface.app import FaceAnalysis

os.environ.setdefault("OMP_NUM_THREADS", "4")
PROJECT=Path(__file__).resolve().parents[1]
ROOT=PROJECT/'results/aesthetic/20260813-flux-identity-lock/inswapper'
MASTER=PROJECT/'results/aesthetic/20260812-blind/flux/seed_0007.png'
TARGETS={s:PROJECT/f'results/aesthetic/20260813-flux-identity-lock/weight_1.00/seed_{s}.png' for s in (31415,27182)}
MODEL=Path('/Users/jacky/ComfyUI/models/insightface/inswapper_128.onnx')
IF_ROOT='/Users/jacky/ComfyUI/models/insightface'

def biggest(faces): return max(faces,key=lambda f:(f.bbox[2]-f.bbox[0])*(f.bbox[3]-f.bbox[1]))

def main():
    ROOT.mkdir(parents=True,exist_ok=True)
    app=FaceAnalysis(name='antelopev2',root=IF_ROOT,providers=['CPUExecutionProvider'])
    app.prepare(ctx_id=-1,det_size=(640,640))
    swapper=insightface.model_zoo.get_model(str(MODEL),providers=['CPUExecutionProvider'])
    master=cv2.imread(str(MASTER)); mf=app.get(master)
    if not mf: raise RuntimeError('master face not detected')
    source=biggest(mf); records=[]
    for seed,target_path in TARGETS.items():
        target=cv2.imread(str(target_path)); tf=app.get(target)
        if not tf: raise RuntimeError(f'target face not detected: {seed}')
        dest=biggest(tf); out=swapper.get(target,dest,source,paste_back=True)
        path=ROOT/f'seed_{seed}.png'; cv2.imwrite(str(path),out)
        check=biggest(app.get(out)); sim=float(source.normed_embedding@check.normed_embedding)
        records.append({'seed':seed,'status':'ok','similarity':round(sim,4),'output':str(path)})
        print(seed,round(sim,4),path)
    payload={'title':'Flux full-body inswapper identity evaluation','tested_at':datetime.now().astimezone().isoformat(timespec='seconds'),
             'master':str(MASTER),'targets':{str(k):str(v) for k,v in TARGETS.items()},'model':str(MODEL),'records':records}
    (ROOT/'report.json').write_text(json.dumps(payload,ensure_ascii=False,indent=2)+'\n')

if __name__=='__main__': main()
