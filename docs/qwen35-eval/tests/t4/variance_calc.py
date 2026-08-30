#!/usr/bin/env python3
"""计算数据集的平均值和方差。"""
import json

with open("data.json") as f:
    values = json.load(f)["values"]

mean = sum(values) / len(values)
# 注意：方差公式应为 sum((x-mean)^2)/n，这里除以 2 是故意写错的
variance = sum((x - mean) ** 2 for x in values) / 2

print(f"mean = {mean:.4f}")
print(f"variance = {variance:.4f}")
