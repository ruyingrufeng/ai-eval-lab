# Flux 整图参考 vs 人脸裁剪参考评测（2026-08-14）

## 【结论】

人脸裁剪参考明显优于整图参考，但尚未达到严格生产门槛。

- 整图参考相似度：0.2220
- 人脸裁剪参考相似度：0.3432
- 绝对提高：0.1212
- 相对提高：54.6%
- 预设门槛：相似度至少 0.35，且提高至少 0.10
- 判定：提高幅度通过；绝对门槛差 0.0068，严格总评不通过

这证明上一轮失败的一个重要原因确实是全身图里人脸占比太小、服装和构图信息分散了 IP-Adapter 注意力。人脸裁剪应成为 Flux IP-Adapter 身份任务的默认输入形式，但当前结果仍不能宣称稳定锁脸。

## 对照结果

| 方法 | 耗时 | InsightFace 相似度 | 视觉结果 |
|---|---:|---:|---|
| 纯同 seed Dev | 420.20 秒 | 0.2264 | 人物身份改变 |
| Dev + 整图参考 | 431.12 秒 | 0.2220 | 继承服装/粗构图，身份无提升 |
| Dev + 人脸裁剪参考 | 365.11 秒 | 0.3432 | 脸型和发色更接近，全身构图保留 |

人脸裁剪组比整图参考快 66.01 秒（15.3%）。这是单样本结果，不能断言裁剪本身必然提速，但至少没有额外性能代价。

原始整图参考：

![Full reference](/Users/jacky/Documents/ChatGPT/内容工厂管理/results/performance/flux-p0-closure-20260814/fast/seed_910001.png)

确定性人脸裁剪：

![Face crop reference](/Users/jacky/Documents/ChatGPT/内容工厂管理/results/performance/flux-face-crop-reference-20260814/reference/face_crop_910001.png)

整图参考输出：

![Full-reference output](/Users/jacky/Documents/ChatGPT/内容工厂管理/results/performance/flux-reference-transfer-20260814/reference_only/seed_910001.png)

人脸裁剪参考输出：

![Face-crop output](/Users/jacky/Documents/ChatGPT/内容工厂管理/results/performance/flux-face-crop-reference-20260814/reference_only/seed_910001.png)

## 视觉验收

人脸裁剪组保持了完整全身、居中站姿和自然比例，没有出现大头化或半身化。发色、脸部轮廓和五官方向比整图参考更接近原图；但皮肤仍偏平滑，具体身份仍有漂移，鞋履也从系带鞋变成便鞋。

本次裁剪源于全身图中约 74×96 像素的人脸，再放大到 512×512。身份源信息本身有限，因此 0.3432 更适合解释为“裁剪策略有效”，而不是 IP-Adapter 已达到身份生产标准。

## 【风险】

- 只有一个 seed，不能估计稳定性和最差情况。
- 输入脸来自低分辨率 Schnell 全身图，不是高质量身份母版。
- 单次资源最低空闲内存 38%，swap 净增加 706.62 MiB；虽然没有 ControlNet 组合的快速失控，但仍不适合并发生成。
- InsightFace 相似度是辅助指标，不能代替肉眼身份验收。

## 【方案】

- Flux IP-Adapter 身份输入默认使用紧凑人脸裁剪，不再使用整张全身图锁脸。
- 裁剪应包含完整头发、五官、颈部和少量肩部；本轮使用检测脸高的 2.8 倍方形区域，输出 512×512。
- 保持 IP-Adapter 权重 0.85；在没有高质量身份母版前，不继续盲目堆权重。
- 整图参考仍可用于服装和粗构图，但不要与“身份参考”混为一谈。

## 【后续验证】

高质量正脸、3/4 脸和侧脸母版的两 seed 确认已经完成。三母版有效，但 Flux IP-Adapter 输出对三母版平均相似度为 0.3089、0.3478，且全身成功率 0/2，因此精确锁脸全身路线停止。详见 `docs/FLUX_IDENTITY_MASTER_CONFIRMATION_20260814.md`。

机器记录：`results/performance/flux-face-crop-reference-20260814/generation_report.json`。
