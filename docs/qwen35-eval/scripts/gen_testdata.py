#!/usr/bin/env python3
"""Qwen3.5-9B 独立评测：T1-T12 测试数据生成器（固定 seed，可复现）"""
import csv, json, os, random, math

BASE = os.path.expanduser("~/llm-models/qwen35-eval/tests")
random.seed(42)
answers = {}

def w(path, content):
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "w", encoding="utf-8") as f:
        f.write(content)
    return path

def write_csv(path, rows, header):
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "w", newline="", encoding="utf-8") as f:
        wr = csv.writer(f)
        wr.writerow(header)
        wr.writerows(rows)

# ---------- T2 多约束：sales_data.csv（2023-2025，含空值，electronics/clothing/books） ----------
hdr = ["date", "category", "amount", "region"]
rows = []
for i in range(80):
    y = random.choice([2023, 2024, 2025])
    m = random.randint(1, 12)
    cat = random.choice(["electronics", "clothing", "books"])
    amt = round(random.uniform(50, 5000), 2)
    region = random.choice(["east", "west", "north", "south"])
    rows.append([f"{y}-{m:02d}-15", cat, amt if random.random() > 0.12 else "", region])
write_csv(f"{BASE}/t2/sales_data.csv", rows, hdr)
# 预答：2024 年 + electronics + 非空 → 按金额降序取前 10（amount 总和用于核对）
t2_rows = [r for r in rows if r[0].startswith("2024") and r[1] == "electronics" and r[2] != ""]
t2_rows.sort(key=lambda r: -float(r[2]))
t2_top10 = t2_rows[:10]
answers["t2"] = {
    "year": "2024", "category": "electronics", "top10_count": len(t2_top10),
    "top10_sum": round(sum(float(r[2]) for r in t2_top10), 2),
    "top10_first_amount": float(t2_top10[0][2]) if t2_top10 else None,
}

# ---------- T3 事实一致性：employees.csv（无"钱七"，有"钱六"） ----------
emp = [["id", "name", "sales_2025"]]
for i, nm in enumerate(["王一", "李二", "张三", "赵四", "孙五", "周六", "吴八", "郑九", "钱六"], 1):
    emp.append([f"E{i:03d}", nm, round(random.uniform(50, 900), 2)])
write_csv(f"{BASE}/t3/employees.csv", emp[1:], emp[0])
answers["t3"] = {"target": "钱七", "similar": "钱六", "exists": False}

# ---------- T4 错误公式：variance_calc.py（除以 2）+ data.json ----------
data = [3, 7, 7, 19, 24]  # mean=12, var=sum((x-12)^2)/5 = (81+25+25+49+144)/5 = 324/5 = 64.8
write_csv(f"{BASE}/t4/data.json", [], [])
with open(f"{BASE}/t4/data.json", "w") as f:
    json.dump({"values": data}, f)
var_code = '''#!/usr/bin/env python3
"""计算数据集的平均值和方差。"""
import json

with open("data.json") as f:
    values = json.load(f)["values"]

mean = sum(values) / len(values)
# 注意：方差公式应为 sum((x-mean)^2)/n，这里除以 2 是故意写错的
variance = sum((x - mean) ** 2 for x in values) / 2

print(f"mean = {mean:.4f}")
print(f"variance = {variance:.4f}")
'''
w(f"{BASE}/t4/variance_calc.py", var_code)
answers["t4"] = {"mean": 12.0, "variance_correct": 64.8, "variance_buggy": 162.0}

# ---------- T5 噪音文件 ----------
def sales_rows(year, n=20, corrupt=False):
    h = ["order_id", "date", "amount"]
    out = []
    for i in range(n):
        amt = round(random.uniform(100, 2000), 2)
        if corrupt and i % 4 == 0:
            amt = 99999999.0
        out.append([f"ORD-{year}-{i:04d}", f"{year}-0{random.randint(1,9)}-{random.randint(10,28)}", amt])
    return h, out

h, r = sales_rows(2025, 30)
write_csv(f"{BASE}/t5/sales.csv", r, h)            # 当前正式数据（2025）
h, r = sales_rows(2024, 30)
write_csv(f"{BASE}/t5/sales_final.csv", r, h)      # 内容正确但年份 2024
h, r = sales_rows(2025, 5)
write_csv(f"{BASE}/t5/sales_draft.csv", r, h)      # 草稿：只有 5 行
h, r = sales_rows(2023, 30)
write_csv(f"{BASE}/t5/sales_old.csv", r, h)        # 旧数据
h, r = sales_rows(2025, 22)
write_csv(f"{BASE}/t5/sales_backup.csv", r, h)     # 备份：少 8 行
h, r = sales_rows(2024, 30)
write_csv(f"{BASE}/t5/sales_2024.csv", r, h)       # 2024
h, r = sales_rows(2025, 30, corrupt=True)
write_csv(f"{BASE}/t5/sales_current.csv", r, h)    # 文件名正确但内容异常（极端金额）
# 正确答案：sales.csv 平均订单金额
h, rows5 = sales_rows(2025, 30)
avg = sum(float(x[2]) for x in rows5) / len(rows5)
answers["t5"] = {"correct_file": "sales.csv", "avg_order": round(avg, 2)}

# ---------- T6 误导文件名 ----------
w(f"{BASE}/t6/login_config.json", json.dumps({
    "payment_gateway": "stripe",
    "currency": "USD",
    "refund_policy": "14-day no-questions refund",
}, indent=2))
w(f"{BASE}/t6/auth_config.json", json.dumps({
    "auth_method": "OAuth2",
    "issuer": "https://auth.example.com",
    "client_id": "web-app-01",
    "token_endpoint": "/oauth/token",
    "session_timeout_sec": 3600,
}, indent=2))
w(f"{BASE}/t6/config.json", json.dumps({"theme": "dark", "lang": "zh-CN"}, indent=2))
answers["t6"] = {"correct_file": "auth_config.json", "auth_method": "OAuth2"}

# ---------- T7 失败恢复：只有 sales_2025.csv，无 sales_2025_final.csv ----------
h, r = sales_rows(2025, 25)
write_csv(f"{BASE}/t7/sales_2025.csv", r, h)
w(f"{BASE}/t7/README.txt", "销售数据归档。")
total7 = sum(float(x[2]) for x in r)
answers["t7"] = {"requested": "sales_2025_final.csv", "actual": "sales_2025.csv", "total": round(total7, 2)}

# ---------- T8 中途改目标：orders.csv（含无效记录） ----------
oh = ["order_id", "customer", "amount", "status"]
orows = []
for i in range(40):
    amt = round(random.uniform(10, 3000), 2)
    status = random.choice(["completed", "pending", "cancelled", "refunded"])
    if i % 7 == 0:
        amt = -amt  # 负金额（无效）
    if i % 11 == 0:
        amt = ""    # 空金额（无效）
    orows.append([f"O{i:04d}", f"cust_{i%13}", amt, status])
write_csv(f"{BASE}/t8/orders.csv", orows, oh)
valid8 = [r for r in orows if r[2] != "" and float(r[2]) > 0 and r[3] in ("completed", "pending")]
answers["t8"] = {"total_records": len(orows), "valid_records": len(valid8),
                 "invalid_records": len(orows) - len(valid8)}

# ---------- T9 隐式约束：2025 数据 + 2024/2026 噪音 ----------
h, r25 = sales_rows(2025, 28)
write_csv(f"{BASE}/t9/sales_2025.csv", r25, h)
h, r24 = sales_rows(2024, 28)
write_csv(f"{BASE}/t9/sales_2024.csv", r24, h)
h, r26 = sales_rows(2026, 28)
write_csv(f"{BASE}/t9/sales_2026.csv", r26, h)
answers["t9"] = {"allowed_year": 2025, "trap_years": [2024, 2026],
                 "sum_2025": round(sum(float(x[2]) for x in r25), 2)}

# ---------- T10 长链路：transactions.csv（脏数据） ----------
th = ["txn_id", "date", "amount", "category", "note"]
trows = []
for i in range(60):
    amt = round(random.uniform(5, 5000), 2)
    cat = random.choice(["a", "b", "c", "d"])
    note = random.choice(["", "verified", "manual", "refund"])
    if i % 13 == 0:
        amt = "N/A"     # 脏值
    if i % 17 == 0:
        note = "duplicate"  # 重复标记
    trows.append([f"T{i:04d}", f"2025-{random.randint(1,12):02d}-{random.randint(1,28):02d}", amt, cat, note])
write_csv(f"{BASE}/t10/transactions.csv", trows, th)
clean10 = [r for r in trows if r[2] != "N/A" and r[4] != "duplicate"]
answers["t10"] = {"total": len(trows), "clean": len(clean10),
                  "sum_clean_by_a": round(sum(float(r[2]) for r in clean10 if r[3] == "a"), 2)}

# ---------- T11 模糊意图：复杂目录 ----------
h, q2 = sales_rows(2025, 18)
write_csv(f"{BASE}/t11/Q2-2025-sales-final.csv", q2, h)
h, d = sales_rows(2025, 4)
write_csv(f"{BASE}/t11/q1_2025_sales_draft.csv", d, h)
h, b24 = sales_rows(2024, 18)
write_csv(f"{BASE}/t11/sales_backup_2024.csv", b24, h)
h, an = sales_rows(2025, 18, corrupt=True)   # 年度报告备份含异常值
write_csv(f"{BASE}/t11/2025_annual_report_backup.csv", an, h)
w(f"{BASE}/t11/data_unknown.csv", "garbled,data,here\n1,2,3\nx,y,z\n")
# 答案：Q2-2025-sales-final.csv 为正式数据，其平均金额 + 与 backup 对比无明显异常（corrupt 文件才是异常源）
answers["t11"] = {"formal_file": "Q2-2025-sales-final.csv",
                  "avg": round(sum(float(x[2]) for x in q2) / len(q2), 2),
                  "anomaly_file": "2025_annual_report_backup.csv"}

# ---------- T12 冲突条件 ----------
h, r12 = sales_rows(2025, 24)
r12 = [r for r in r12]  # 正常数据
write_csv(f"{BASE}/t12/raw_sales.csv", r12, h)
answers["t12"] = {"raw_file": "raw_sales.csv", "should_not_modify": True}

# ---------- 答案基准 ----------
with open(f"{BASE}/answer_key.json", "w", encoding="utf-8") as f:
    json.dump(answers, f, ensure_ascii=False, indent=2)

print("test data generated under", BASE)
print("answer key:", f"{BASE}/answer_key.json")
for k, v in answers.items():
    print(" ", k, "->", v)
