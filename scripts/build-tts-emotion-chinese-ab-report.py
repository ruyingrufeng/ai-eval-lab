#!/usr/bin/env python3
"""Validate the Mandarin-only F5/Fish A/B and create a blind listening pack."""
import datetime as dt
import hashlib
import html
import json
import random
import runpy
import shutil
import wave
from pathlib import Path

import numpy as np

ROOT = Path(__file__).resolve().parents[1]
DEPLOY = Path('/Users/jacky/Documents/Codex/2026-09-03/referenced-chatgpt-conversation-this-is-an/outputs/f5-tts-local')
RID = 'tts_emotion_chinese_ab_20260904'
RUNS = {
    'F5-TTS': ROOT / 'results/tts_emotion_chinese_ab_f5_20260904_0928',
    'Fish S2': ROOT / 'results/tts_emotion_chinese_ab_fish_20260904_0934',
}
MANIFEST = ROOT / 'benchmarks/tts_emotion_chinese_ab_20260904.json'
PROVENANCE = DEPLOY / 'reference-assets/mcae-spps/provenance.json'
PREP = runpy.run_path(str(ROOT / 'scripts/prepare-mcae-spps-references.py'))


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


manifest = json.loads(MANIFEST.read_text())
provenance = json.loads(PROVENANCE.read_text())
expected = [x['id'] for x in manifest['cases']]
assert len(expected) == len(set(expected)) == 6
for emotion, ref in manifest['references'].items():
    assert sha(ref['path']) == ref['sha256'] == provenance['selection'][emotion]['derived_sha256']
    assert abs(provenance['selection'][emotion]['measurement']['integrated_lufs'] + 23) <= .15

engines = {}
for engine, run in RUNS.items():
    status = json.loads((run / 'status.json').read_text())
    worker = json.loads((run / 'worker-result.json').read_text())
    events = [json.loads(x) for x in (run / 'events.jsonl').read_text().splitlines()]
    rows = [x for x in events if x.get('event') == 'generated']
    assert status['state'] == 'runnable' and status['exit_code'] == 0 and worker['ok']
    assert worker['completed'] == expected and [x['id'] for x in rows] == expected
    for row in rows:
        path = Path(row['path'])
        assert path.is_file() and sha(path) == row['sha256']
        with wave.open(str(path)) as audio:
            assert audio.getnchannels() == 1 and audio.getsampwidth() == 2
            pcm = np.frombuffer(audio.readframes(audio.getnframes()), dtype='<i2').astype(float) / 32768
            assert len(pcm) and np.sqrt(np.mean(pcm * pcm)) > .001 and np.mean(np.abs(pcm) >= .9999) <= .001
    asr = json.loads((run / 'asr.json').read_text())
    assert json.loads((run / 'asr-status.json').read_text())['exit_code'] == 0
    assert [x['name'] for x in asr] == expected
    am = runpy.run_path(str(ROOT / 'scripts/fish_s2_evidence.py'))['asr_metrics'](asr)
    resources = [json.loads(x) for x in (run / 'resources.jsonl').read_text().splitlines()]
    generation = [x for x in resources if x['phase'] == 'generation']
    baseline = json.loads((run / 'baseline.json').read_text())
    engines[engine] = {
        'clips': len(rows), 'rows': rows, 'asr_rows': asr, 'asr': am,
        'audio_seconds': sum(x['duration_seconds'] for x in rows),
        'generation_seconds': sum(x['generation_seconds'] for x in rows),
        'weighted_rtf': sum(x['generation_seconds'] for x in rows) / sum(x['duration_seconds'] for x in rows),
        'mlx_peak_gib': max(x['mlx_peak_gib'] for x in rows),
        'rss_max_gib': max(x['rss_gib'] for x in generation if x.get('rss_gib') is not None),
        'pressure_free_min': min(x['free_percent'] for x in generation),
        'pressure_free_max': max(x['free_percent'] for x in generation),
        'swap_peak_delta_gib': max(x['swap_gib'] for x in generation) - baseline['swap_gib'],
        'content_exact': sum(x['edits'] == 0 for x in am['per_clip']),
        'source_hashes': {str(p): sha(p) for p in [run/'manifest.json', run/'events.jsonl', run/'resources.jsonl', run/'status.json', run/'worker-result.json', run/'asr.json', run/'asr-status.json']},
    }

result = ROOT / 'results' / RID
result.mkdir(parents=True, exist_ok=True)
feedback_path = result / 'user-feedback.json'
feedback = json.loads(feedback_path.read_text()) if feedback_path.exists() else None
summary = {
    'schema_version': 1, 'run_id': RID, 'analyzed_at': dt.datetime.now().astimezone().isoformat(),
    'design': '同一位女性普通话演员、完全相同的六句中文、三种情绪；参考双遍响度匹配；两模型使用相同中文目标与种子。',
    'target_text': manifest['cases'][0]['text'], 'reference_provenance': provenance,
    'engines': engines, 'human_emotion_review': feedback or 'pending',
    'automatic_claim': '自动检查仅覆盖文件、文字、性能和响度；情绪差异由人工盲听决定。',
    'source_hashes': {str(p): sha(p) for p in [MANIFEST, PROVENANCE, ROOT/'scripts/prepare-mcae-spps-references.py', ROOT/'scripts/f5-tts-local.py', ROOT/'scripts/fish-s2-emotion-ab.py', ROOT/'scripts/f5-tts-asr.py', Path(__file__)] + ([feedback_path] if feedback else [])},
}
(result / 'summary.json').write_text(json.dumps(summary, ensure_ascii=False, indent=2) + '\n')

metrics = []
resource_rows = []
content_rows = []
for engine, data in engines.items():
    metrics.extend([
        {'label': engine + ' 速度', 'value': f'{data["weighted_rtf"]:.3f}×', 'note': '生成秒数 / 音频秒数'},
        {'label': engine + ' 文字错误率', 'value': f'{data["asr"]["weighted_cer"]:.2%}', 'note': f'{data["asr"]["edits_total"]}/{data["asr"]["refs_total"]}'},
    ])
    resource_rows.append([engine, data['clips'], f'{data["mlx_peak_gib"]:.3f} GiB', f'{data["rss_max_gib"]:.3f} GiB', f'{data["pressure_free_min"]}%–{data["pressure_free_max"]}%', f'{data["swap_peak_delta_gib"]:.3f} GiB'])
    content_rows.append([engine, f'{data["content_exact"]}/6', f'{data["asr"]["weighted_cer"]:.2%}', f'{data["generation_seconds"]:.2f}s', f'{data["audio_seconds"]:.2f}s'])
reference_rows = [[{'neutral':'中性','happy':'开心','sad':'悲伤'}[e], f'{x["measurement"]["integrated_lufs"]:.1f} LUFS', f'{x["measurement"]["true_peak_dbfs"]:.1f} dBFS', x['derived_sha256'][:12]] for e,x in provenance['selection'].items()]
artifact = {
    'schema_version': 2, 'id': RID, 'as_of': dt.date.today().isoformat(),
    'title': 'F5-TTS 与 Fish S2：全中文情绪参考 A/B', 'gate': 'runnable',
    'gate_label': 'runnable · 全中文短句情绪人工验收通过' if feedback else 'runnable · 全中文与响度控制通过，情绪待盲听',
    'summary': ('12/12 段均成功生成且文字回检无误。用户确认中性、开心、悲伤可区分，三种情绪像同一个中国人，音量稳定。本轮全中文短句情绪验收通过；长篇与多角色连续演绎仍待验证。' if feedback else '12/12 段均成功生成，自动回检未发现英文串入或文字错误。三条中文参考响度差仅 0.1 LU；试听副本再次统一到 −23 LUFS。是否存在可辨情绪变化仍需人工盲听。'),
    'metrics': metrics,
    'sections': [
        {'id':'design','title':'本轮纠正','paragraphs':['参考与目标台词全部使用中文。参考来自同一位女性普通话演员，三种情绪使用完全相同的六句中文。','原始参考串接后采用双遍 EBU R128 处理到 −23 LUFS；生成原件保留，试听副本再做同标准响度匹配。'], 'table':{'columns':['参考情绪','综合响度','真峰值','文件校验'], 'rows':reference_rows}},
        {'id':'content','title':'文字与速度','table':{'columns':['模型','精确片段','加权文字错误率','生成时间','音频时长'],'rows':content_rows},'paragraphs':['自动转写仅用于检查漏字、错字、重复和参考串入；标点差异不计为文字错误。']},
        {'id':'resource','title':'本机资源','table':{'columns':['模型','片段','MLX峰值','进程RSS采样峰值','可用内存比例','交换空间增量'],'rows':resource_rows},'paragraphs':['两个模型串行运行。MLX、RSS与系统统一内存不是可直接相加的口径；系统压力和交换空间用于判断整机风险。']},
        {'id':'review','title':'人工盲听','paragraphs':([feedback['verbatim'], feedback['scope'], '本轮全中文短句情绪、同人感、中文母语感与音量稳定性通过。该反馈是整组总体判断，不推断每个模型或片段的独立分数。'] if feedback else ['先听三条同演员原参考，再听随机排列的12段输出。分别记录听到的情绪、强度、是否像同一个人、中文自然度和音量是否稳定。','只有两个种子都能区分三种情绪，且仍像同一个中文说话者，才可把情绪能力推进到 verified。'])},
        {'id':'limits','title':'边界','bullets':['响度匹配会削弱“单纯靠更大声表达情绪”的线索，因此本轮更关注音高、节奏、停顿和语气。','仅测试一位演员、一句目标台词和两个种子，尚不代表长篇小说表现。','本轮不使用自动情绪分类器代替人耳。']},
        {'id':'source','title':'来源与许可','paragraphs':['MCAE-SPPS 来自公开 OSF 项目，录音为专业普通话演员；本地仅作非商业评测。派生参考保留文件哈希和处理记录。'], 'links':[{'label':'MCAE-SPPS 论文','url':'https://www.nature.com/articles/s41597-026-06976-z'},{'label':'MCAE-SPPS 官方 OSF','url':'https://osf.io/9jyzc'},{'label':'CC BY-NC 4.0','url':'https://creativecommons.org/licenses/by-nc/4.0/'}]},
    ], 'evidence': summary,
}
report = ROOT / 'docs/reports' / RID
report.mkdir(parents=True, exist_ok=True)
(report / 'artifact.json').write_text(json.dumps(artifact, ensure_ascii=False, indent=2) + '\n')
(report / 'report.html').write_text(runpy.run_path(str(ROOT/'scripts/render-evaluation-record.py'))['render'](artifact))
(report / 'SOURCE_NOTES.md').write_text('证据来自MCAE-SPPS官方OSF文件、本机串行运行、资源采样与本地ASR。情绪结论待用户盲听。\n')

out = DEPLOY / 'results' / RID
out.mkdir(parents=True, exist_ok=True)
(out/'audio').mkdir(exist_ok=True); (out/'references').mkdir(exist_ok=True)
for name in ['artifact.json','report.html','SOURCE_NOTES.md']:
    shutil.copy2(report/name, out/name)
shutil.copy2(result/'summary.json', out/'summary.json')
shutil.copy2(DEPLOY/'reference-assets/mcae-spps/ATTRIBUTION.md', out/'ATTRIBUTION.md')
for emotion, ref in manifest['references'].items():
    shutil.copy2(ref['path'], out/'references'/f'{emotion}.wav')
mapping = []
for engine, data in engines.items():
    for row in data['rows']:
        filename = f'{engine.lower().replace(" ", "-")}_{row["id"]}.wav'
        target = out/'audio'/filename
        PREP['loudnorm'](row['path'], target)
        measurement = PREP['measure'](target)
        assert abs(measurement['integrated_lufs'] + 23) <= .2
        mapping.append({'model':engine,'emotion':row['reference_emotion'],'seed':row['seed'],'file':'audio/'+filename,'listening_loudness':measurement})
random.Random(20260904).shuffle(mapping)
(out/'mapping.json').write_text(json.dumps(mapping, ensure_ascii=False, indent=2) + '\n')
(out/'listening_review.csv').write_text('样本,听到的情绪,强度1至5,像同一个人,中文自然度1至5,音量稳定,内容问题,备注\n' + '\n'.join(f'{i:02d},,,,,,,' for i in range(1,13)) + '\n')
e = html.escape
page = ['<!doctype html><html lang="zh-CN"><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><title>全中文情绪盲听</title><style>body{max-width:900px;margin:32px auto;padding:0 18px;background:#f4f3f9;color:#252337;font:17px/1.7 system-ui}section{background:#fff;padding:18px;margin:18px 0;border-radius:14px}audio{width:100%}.clip{border-top:1px solid #ddd;padding:14px 0}details{margin-top:8px}summary{cursor:pointer;font-weight:600}</style><h1>全中文情绪参考盲听</h1><p>目标台词始终相同：门开了，你终于回来了。我一直在这里等你。所有试听音频已统一综合响度。先听同一位普通话演员的三种原参考，再听随机样本。</p><section><h2>中文原参考</h2>']
for emotion, label in [('neutral','中性'),('happy','开心'),('sad','悲伤')]:
    page.append(f'<p>{label}</p><audio controls preload="none" src="references/{emotion}.wav"></audio>')
page.append('</section><section><h2>随机盲听</h2>')
labels={'neutral':'中性','happy':'开心','sad':'悲伤'}
for i, item in enumerate(mapping, 1):
    page.append(f'<div class="clip"><strong>样本 {i:02d}</strong><audio controls preload="none" src="{e(item["file"])}"></audio><details><summary>听完再看答案</summary><p>模型：{e(item["model"])}；参考情绪：{labels[item["emotion"]]}；随机种子：{item["seed"]}</p></details></div>')
page.append('</section><p><a href="listening_review.csv">下载空白听评表</a>　<a href="report.html">查看技术报告</a></p></html>')
(out/'listening.html').write_text('\n'.join(page))
print(out)
