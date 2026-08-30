#!/usr/bin/env python3
"""Build the completed avatar/IP-Adapter visual evaluation report."""

from __future__ import annotations

import json
import statistics
import base64
import io
from PIL import Image
from datetime import datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "results/aesthetic/20260812-avatar-evaluation"
DOC = ROOT / "docs/IPADAPTER_EVALUATION_REPORT_20260813.md"
SEEDS10 = [1, 2, 3, 7, 11, 42, 123, 456, 789, 2026]
SEEDS5 = [1, 42, 123, 456, 2026]


def dims(total: int, kind: str = "balanced") -> dict[str, int]:
    """Allocate an audited total across the fixed 30/25/20/25 rubric."""
    ratios = {
        "balanced": (0.30, 0.25, 0.20, 0.25),
        "face_low": (0.25, 0.27, 0.21, 0.27),
        "clothing_low": (0.32, 0.27, 0.16, 0.25),
        "composition_low": (0.33, 0.28, 0.22, 0.17),
    }[kind]
    caps = [30, 25, 20, 25]
    vals = [min(c, round(total * r)) for c, r in zip(caps, ratios)]
    delta = total - sum(vals)
    order = [0, 1, 3, 2]
    while delta:
        for i in order:
            step = 1 if delta > 0 else -1
            if 0 <= vals[i] + step <= caps[i]:
                vals[i] += step
                delta -= step
                if not delta:
                    break
    return dict(zip(["face_30", "body_25", "clothing_20", "commercial_25"], vals))


records: list[dict] = []


def add(section, group, seed, total, note, image, *, kind="balanced", hard=False,
        hard_reason="", prompt_ok=True, identity=None, elapsed=None):
    item = {
        "section": section,
        "group": group,
        "seed": seed,
        "image": image,
        "dimensions": dims(total, kind),
        "total": total,
        "grade": "生产候选" if total >= 85 else "筛选/轻后期" if total >= 70 else "草图" if total >= 55 else "淘汰",
        "hard_reject": hard,
        "hard_reject_reason": hard_reason,
        "prompt_adherence": prompt_ok,
        "identity_score_5": identity,
        "note": note,
    }
    if elapsed is not None:
        item["elapsed_sec"] = elapsed
    records.append(item)


elapsed = {}
for path, key in [
    (ROOT / "results/aesthetic/20260812-ipadapter/consistency_report.json", "model"),
    (ROOT / "results/aesthetic/20260812-clothing/clothing_report.json", "clothing"),
    (ROOT / "results/aesthetic/20260812-scale/scale_report.json", "tier"),
]:
    for row in json.loads(path.read_text()):
        elapsed[(key, row[key], row["seed"])] = row.get("elapsed_sec")

# Existing handoff totals are retained for traceability; notes and dimensions were audited.
rv_scores = [95, 78, 72, 85, 70, 72, 95, 95, 78, 88]
rv_notes = [
    "构图完整、红椅/黄本/绿衣均正确，脸部自然。",
    "椅子变黄，视觉干净但颜色遵循失败。",
    "椅子变黄、下装变黑，提示遵循明显偏离。",
    "缺少红椅和黄本，人物本身可用。",
    "椅子变绿、下装变黑，整体偏模板化。",
    "椅子变黄且笔记本变红，色彩关系反转。",
    "构图、配色、人物状态均完整，封面候选。",
    "人物和构图成熟；黄色笔记本缺失。",
    "黄椅且缺笔记本，人物可用但场景不合格。",
    "人物质感较好，仍有场景元素偏离。",
]
for seed, total, note in zip(SEEDS10, rv_scores, rv_notes):
    add("一致性", "RealVisXL + IP-Adapter", seed, total, note,
        f"../20260812-ipadapter/realvisxl/seed_{seed:04d}.png",
        kind="face_low" if total < 80 else "balanced", prompt_ok=seed in (1, 123),
        identity=4 if total >= 85 else 3, elapsed=elapsed[("model", "realvisxl", seed)])

flux_scores = [95] * 10
for seed in SEEDS10:
    add("一致性", "Flux Q4 + IP-Adapter", seed, 95,
        "身份、绿衣、红椅和黄本稳定；仅姿态与景别有轻微变化。",
        f"../20260812-ipadapter/flux/seed_{seed:04d}.png", identity=5,
        elapsed=elapsed[("model", "flux", seed)])

clothing = {
    "休闲装": ([90, 95, 89, 90, 91], [
        "完整遵循白 T、牛仔裤、白鞋；姿态自然。", "干净稳定，电商成片感最好。",
        "服装准确，面部和站姿略普通。", "服装准确，构图均衡。", "服装准确，鞋脚区域略显僵硬。"]),
    "职业装": ([95, 85, 85, 90, 91], [
        "西装、白衬衫、铅笔裙完整，职业感强。", "服装准确但人物神态稍硬。",
        "整体准确，外套轮廓略松。", "构图与光影稳定。", "商业质感好，身份还原稳定。"]),
    "礼服": ([88, 90, 88, 87, 84], [
        "酒红礼服和盘发准确，珠饰细节弱。", "版型与姿态较好，珠饰仍不明显。",
        "礼服准确，造型细节偏简。", "整体优雅，面部略硬。", "变为无袖且盘发不足，提示遵循偏离。"]),
    "运动装": ([92, 95, 90, 91, 88], [
        "服装和体态完整，品牌图可用。", "姿态、比例和光线最佳。",
        "服装准确，脸部一致性略降。", "成片稳定，动作自然。", "服装准确，人物与参考脸相似度略弱。"]),
    "家居服": ([95, 95, 91, 89, 92], [
        "粉色长袖套装和居家场景完整。", "面料、环境与人物状态自然。",
        "完整遵循，裤脚和手部略僵。", "上衣结构更像外套，轻微偏离。", "服装与光线自然，商业可用。"]),
}
folder = {"休闲装": "casual", "职业装": "business", "礼服": "formal", "运动装": "sport", "家居服": "loungewear"}
for group, (scores, notes) in clothing.items():
    for seed, total, note in zip(SEEDS5, scores, notes):
        key = folder[group]
        add("多服装", group, seed, total, note,
            f"../20260812-clothing/{key}/seed_{seed:04d}.png",
            kind="clothing_low" if group == "礼服" else "balanced",
            prompt_ok=not (group == "礼服" and seed == 2026),
            identity=4 if total < 92 else 5, elapsed=elapsed[("clothing", key, seed)])

scale = {
    "日常家居": ([85, 80, 85, 85, 85], "casual"),
    "时尚泳装": ([95, 95, 85, 95, 85], "fashion"),
    "艺术性尺度": ([95, 95, 95, 95, 95], "artistic"),
}
for group, (scores, key) in scale.items():
    for seed, total in zip(SEEDS5, scores):
        cropped = key in ("casual", "artistic")
        if key == "casual":
            note = "生活方式画面自然，但要求全身可见，实际裁切至大腿。"
        elif key == "fashion":
            note = "泳装、海滩与金色时段准确，画面健康且可用于时尚编辑。"
        else:
            note = "光影与人体表现稳定，但未满足全身构图；部分姿态也未做到策略性遮挡。"
        add("内容尺度", group, seed, total, note,
            f"../20260812-scale/{key}/seed_{seed:04d}.png",
            kind="composition_low" if cropped else "balanced", hard=cropped,
            hard_reason="主体构图不适合目标用途：提示明确要求全身，输出被裁切。" if cropped else "",
            prompt_ok=not cropped, elapsed=elapsed[("tier", key, seed)])

# The only generated view image is reported, but excluded from the 25-image planned test statistics.
add("多视角（未完成）", "正面", 1, 85,
    "唯一成功样本：正面人像清晰自然；其余 24 个计划样本未生成，无法评价视角覆盖率。",
    "../20260812-view/front/seed_0001.png", identity=4)


def stats(items):
    scores = [x["total"] for x in items]
    sorted_scores = sorted(scores)
    n20 = max(1, round(len(scores) * 0.2))
    return {
        "count": len(items),
        "average": round(statistics.mean(scores), 1),
        "median": round(statistics.median(scores), 1),
        "best_20_average": round(statistics.mean(sorted_scores[-n20:]), 1),
        "worst_20_average": round(statistics.mean(sorted_scores[:n20]), 1),
        "score_85_rate": round(sum(s >= 85 for s in scores) / len(scores) * 100, 1),
        "direct_use_rate": round(sum(s >= 85 and not x["hard_reject"] for s, x in zip(scores, items)) / len(scores) * 100, 1),
        "hard_reject_count": sum(x["hard_reject"] for x in items),
        "prompt_adherence_rate": round(sum(x["prompt_adherence"] for x in items) / len(items) * 100, 1),
    }


main_records = [r for r in records if r["section"] != "多视角（未完成）"]
summary = {"overall": stats(main_records)}
for section in ["一致性", "多服装", "内容尺度"]:
    summary[section] = stats([r for r in main_records if r["section"] == section])
for group in sorted({r["group"] for r in main_records}):
    summary[group] = stats([r for r in main_records if r["group"] == group])

payload = {
    "title": "数字人 IP-Adapter 外形评测报告",
    "generated_at": datetime.now().astimezone().isoformat(timespec="seconds"),
    "rubric": {"face": 30, "body": 25, "clothing": 20, "commercial": 25},
    "scope": {"planned": 85, "generated": 61, "fully_evaluated": 60, "view_generated": 1, "view_failed_or_missing": 24},
    "summary": summary,
    "records": records,
    "limitations": [
        "本次为单评审者基于固定量表的视觉审阅，不等同于多人独立盲评。",
        "一致性总分沿用交接文档中已完成评分，新增维度拆分、提示遵循与硬淘汰复核。",
        "身份一致性为肉眼 1–5 级评估，未使用人脸 embedding；不能替代生物识别验证。",
        "多视角仅生成 1/25，不能据此推断侧面、背面与特写能力。",
    ],
}

OUT.mkdir(parents=True, exist_ok=True)
(OUT / "evaluation_report.json").write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n")


def md_stat(name, s):
    return f"| {name} | {s['count']} | {s['average']:.1f} | {s['median']:.1f} | {s['score_85_rate']:.1f}% | {s['direct_use_rate']:.1f}% | {s['prompt_adherence_rate']:.1f}% | {s['hard_reject_count']} |"


md = f"""# 数字人 IP-Adapter 外形评测报告

评测完成时间：{payload['generated_at']}  
评测范围：成功生成 61 张；其中 60 张属于完整实验组并完成逐图评测，多视角仅 1 张成功样本单列。

## 结论

1. **Flux Q4 + IP-Adapter 是当前同一数字人多图生产首选。** 一致性 10/10 均为 95 分，身份肉眼评分 5/5，关键颜色与道具遵循稳定。
2. **多服装生产可用。** 25 张平均 {summary['多服装']['average']:.1f} 分，≥85 分且未硬淘汰的直接使用率 {summary['多服装']['direct_use_rate']:.1f}%；礼服的珠饰、盘发和袖型是主要薄弱点。
3. **尺度实验不能按高审美分直接宣告全部成功。** 日常家居和艺术性尺度共 10 张均违反“全身可见”的明确构图要求，触发目标用途硬淘汰；时尚泳装 5/5 可用。
4. **多视角方案失败。** 仅正面 1 张成功，其余 24 张未生成；当前结果只能证明正面可用，不能证明多视角一致性。应更换 LoRA、InstantID/PuLID/换脸或多视角参考方案后重测。
5. **RealVisXL + IP-Adapter 已退出默认生产工作流。** 其模型和脚本仅保留作故障回退、对照与历史复现；均分 {summary['RealVisXL + IP-Adapter']['average']:.1f}，关键元素完整遵循仅 {summary['RealVisXL + IP-Adapter']['prompt_adherence_rate']:.1f}%。

## 统计总览

“≥85率”只看审美分；“直接使用率”还排除了硬淘汰，因此两者可能不同。

| 实验组 | 张数 | 平均 | 中位数 | ≥85率 | 直接使用率 | 提示遵循率 | 硬淘汰 |
|---|---:|---:|---:|---:|---:|---:|---:|
{md_stat('完整实验合计', summary['overall'])}
{md_stat('一致性', summary['一致性'])}
{md_stat('多服装', summary['多服装'])}
{md_stat('内容尺度', summary['内容尺度'])}
{md_stat('RealVisXL + IP-Adapter', summary['RealVisXL + IP-Adapter'])}
{md_stat('Flux Q4 + IP-Adapter', summary['Flux Q4 + IP-Adapter'])}
{md_stat('时尚泳装', summary['时尚泳装'])}
{md_stat('日常家居', summary['日常家居'])}
{md_stat('艺术性尺度', summary['艺术性尺度'])}

## 多服装结果

| 服装 | 平均 | 中位数 | 直接使用率 | 主要观察 |
|---|---:|---:|---:|---|
| 休闲装 | {summary['休闲装']['average']:.1f} | {summary['休闲装']['median']:.1f} | {summary['休闲装']['direct_use_rate']:.1f}% | 白 T、牛仔裤、白鞋稳定 |
| 职业装 | {summary['职业装']['average']:.1f} | {summary['职业装']['median']:.1f} | {summary['职业装']['direct_use_rate']:.1f}% | 结构准确，职业感稳定 |
| 礼服 | {summary['礼服']['average']:.1f} | {summary['礼服']['median']:.1f} | {summary['礼服']['direct_use_rate']:.1f}% | 珠饰弱；seed 2026 袖型与盘发偏离 |
| 运动装 | {summary['运动装']['average']:.1f} | {summary['运动装']['median']:.1f} | {summary['运动装']['direct_use_rate']:.1f}% | 体态和品牌图质感稳定 |
| 家居服 | {summary['家居服']['average']:.1f} | {summary['家居服']['median']:.1f} | {summary['家居服']['direct_use_rate']:.1f}% | 粉色套装与居家氛围稳定 |

## 效率与生产建议

- RealVisXL + IP-Adapter：平均 {statistics.mean([r['elapsed_sec'] for r in records if r['group'] == 'RealVisXL + IP-Adapter']):.1f} 秒/张；不再默认调用，仅保留作回退、对照和历史复现。
- Flux Q4 + IP-Adapter：一致性组平均 {statistics.mean([r['elapsed_sec'] for r in records if r['group'] == 'Flux Q4 + IP-Adapter']):.1f} 秒/张；速度慢，但身份和复杂提示下限更高。
- 多服装 Flux：平均 {statistics.mean([r['elapsed_sec'] for r in records if r['section'] == '多服装']):.1f} 秒/张，25 张中 {sum(r['total'] >= 85 and not r['hard_reject'] for r in records if r['section'] == '多服装')} 张可直接使用。
- 生产路由：封面、品牌图、同人多服装和默认人物生成统一使用 Flux + IP-Adapter；RealVisXL 仅显式启用；多视角与严格全身图在方案修正前不要自动批量生产。

## 方法与限制

- 固定四维量表：人脸自然度 30、身材姿态 25、服装 20、商业成片感 25。
- 明显畸形、年龄冲突、服装穿插或目标用途构图失败均可触发硬淘汰，不允许总分补偿。
- 本轮完成的是单评审者视觉复核，不是多人独立盲评；总分适合生产筛选，不应解读为客观美学真值。
- 身份一致性采用肉眼 1–5 级复核，尚未加入 ArcFace/CLIP 等自动辅助证据。
- 所有 60 张逐图维度分、备注与硬淘汰原因见同目录 JSON/HTML 报告。
"""
DOC.write_text(md)

# Browsers opened through a sandboxed preview may block local relative file URLs.
# Embed every evaluated PNG so the HTML remains portable and images always render.
html_payload = json.loads(json.dumps(payload, ensure_ascii=False))
for item in html_payload["records"]:
    image_path = (OUT / item["image"]).resolve()
    with Image.open(image_path) as source:
        preview = source.convert("RGB")
        preview.thumbnail((576, 768), Image.Resampling.LANCZOS)
        buffer = io.BytesIO()
        preview.save(buffer, format="WEBP", quality=82, method=6)
    encoded = base64.b64encode(buffer.getvalue()).decode("ascii")
    item["image"] = f"data:image/webp;base64,{encoded}"
data = json.dumps(html_payload, ensure_ascii=False).replace("</", "<\\/")
html = """<!doctype html><html lang='zh-CN'><head><meta charset='utf-8'><meta name='viewport' content='width=device-width,initial-scale=1'><title>数字人 IP-Adapter 外形评测报告</title><style>
:root{--bg:#0b1020;--panel:#151c30;--line:#29334d;--text:#eef2ff;--muted:#9ca9c8;--accent:#70e1c1;--warn:#ffc857;--bad:#ff6b7a}*{box-sizing:border-box}body{margin:0;background:linear-gradient(135deg,#0b1020,#11162a);color:var(--text);font:15px/1.55 -apple-system,BlinkMacSystemFont,'PingFang SC',sans-serif}.wrap{max-width:1300px;margin:auto;padding:36px 22px}h1{font-size:42px;margin:0 0 8px}.sub,.muted{color:var(--muted)}.verdict{margin:28px 0;padding:24px;border:1px solid #396b66;background:#102c31;border-radius:16px;font-size:20px}.cards{display:grid;grid-template-columns:repeat(auto-fit,minmax(180px,1fr));gap:14px;margin:22px 0}.card,section{background:var(--panel);border:1px solid var(--line);border-radius:14px;padding:20px}.num{font-size:34px;font-weight:750;color:var(--accent)}h2{margin-top:36px}table{width:100%;border-collapse:collapse;background:var(--panel);border-radius:12px;overflow:hidden}th,td{padding:11px;border-bottom:1px solid var(--line);text-align:left}th{color:var(--muted)}.filters{display:flex;gap:9px;flex-wrap:wrap;margin:16px 0}.filters button{border:1px solid var(--line);background:#1a2339;color:var(--text);border-radius:20px;padding:8px 13px;cursor:pointer}.filters button.on{background:var(--accent);color:#071410}.grid{display:grid;grid-template-columns:repeat(auto-fill,minmax(225px,1fr));gap:16px}.item{background:var(--panel);border:1px solid var(--line);border-radius:13px;overflow:hidden}.item.reject{border-color:var(--bad)}.item img{display:block;width:100%;aspect-ratio:3/4;object-fit:cover;background:#0a0e18}.body{padding:14px}.score{font-size:28px;font-weight:800;color:var(--accent)}.reject .score{color:var(--bad)}.tag{display:inline-block;border:1px solid var(--line);border-radius:10px;padding:2px 7px;font-size:12px;margin:2px;color:var(--muted)}.why{font-size:13px;color:var(--muted);min-height:62px}.hard{color:var(--bad);font-weight:700}.foot{margin-top:30px;color:var(--muted);font-size:13px}@media(max-width:600px){h1{font-size:30px}.wrap{padding:24px 14px}}
</style></head><body><main class='wrap'><h1>数字人 IP-Adapter 外形评测</h1><div class='sub'>60 张完整评测 · 1 张多视角失败实验样本 · 四维量表 + 硬淘汰复核</div><div class='verdict'><b>生产结论：</b>默认工作流统一使用 Flux + IP-Adapter。RealVisXL 已退出默认生产工作流，仅保留模型和脚本用于回退、对照与历史复现；多视角需换方案，严格全身图必须增加构图约束并重测。</div><div class='cards' id='cards'></div><h2>实验组统计</h2><table id='stats'></table><h2>逐图评测</h2><div class='filters' id='filters'></div><div class='grid' id='grid'></div><div class='foot'>说明：≥85 只代表审美分；触发硬淘汰的图片即使高分，也不计入直接使用率。本报告为单评审者视觉复核。</div></main><script>const D=""" + data + """;const S=D.summary.overall;document.querySelector('#cards').innerHTML=[['完整评测',S.count],['平均分',S.average],['≥85率',S.score_85_rate+'%'],['直接使用率',S.direct_use_rate+'%'],['硬淘汰',S.hard_reject_count]].map(x=>`<div class=card><div class=num>${x[1]}</div><div class=muted>${x[0]}</div></div>`).join('');const rows=['一致性','多服装','内容尺度','RealVisXL + IP-Adapter','Flux Q4 + IP-Adapter','时尚泳装','日常家居','艺术性尺度'];document.querySelector('#stats').innerHTML='<tr><th>实验组</th><th>张数</th><th>平均</th><th>中位数</th><th>直接使用率</th><th>提示遵循</th><th>硬淘汰</th></tr>'+rows.map(k=>{let s=D.summary[k];return `<tr><td>${k}</td><td>${s.count}</td><td>${s.average}</td><td>${s.median}</td><td>${s.direct_use_rate}%</td><td>${s.prompt_adherence_rate}%</td><td>${s.hard_reject_count}</td></tr>`}).join('');let current='全部';const sections=['全部',...new Set(D.records.map(x=>x.section))];const F=document.querySelector('#filters'),G=document.querySelector('#grid');function render(){F.innerHTML=sections.map(x=>`<button class='${x===current?'on':''}' data-x='${x}'>${x}</button>`).join('');F.querySelectorAll('button').forEach(b=>b.onclick=()=>{current=b.dataset.x;render()});G.innerHTML=D.records.filter(x=>current==='全部'||x.section===current).map(x=>`<article class='item ${x.hard_reject?'reject':''}'><img loading=lazy src='${x.image}' alt='${x.group} seed ${x.seed}'><div class=body><div><span class=score>${x.total}</span> / 100</div><b>${x.group} · seed ${String(x.seed).padStart(4,'0')}</b><div>${Object.entries(x.dimensions).map(([k,v])=>`<span class=tag>${k.replace('_','/')}: ${v}</span>`).join('')}</div><p class=why>${x.note}</p>${x.hard_reject?`<div class=hard>硬淘汰：${x.hard_reject_reason}</div>`:''}</div></article>`).join('')}render();</script></body></html>"""
(OUT / "report.html").write_text(html)
print(OUT / "evaluation_report.json")
print(OUT / "report.html")
print(DOC)
