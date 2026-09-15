#!/usr/bin/env python3
"""Render Fish reports only from recomputed summary and bound local evidence."""
import argparse
import csv
import datetime as dt
import hashlib
import json
from pathlib import Path
import runpy
import wave

ROOT = Path(__file__).resolve().parents[1]

def chapter_check(run):
    paths = sorted((run/'assembled').glob('chapter_*.wav'))
    if not paths:
        if run.name.startswith('fish_s2_persistent_'):
            result = chapter_check(ROOT/'results/fish_s2_followup_20260903_142148')
            result['source_run'] = 'fish_s2_followup_20260903_142148'
            result['reuse_note'] = '复用旧轮 21 段的完整章节供试听；不将本次补测填充片段冒充新章节。'
            return result
        return {'state':'pending', 'reason':'No assembled chapter'}
    path = paths[0]
    try:
        with wave.open(str(path),'rb') as w:
            params = w.getparams(); pcm = w.readframes(w.getnframes()); duration = w.getnframes()/w.getframerate()
        chunks = []
        segments = sorted((run/'audio').glob('T1_chapter_seg*.wav'))
        if len(segments) != 21:
            return {'state':'fail', 'reason':'Expected 21 chapter segments'}
        for i,seg in enumerate(segments):
            with wave.open(str(seg),'rb') as w:
                if (w.getframerate(),w.getnchannels(),w.getsampwidth()) != (params.framerate,params.nchannels,params.sampwidth):
                    return {'state':'fail','reason':'PCM format mismatch'}
                if i: chunks.append(bytes(round(params.framerate*.25)*params.nchannels*params.sampwidth))
                chunks.append(w.readframes(w.getnframes()))
        return {'state':'pass' if pcm == b''.join(chunks) else 'fail', 'path':str(path), 'duration_seconds':duration, 'segments':len(segments), 'sha256':hashlib.sha256(path.read_bytes()).hexdigest(), 'human_review':'pending'}
    except Exception as exc:
        return {'state':'fail', 'reason':str(exc)}

def build(run):
    s = json.loads((run/'summary.json').read_text())
    integrity = s['integrity']
    n = integrity['verified_audio_count']; expected = integrity['expected_count']
    timing = s['fish_timing']; seconds = timing['pure_generation_seconds']
    wall = timing.get('worker_wall_seconds')
    cer = s.get('asr_weighted_cer')
    percentage = f'{cer*100:.2f}%' if cer is not None else '未取得'
    anchors = s.get('anchor_per_role_rtf',{})
    chapter = chapter_check(run)
    reviews = list(csv.DictReader((run/'listening_review.csv').open())) if (run/'listening_review.csv').exists() else []
    qualitative = list(dict.fromkeys(r['artifact_notes'] for r in reviews if r.get('reviewer') and r.get('artifact_notes')))
    feedback = s.get('human_feedback', {}).get('feedback', [])
    qualitative.extend('用户原话：' + item['quote'] for item in feedback if item.get('quote'))
    emotion_failed = s.get('acceptance_verdicts', {}).get('emotion_distinguishability', '').startswith('FAIL:')
    emotion_note = '本轮用户试听反馈：同一音色缺乏可辨情绪变化，情绪需求未通过；仅适用于本轮配置与所听样本，不推广至全部 Fish 版本。' if emotion_failed else '旧轮角色 A 的定性反馈为声音一致但情绪平淡；新样本必须另行试听，不能沿用旧评分。'
    grades = [{k:r.get(k) for k in ('clip_id','intelligibility_1to5','voice_consistency_1to5','naturalness_1to5')} for r in reviews if any(r.get(k) for k in ('intelligibility_1to5','voice_consistency_1to5','naturalness_1to5'))]
    resident = timing.get('persistent_model_verified',False)
    resources = s.get('resource_summary',{})
    metrics = [
        {'label':'证据完整性','value':f'{n}/{expected}', 'note':'通过：预期任务、退出码、音频和哈希一致' if integrity['pass'] else '未通过；见证据问题'},
        {'label':'加权 RTF','value':f"{s['weighted_rtf']:.3f}×" if s.get('weighted_rtf') is not None else '未取得','note':s.get('acceptance_verdicts',{}).get('weighted_rtf','pending')},
        {'label':'ASR 加权 CER','value':percentage,'note':f"{s.get('asr_weighted_cer_numerator',0)}/{s.get('asr_weighted_cer_denominator',0)}；自动转写筛查，非人工验收"},
        {'label':'纯生成时间','value':f'{seconds/60:.2f} 分钟','note':f'阶段总耗时 {wall/60:.2f} 分钟' if wall is not None else '阶段总耗时缺失'},
    ]
    anchor_rows = []
    for role, info in anchors.items():
        ratio = info.get('end_slowdown_ratio')
        mid = info.get('middle_slowdown_ratio')
        anchor_rows.append([role,info.get('start_rtf'),info.get('middle_rtf'),info.get('end_rtf'),f'{mid*100:+.1f}%' if mid is not None else '缺失',f'{ratio*100:+.1f}%' if ratio is not None else '缺失',s.get('acceptance_verdicts',{}).get('anchor_end_'+role,'pending')])
    sections = [
        {'id':'verdict','title':'当前可用范围','paragraphs':['本机语音生成仍登记为 runnable。数值筛查、内容正确性、情绪与自然度分别验收；不自动晋级推荐栈。','本轮属于同一模型进程持续运行补测。' if resident else '本轮每段重新加载模型；累计生成时间不能证明单一模型长期驻留稳定。',emotion_note]},
        {'id':'gates','title':'验收判定（自动检查与人工反馈）','table':{'columns':['项目','判定'], 'rows':[[k,v] for k,v in s.get('acceptance_verdicts',{}).items()]}},
        {'id':'errors','title':'证据问题','bullets':integrity['errors'] or ['已验证全部预期生成任务的 WAV 和哈希；人工检查尚待完成。']},
        {'id':'timing','title':'速度与持续运行','paragraphs':[f'纯生成 {seconds:.3f} 秒；音频 {s.get("audio_seconds_total",0):.3f} 秒。RTF = 纯生成耗时 / 音频时长。', timing.get('method',''), '不与第一轮 5.25× 作严格 A/B：样本组成、部分参考条件和模型加载方式不同。']},
        {'id':'anchors','title':'同角色 RTF 前后配对','table':{'columns':['角色','开头 RTF','中段 RTF','结尾 RTF','中段增幅','结尾增幅','结尾门槛判定'],'rows':anchor_rows},'paragraphs':['原 120 段测试锚点排布不均匀，旁白开头与 A/B 开头相隔约 12 分钟，中段与结尾相隔约 1 分钟；原轮不能单凭变化认定热降速。'] if not resident else ['先完成三角色预热；三个角色锚点按相同文本、参考、seed 在开始、约 15 分钟和至少 30 分钟时配对。结尾门槛通过不代表中途没有波动；没有 GPU 温度/频率证据时不归因为热降频。']},
        {'id':'asr','title':'文字回检','paragraphs':[s.get('asr_cleaning_method','尚未回检'),'去除控制标签；保留同音字差异。CER 通过不能替代漏句、尾句、角色及情绪人工复核。'],'table':{'columns':['指标','值'],'rows':[['加权 CER',percentage],['编辑距离',s.get('asr_weighted_cer_numerator')],['参考字符',s.get('asr_weighted_cer_denominator')],['转写段数',s.get('asr_clip_count')]]}},
        {'id':'resources','title':'内存与系统压力','paragraphs':['RSS、MLX 分配统计与系统统一内存是不同口径；12GiB 配置值不等于整机实测硬上限。'],'table':{'columns':['字段','实测'],'rows':[[k,json.dumps(v,ensure_ascii=False)] for k,v in resources.items()]}},
        {'id':'chapter','title':'完整章节','paragraphs':[f'拼接校验：{chapter["state"]}。'+(f' {chapter["segments"]} 段，{chapter["duration_seconds"]:.3f} 秒，逐字节验证原片段与 0.25 秒间隔。' if chapter.get('segments') else chapter.get('reason','')),chapter.get('reuse_note','本轮 21 段章节片段已拼接。'),'整章漏句、重复、停顿和听感仍需人工复核。']},
        {'id':'review','title':'人工反馈与归因','paragraphs':qualitative or ['尚无本轮人工反馈。'],'bullets':['仅保存明确的定性反馈；没有用户给出的分数就留空。',f'当前具有数字评分的记录数：{len(grades)}。未填写不视作通过。'] + (['本次为整体试听反馈，未列出具体片段；不据此代填逐段评分、声纹相似度或内容正确性。'] if feedback else [])},
        {'id':'sources','title':'来源与复现','paragraphs':[str(run),'summary.json → artifact.json → report.html。报告生成器不另算 CER，不维护脱离数据源的通过文案。'],'commands':[f'python scripts/fish-s2-followup.py analyze --run-id {run.name}',f'python scripts/build-fish-s2-followup-report.py --run-id {run.name}'] if not resident else [f'python scripts/analyze-fish-persistent.py {run.name}']},
    ]
    speed = s.get('acceptance_verdicts',{}).get('weighted_rtf','pending')
    speed_note = '整体速度达到本轮门槛。' if speed.startswith('pass:') else '整体速度尚未达到本轮门槛。'
    return {'schema_version':2,'id':run.name,'as_of':dt.date.today().isoformat(),'title':'Fish S2 本地评测：证据与验收','gate':'runnable','gate_label':'runnable · 情绪需求未通过，不进入推荐栈' if emotion_failed else 'runnable · 人工听评及未覆盖项目仍待验收','summary':f'已核验音频 {n}/{expected} 段；加权 CER {percentage}。'+('证据完整性通过。' if integrity['pass'] else '证据完整性未通过。')+speed_note+(' 用户试听确认同一音色缺乏可辨情绪变化，本轮情绪验收未通过。' if emotion_failed else ' 不自动判定角色情绪合格。'),'metrics':metrics,'sections':sections,'evidence':{'summary':s,'chapter':chapter,'numeric_reviews':grades,'report_generator_sha256':hashlib.sha256(Path(__file__).read_bytes()).hexdigest()},'notes':{'visual_qa':'静态响应式结构检查；本会话未完成浏览器视觉复核','html_self_contained':True}}

def main():
    p=argparse.ArgumentParser();p.add_argument('--run-id',required=True);a=p.parse_args()
    run=ROOT/'results'/a.run_id
    data=build(run);dest=ROOT/'docs/reports'/a.run_id;dest.mkdir(parents=True,exist_ok=True)
    (dest/'artifact.json').write_text(json.dumps(data,ensure_ascii=False,indent=2)+'\n')
    renderer=runpy.run_path(str(ROOT/'scripts/render-evaluation-record.py'))['render']
    (dest/'report.html').write_text(renderer(data))
    (dest/'SOURCE_NOTES.md').write_text('本报告从原始事件重新分析为 summary，再统一生成 artifact 与 HTML。\n原始来源哈希见 summary.source_hashes；不将人工待评项目当作通过。\n')
    print(dest/'report.html')
if __name__=='__main__': main()
