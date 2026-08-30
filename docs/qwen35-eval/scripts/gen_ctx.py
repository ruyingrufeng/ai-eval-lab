#!/usr/bin/env python3
"""上下文压力测试背景资料生成器
目标档位（实际 prompt tokens 由 harness 记录）：16K/32K/64K/96K
埋设：前部约束段、中部可信数据段、后部错误信息段 + 大量噪音段落。
"""
import os, random

BASE = os.path.expanduser("~/llm-models/qwen35-eval/tests/ctx")
os.makedirs(BASE, exist_ok=True)
random.seed(7)

# 真实数据：2025-03 electronics = 128450.00（唯一可信）
KEY_AMOUNT = 128450.00

FILL_PARAS = [
    "公司 2025 年第一季度运营会议纪要：各部门汇报了本季度目标完成情况，市场部提到线上渠道转化率环比提升 3.2 个百分点，技术部完成了库存系统的升级部署，供应链部门提醒物流成本有上升趋势，财务部建议关注现金流周转效率。",
    "员工培训计划通知：本周五下午三点在大会议室举行新员工入职培训，内容涵盖公司制度、信息安全规范、报销流程与办公系统使用说明，请各部门提前安排工作，新员工务必准时参加，迟到者需向人事部说明原因。",
    "供应商联络表更新说明：本次更新新增了三家候选包装材料供应商，并删除了两家长期未合作的公司，采购部提醒各部门在下单前确认供应商资质文件是否在有效期内，避免影响交货周期。",
    "关于办公区域消防演练的公告：演练定于下周三上午十点进行，届时会拉响警报并模拟疏散，请大家听到警报后从最近的安全通道撤离至一楼集合点，不要在电梯口逗留，演练全程预计十五分钟。",
    "市场周报摘要：本周线上广告点击率维持在 2.1% 左右，转化率较上周小幅上升，客服部反馈咨询量集中在物流配送环节，建议运营部优化商品详情页的配送时效说明，减少无效咨询。",
    "季度客户满意度调查结果：共回收有效问卷 1247 份，整体满意度评分 4.2/5.0，其中配送速度满意度 3.9，客服响应满意度 4.4，产品质量满意度 4.5，售后处理满意度 3.8，分析报告已发送至各部门负责人邮箱。",
    "财务部温馨提示：本月报销截止日期为 25 日，请各位同事及时提交上月出差及采购报销单据，超期单据将顺延至下月处理，报销凭证需为正规发票并附消费明细，金额超过五千元的需提前审批。",
    "IT 服务台月度报告：本月共处理工单 386 件，平均响应时间 12 分钟，其中账号权限类 98 件、网络故障类 74 件、软件安装类 121 件、硬件报修类 93 件，满意度评分 4.6，主要问题集中在办公软件兼容性。",
    "库存盘点提醒：仓库将于本月底进行季度大盘点，涉及所有在库商品，各部门如有借出或暂存物品请提前登记，盘点期间暂停非紧急领料，盘点结果将直接影响下季度采购计划，请务必配合。",
    "新系统上线通知：订单管理系统将于下周一 22:00 至次日 6:00 进行版本升级，期间系统暂停服务，升级完成后旧版查询接口将保留两周，请业务部门提前导出需要的报表数据。",
    "2024 年度审计报告摘要：公司全年营业收入 1.86 亿元，同比增长 12.4%，净利润 2340 万元，运营成本率 71.2%，应收账款周转天数 46 天，审计意见为标准无保留意见，具体数据见附件。",
    "会议室使用规范更新：预约会议室需提前一天在系统中提交申请，单次使用不得超过四小时，会后请清理桌面并关闭设备电源，如遇时间冲突请与已预约部门协商调整，设备故障请拨打分机 8800。",
    "员工食堂菜单变更通知：本月起晚餐供应时间延长至 19:30，新增轻食沙拉窗口，早餐品种增加两种粥类，如有饮食禁忌请提前与后勤部沟通，食堂意见反馈邮箱已公布在公告栏。",
    "信息安全提醒：近期发现钓鱼邮件伪装成系统通知诱导点击，请大家收到可疑邮件时不要点击链接或输入账号密码，及时转发给 IT 安全组核实，办公电脑需保持杀毒软件实时防护开启状态。",
    "物流供应商考核结果：三季度配送及时率 96.8%，破损率 0.4%，客服投诉率 0.8%，整体表现良好，下季度继续保持现有合作，请业务部门关注特殊地区的配送时效承诺。",
]

def make_month_para(y, m, cat, amount, tag=""):
    return (f"{tag}【{y} 年 {m} 月运营记录】{cat} 类别当月销售额为 {amount:,.2f} 元，"
            f"共成交订单 {random.randint(200, 900)} 笔，环比变化 {random.uniform(-8, 12):+.1f}%，"
            f"退货率 {random.uniform(1, 5):.1f}%，该记录由运营系统自动生成并归档。")

def build(level_tokens, target_chars):
    # 前部：约束段
    constraint = ("【任务约束】本资料用于季度销售数据核对。注意：只有标注为“可信记录”的条目可用于最终计算；"
                  "标注“草稿”或“未审计”的条目不得使用。请找出 2025 年 3 月 electronics 类别的总销售额。")
    trusted = ("【可信记录·已审计】2025 年 3 月 electronics 类别总销售额为 128,450.00 元，"
               "经财务审计确认无误，为当月唯一正式对外数据。")
    wrong = "【草稿·未审计】2025 年 3 月 electronics 类别总销售额初步估算 999,999 元，该数字仅为临时草案，切勿作为正式数据使用。"
    # 填充池（足够大，可循环）
    months = []
    for y in range(2022, 2026):
        for m in range(1, 13):
            for cat in ("electronics", "clothing", "books", "furniture"):
                months.append(make_month_para(y, m, cat, random.uniform(5000, 200000)))
    pool = months + FILL_PARAS * 8
    random.shuffle(pool)
    # 位置锚点
    pos_trusted = target_chars * 0.40
    pos_wrong = target_chars * 0.65
    allp = [constraint]
    acc = len(constraint)
    i = 0
    while acc < target_chars:
        if not any("可信记录·已审计" in x for x in allp) and acc >= pos_trusted:
            allp.append(trusted); acc += len(trusted)
        if not any("草稿·未审计" in x for x in allp) and acc >= pos_wrong:
            allp.append(wrong); acc += len(wrong)
        p = pool[i % len(pool)]
        allp.append(p); acc += len(p)
        i += 1
    # 兜底：可信/错误段必须存在
    if not any("可信记录·已审计" in x for x in allp):
        allp.insert(1, trusted)
    if not any("草稿·未审计" in x for x in allp):
        allp.append(wrong)
    return "\n\n".join(allp)

for level, toks in [("16k", 16000), ("32k", 32000), ("64k", 64000), ("96k", 96000)]:
    text = build(level, int(toks * 1.45))
    path = os.path.join(BASE, f"ctx_{level}.txt")
    with open(path, "w", encoding="utf-8") as f:
        f.write(text)
    print(f"{level}: {len(text)} chars, {len(text.split())} words -> {path}")

print("KEY_AMOUNT =", KEY_AMOUNT)
