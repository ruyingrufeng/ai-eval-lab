#!/usr/bin/env python3
"""Rebuild the Fish S2 deployment record from the archived experiment logs."""
from datetime import datetime
import json
from pathlib import Path
import re
import runpy

ROOT = Path(__file__).resolve().parents[1]
ID = 'fish_s2_pro_mlx_20260903'
raw = ROOT/'results'/ID
out = ROOT/'docs/reports'/ID
rows = [json.loads(x) for x in (raw/'logs/validation.jsonl').read_text().splitlines()]
clips = [x for x in rows if x['event'] == 'generated']
asr = json.loads((raw/'logs/asr-verification.json').read_text())
feedback = json.loads((raw/'user-feedback.json').read_text())
total_audio = sum(x['audio_seconds'] for x in clips)
total_gen = sum(x['generation_seconds'] for x in clips)
footprint = int(re.search(r'(\d+)  peak memory footprint', (raw/'logs/validation-console.log').read_text())[1])/1024**3
lookup = {x['name']:x for x in asr}
labels = ['中文旁白','合成参考 A','合成参考 B','克隆：普通','克隆：兴奋','克隆：悲伤','说话人标签实验','场景 1：旁白','场景 2：A','场景 3：B','场景 4：旁白','场景 5：A','场景 6：B']
deployment = json.loads((raw/'archive-manifest.json').read_text())['source']
data = {
    'schema_version': 1, 'id': ID, 'surface': 'report', 'status': 'ready',
    'generated_at': datetime.now().astimezone().isoformat(), 'as_of': '2026-09-03',
    'title': 'Fish S2 Pro 本地配音：试听认可，保留按需试用',
    'gate': 'runnable', 'gate_label': 'runnable · 用户试听正向反馈 · 完整验收待补',
    'summary': 'M5 / 32GB 上的 MLX 8-bit 路线已完成隔离安装和中文、参考音频克隆、情绪标签、三角色逐句合成。用户反馈“效果还不错”。保留为本地配音实验选项；长篇、声纹一致性和并发门禁未完成，不升级为完整 verified，不自动替换现有语音路由。',
    'metrics': [
        {'label':'主套件生成成功','value':f'{len(clips)}/13','note':'另有 3 段 CLI 入口复现，不计入基准'},
        {'label':'加权实时系数','value':f'{total_gen/total_audio:.3f}×','note':f'{total_audio:.3f}s 音频 / {total_gen:.3f}s 生成'},
        {'label':'系统进程峰值 footprint','value':f'{footprint:.2f} GiB','note':'MLX 峰值 11.093GiB；RSS 不代表总占用'},
        {'label':'ASR 文字完全匹配','value':f'{sum(x["character_error_rate"] == 0 for x in asr)}/13','note':'另 3 段仅出现普通话同音字差异'},
    ],
    'evidence': {
        'deployment': deployment, 'raw_archive': f'results/{ID}', 'benchmark':f'benchmarks/{ID}.yaml',
        'model': json.loads((raw/'model-lock.json').read_text()),
        'asr_model': json.loads((raw/'asr-model-lock.json').read_text()),
        'weight_files': json.loads((raw/'model-files.json').read_text()),
        'package_lock': (raw/'requirements.lock.txt').read_text(),
        'user_feedback': feedback,
        'performance': [{k:v for k,v in x.items() if k not in ['text','reference_text','output']} for x in clips],
        'asr': [{'name':x['name'],'character_error_rate':x['character_error_rate']} for x in asr],
        'generation_wall_seconds':total_gen, 'audio_seconds':total_audio,
        'process_wall_seconds':320.24, 'peak_physical_footprint_gib':footprint,
        'no_production_assets_embedded':True,
    },
    'sections': [
        {'id':'record-qa','title':'归档核验状态','paragraphs':[
            '已核对 22 份复制证据的 SHA-256、YAML/JSON 可解析性、报告内嵌 artifact 与外部 artifact.json 一致性，以及无远程资源依赖。',
            'Browser 安全策略阻止打开本地 file URL，未绕过限制；桌面与窄屏视觉核验尚未完成。此项是报告展示核验缺口，不改变已保存的 TTS 实测数据。']},
        {'id':'feedback','title':'试听反馈与决策','quote':feedback['quote'],'paragraphs':[
            '来源：用户在本任务中对试听效果的直接反馈，2026-09-03（时间精度：日）。这是整体主观认可，没有虚构评分、盲听结果或逐角色验收。',
            '定案：保留 Fish S2 Pro 供人工复核的短句与多角色段落按需试用，暂列 runnable。现有 Qwen3-TTS 9893 和其他服务路由不因本次记录而变更。']},
        {'id':'gates','title':'四关卡与验证边界','table':{'columns':['关卡','本次证据','结论'],'rows':[
            ['discovered','上游项目、MLX 包与固定权重提交已核对','通过'],
            ['installable','独立 Python 3.13.15；25 个依赖无冲突；官方 SHA-256 核验','通过'],
            ['runnable','13 段主套件 + 角色 JSON / 参考路径入口运行成功','通过'],
            ['verified','缺长篇、多 seed、声纹评分、排队并发与独立空闲基线','未完成；不进入推荐栈']]}},
        {'id':'performance','title':'13 段实测明细','paragraphs':[
            'RTF = 生成耗时 / 音频时长，小于 1 才快于实时。加权值由总耗时除以总音频时长得到，不是逐段 RTF 的算术平均。',
            '生成耗时含模型预填充、音频 token 推理和 codec 解码，不含 WAV 写盘。参考编码共约 4.25 秒，作为单独阶段记录。加载约 1.453 秒，发生在下载校验后，不能当作重启电脑后的冷加载。'],
         'table':{'columns':['样本','音频 / 秒','生成 / 秒','RTF','MLX 峰值 / GiB','文字回检'],
             'rows':[[label,f'{x["audio_seconds"]:.3f}',f'{x["generation_seconds"]:.3f}',f'{x["rtf"]:.3f}',f'{x["mlx_peak_gib"]:.3f}','一致' if lookup[x['name']]['character_error_rate']==0 else '同音字差异'] for label,x in zip(labels,clips)]}},
        {'id':'resources','title':'统一内存与后台负载','bullets':[
            '测试时已有 llama-server 初始 RSS 约 16.3GiB，未暂停它。测试条件为共存负载，没有单独运行对照，不能量化干扰因子。',
            f'权重加载后 MLX 约 6.261GiB；MLX 峰值 {max(x["mlx_peak_gib"] for x in clips):.3f}GiB；macOS time 的峰值 footprint 为 {footprint:.3f}GiB。进程最高 RSS 仅 1.327GiB，明显不能代替 GPU 与映射内存。不同口径不能相加。',
            '开始时系统 swap 为 0；句末采样最高 3.746GiB，另一次运行中快照为 3812.19MiB。这里只能称采样最大值，未连续捕获绝对峰值。',
            'memory_pressure 的系统空闲百分比由开始 28% 降至最低句末样本 14%，结束样本 33%。没有持续记录压缩内存/pageout，不宣称完整资源门禁已通过。',
            '单次 pmset 检查没有 thermal/performance warning；未测连续 30 分钟负载，也未证明不存在温度或功耗影响。']},
        {'id':'quality','title':'文字、情绪和多角色结果','bullets':[
            '全部样本均为非空、有限数值的 44.1kHz 单声道 16-bit PCM WAV；无 token 上限命中，无超幅削波。三角色六句拼接场景为 26.049 秒。',
            '本地 Qwen3-ASR 1.7B int8 分时回检 13 段；10 段忽略标点后完全匹配，3 段差异为“她/他”“薇/威”“它/他”。保留原始 CER，不将同音字人为修正成零错误。',
            '转写未显示明显漏读或标签被读出，但 ASR 不是人工真值；未进行双 ASR 交叉验证。',
            '克隆测试使用本模型生成的参考音频，没有使用用户真人录音。验证了参考条件生成通路，未验证真人克隆相似度。',
            '普通、兴奋、悲伤使用同文本与同参考；用户给出整体正面反馈，不能据此宣称所有情绪或音色分别获认证。',
            '说话人标签仅作单次生成实验。公开接口只接受一组参考音频；小说示例以每个角色固定参考、逐句合成、再拼接实现。尚无自动小说拆角和情绪导演层。']},
        {'id':'deployment','title':'固定版本、入口与复现','paragraphs':[
            'Python 3.13.15；mlx-speech 0.5.2；mlx / mlx-metal 0.32.2。uv 0.12.3 与 ffmpeg 8.1.2 使用已有安装，不需要 conda、PyTorch 或 CUDA。',
            '部署目录：'+deployment,
            '模型、虚拟环境、原始音频与参考声音留在外部目录。项目仅保存评测定义、记录、脚本和 Git 排除的日志副本。'],
         'commands':['./scripts/fish-s2-local.sh --text "你好，欢迎收听。" --output samples/test.wav',
                     './scripts/fish-s2-local.sh --suite --log logs/new-validation.jsonl',
                     f'cd "{deployment}"\n./verify-audio.sh --metrics logs/new-validation.jsonl --output logs/new-asr.json',
                     'python3 scripts/build-fish-s2-report.py'],
         'bullets':['run.sh 默认离线生成；进程按需启动并退出，没有监听端口或新增开机启动服务。','重跑套件会覆盖固定命名的测试 WAV；要保留原测试音频，请先复制 samples 与 references。','模型主权重约 4.85GB + codec 约 1.87GB；完整 Fish 包约 6.74GB，可选 ASR 约 2.51GB。']},
        {'id':'issues','title':'问题与修复记录','bullets':[
            '官方站点直连探测超时，系统已有代理可访问 API；默认 Xet 传输缓慢，改用公共镜像分块，按官方固定提交的 SHA-256 校验后才采用。没有改系统代理。',
            '首次性能记录脚本误向 codec 包装对象调用 parameters() 导致 AttributeError，已修正自有记录脚本并完整重跑；第三方库未打补丁，异常日志保留。',
            'uv 初次创建的项目 Python 全局链接已撤销，setup.sh 使用 --no-bin；原默认 Python 仍为 .agent-reach-venv 的 3.13.12。',
            '中断下载残片约 537MB 已在权重校验完成后清理。部署阶段结束时生成、回检与下载进程均退出；本次归档未再启动推理。']},
        {'id':'next','title':'下一阶段验收','bullets':[
            '以长段落和跨章节角色复现为重点，增加多随机种子/重复样本，估计重复、漏读和异常率。',
            '独立记录角色声纹一致性与情绪听感评分；如测真人克隆，使用授权录音并记录授权范围。',
            '在明确安排负载的情况下补单独运行、队列并发及共存对照，采集完整 pressure/swap/pageout 和长时间稳定性。',
            '用户当前要求是归档记录，本次没有额外执行上述评测，也没有改选型门槛。']},
        {'id':'sources','title':'来源与审计入口','paragraphs':[
            f'主日志：results/{ID}/logs/validation.jsonl；转写：logs/asr-verification.json；复制校验：archive-manifest.json。',
            '完整依赖锁定、模型提交和权重 SHA-256 包含在同目录 artifact.json；报告内嵌同一份脱敏指标数据，不嵌入小说台词或音频。',
            'mlx-speech 为 MIT；Fish 权重沿用 Fish Audio Research License，非商业/研究可用，商业许可需另行取得。此处记录部署时已核对的来源，不替代后续商用许可核验。'],
         'links':[{'label':'mlx-speech 项目','url':'https://github.com/appautomaton/mlx-speech'},
                  {'label':'MLX 8-bit 模型包','url':'https://huggingface.co/appautomaton/fishaudio-s2-pro-8bit-mlx'},
                  {'label':'Fish 官方模型与许可证','url':'https://huggingface.co/fishaudio/s2-pro'}]},
    ],
}
out.mkdir(parents=True, exist_ok=True)
(out/'artifact.json').write_text(json.dumps(data, ensure_ascii=False, indent=2)+'\n')
renderer = runpy.run_path(str(ROOT/'scripts/render-evaluation-record.py'))['render']
(out/'report.html').write_text(renderer(data), encoding='utf-8')
print(f'Generated {out}/report.html from {len(clips)} clips and {len(asr)} ASR records')
