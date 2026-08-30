# Flux 候选图参考传递评测（2026-08-14）

## 【结论】

整张 Schnell 候选图作为 FLUX Dev IP-Adapter 参考，可以明显继承服装色系、居中站姿和整体轮廓，但不能锁定人物身份。InsightFace 相似度没有提高：纯同 seed 为 0.2264，参考图约束为 0.2220。

`IP-Adapter + Flux OpenPose ControlNet` 组合不适合进入当前 32 GB 机器的默认工作流。加载 ControlNet 时 swap 在 10 秒内最多增加 2,426.06 MiB，整段从 12,047.38 MiB 增至最高 16,007.31 MiB，因此按照预设停止条件在第 2/20 步中止，没有成片、不得评分。

## 对照结果

| 方法 | 耗时 | 人脸相似度 | 结果 |
|---|---:|---:|---|
| 纯同 seed Dev | 420.20 秒 | 0.2264 | 身份、服装均改变 |
| Dev + 整图参考（IP-Adapter 0.85） | 431.12 秒 | 0.2220 | 服装和粗构图更接近，身份无提升 |
| Dev + 整图参考 + OpenPose | 未完成 | 不可评分 | 快速 swap 增长，第 2/20 步安全中止 |

参考候选：

![Schnell reference](/Users/jacky/Documents/ChatGPT/内容工厂管理/results/performance/flux-p0-closure-20260814/fast/seed_910001.png)

纯同 seed Dev：

![Same-seed Dev](/Users/jacky/Documents/ChatGPT/内容工厂管理/results/performance/flux-p0-closure-20260814/quality/seed_910001.png)

整图参考 Dev：

![Reference-only Dev](/Users/jacky/Documents/ChatGPT/内容工厂管理/results/performance/flux-reference-transfer-20260814/reference_only/seed_910001.png)

从候选图提取的姿态证据：

![Extracted OpenPose](/Users/jacky/Documents/ChatGPT/内容工厂管理/results/performance/flux-reference-transfer-20260814/reference_pose/pose_910001.png)

本次已保存的骨架是中止前生成的 1024×1365 版本；运行器随后已把预处理基准修正为 768，使未来输出严格匹配 768×1024 画布。该修正尚未重新生成成片。

## 【风险】

- 当前 Flux IP-Adapter 的“整图参考”更像外观/风格参考，不是可靠锁脸工具。
- IP-Adapter、Flux Dev、T5/CLIP 与 4 GB ControlNet 同时驻留会造成明显内存与 swap 压力。
- OpenPose 只约束姿态，不能改善身份；此前评测还出现过脚部伪影。
- 本次姿态组没有成片，不能外推其画质，只能确认当前组合的资源风险。

## 【方案】

- 默认候选→成片：Schnell 选方向，Dev 重写提示词；若需要服装和粗构图延续，可按需使用整图 IP-Adapter。
- 不把 `IP-Adapter + OpenPose` 组合加入默认链；精确姿态任务单独使用 OpenPose，并避免与身份控制同时叠加。
- 身份一致性不能继续依赖整张全身参考。下一次应比较“整图参考”与“人脸裁剪参考”，或改用专门的 FaceID/InstantID/LoRA/换脸链。
- 运行器已修复旧 `flux_ref.png` 被误复用的问题，并把姿态预处理分辨率修正为与输出匹配的 768×1024。

## 【后续验证】

整图参考与人脸裁剪参考 A/B 已完成：人脸裁剪相似度从 0.2220 提高到 0.3432，但严格门槛 0.35 未通过。详见 `docs/FLUX_FACE_CROP_REFERENCE_EVALUATION_20260814.md`。

机器可读记录：`results/performance/flux-reference-transfer-20260814/generation_report.json`。
