# 选型决策日志

## 2026-08-15：修正Qwen3.8-27B的SillyTavern结论，适合但暂不替换Fable

- 此前以一篇854字长文和五轮角色测试写成的“不适合SillyTavern”结论证据不足；本轮以相同参数、种子和64K单槽，对Qwen3.6-27B Fable与Qwen3.8-27B各跑26轮。
- 三篇长文平均中文字为1658/1604（3.6/3.8）；3.8同题可写到1965字，1500字刻度写到1513字。因此撤回“3.8写不长”，改为“长度能力足够但波动较大”。
- 普通角色轮均148/205字，成人轮均218/316字，3.8分别长约38%/45%；它不是回复更短，而是短轮更容易超出角色卡上限。
- Fable在双人冲突、人物关系、句子张力和自然角色声音上更好；3.8更愿展开，但更常出现括号舞台动作、通用强情绪句式、突然解释背景及戏剧化新增设定。
- 角色与世界书均非零错误：3.6出现用户动作接管、门锁和银币债务错误；3.8没有用户动作接管且银币修正更准，但出现门锁、左手旧伤与椅子处理矛盾，并编造更多共同历史/家族设定。
- 成人四轮两者均不拒绝且撤回同意后停止；3.6更直白紧凑且立即退出，3.8更长但偏说明式，并在恢复轮重复已完成的退出状态。
- 3.8角色轮完整耗时约为3.6的1.81倍，长文约1.43倍；当前文件量化不同，倍率只代表本机实际体验。
- 决策：8086继续使用3.6 Fable单槽64K；3.8改列为“适合ST但暂不替换”的按需候选，并继续承担一体化视觉/本地Agent研究。报告：`docs/reports/qwen36_vs_qwen38_st_20260815/report.html`。

## 2026-08-15：27B生产配置改为SillyTavern专用单槽64K

- 用户取消Hermes与SillyTavern共享本地模型的双槽需求；27B只供SillyTavern单会话使用。
- `qwen3.6-27b-fable` 从总上下文131072、parallel 2改为总上下文65536、parallel 1；保持单会话可用上下文64K不变，释放原第二槽的KV缓存预算。
- 35B因短上下文加载已占约21.2GiB，且无法与7B视觉模型可靠共存，不进入Hermes；30B实际上下文上限约40960，也不进入Hermes。
- 当前本地Hermes没有候选，继续使用现有云端模型；27B单槽64K只服务SillyTavern。历史双槽并发测试仍作为历史证据保留，不改写原始报告。

## 2026-08-14：35B单槽受控业务流程成为重要任务默认

- 35B单槽64K用与27B相同的事实表、内容策略、提纲三步完成对照，3/3步骤与全部硬校验通过，总耗时37.649秒。
- 27B双槽并发业务线同三步耗时419.79秒；35B生产路由观测约快11.1倍。该倍率包含27B并发负载差异，不能写成纯模型速度倍率。
- 35B输出1552 tokens，27B输出1625 tokens，只少约4.5%；速度收益不是明显缩短输出造成。
- 两者均9/9事实、策略5/5部分、提纲7/7类。35B策略层级更清楚，27B检查清单更细；各有1处轻微资料外建议，单样本只支持35B质量至少相当，不支持全面质量碾压。
- 35B最低可用内存19%、swap净变化0；运行只有8个5秒样本，不替代长时间稳定性测试。
- 路由定稿：35B单槽独占用于重要方案、最终稿和快速受控业务任务；27B双槽用于必须同时保留两个64K会话的并行常驻后台任务；30B退出主候选。
- 报告：`docs/reports/controlled_business_model_comparison_20260814/report.html`。

## 2026-08-14：27B双64K并发通过，保留为常驻后台候选

- 27B保持总上下文131072、parallel 2、每槽65536的真实配置，同时运行外部编排业务三步与普通/成人各三轮对话。
- 业务3/3步骤通过、9/9事实完整；对话6/6成功；没有请求失败、上下文串线或隔离标识回显。
- 普通/成人对话平均首字3.236/4.363秒，均达到“3秒或历史单跑2倍”门槛；完整长输出仍慢，业务三步合计419.79秒。
- 84个资源样本最低可用内存15%，swap净变化−40MiB，红色内存样本0；本轮资源门禁通过。
- 普通对话长度0/3达到60字下限，因此“部署并发通过”不等于“对话质量默认”。27B保留双槽常驻后台候选；35B仍为卸载27B后的单槽独占质量档。
- 外部系统拆步、检查和结束的路线通过；不得恢复让模型自行管理完整Hermes工具循环。下一步按同一三步资料跑35B单槽质量对照。
- 专项报告：`docs/reports/dual_slot_27b_evaluation_20260814/report.html`；业务总报告已同步更新。

## 2026-08-14：27B按双64K并行候选评测，35B改为独占质量档

- 27B总上下文131072、并行槽位2是明确的生产架构：Hermes与SillyTavern各占64K；Hermes最低要求64K，不能通过降上下文或取消第二槽来优化测试结果。
- 27B定位改为双槽并行常驻候选；35B只作为卸载27B后的单槽独占质量档，不作为双槽默认替代；30B退出主路由。
- 已有27B双64K预检出现最低8%空闲内存与约1566MiB swap增长，禁止再与Flux默认共存；但两个文本槽位同时活跃仍需正式测试。
- 下一轮优先测试27B真实双槽：受控分步Hermes业务任务与SillyTavern普通/成人对话同时运行，并记录延迟、完成度、串线、内存压力和swap。
- 只有27B双槽测试完成后，才运行35B单槽同资料质量对照。

## 2026-08-14：正式评测报告默认改为自包含 HTML

- 后续正式评测必须输出 `report.html` 作为主交付物；Markdown只保留为源报告、方法说明或交接附件。
- HTML从可复核的机器数据/`artifact.json`生成，包含结论、证据、限制和下一步，并验证桌面与窄屏布局。
- 敏感逐轮原文不得嵌入HTML，只展示脱敏指标与人工审计结论。
- 首份统一报告：`docs/reports/sillytavern_evaluation_20260814/report.html`。

## 2026-08-14：35B 成人 12 轮状态通过，但写作指令未全过

- 修正版12轮中，安全套流转、不肛交边界、慢且浅、安全词停止、暂停保持、重新同意和最终状态4/4均通过；平均首字0.489秒、单轮2.950秒。
- 长度仅1/12符合140–280字，双方轮流口交也只完成一方，因此不记为完整通过。
- 首跑含安全套状态题目矛盾，已保留为无效证据，不纳入结论；修正版自动词典三处假阴性由独立人工审计纠正，原始结果未覆盖。
- 最佳实践：关键成人状态用外部结构化状态块与同意状态机管理；长度改用段落/句数约束或接受120–180字自然区间。
- 末轮只有约1,800 prompt tokens，16K/32K长上下文仍未验证。报告：`docs/SILLYTAVERN_ADULT_CONTINUITY_EVALUATION_20260814.md`。

## 2026-08-14：SillyTavern 成人直白内容仍选 35B 调参档

- 合法虚构成年人四轮专项中，35B和27B自动硬门禁通过；35B热状态平均单轮4.673秒，连续性与可控性更均衡，继续作为成人默认候选。
- 27B用词更直白，但平均单轮29.819秒，并出现减速后又加速的同轮矛盾，只保留露骨文风对照价值。
- 30B Abliterated 平均单轮1.992秒，但直白词覆盖失败且四轮全部过短；“无审查”名称不等于直白内容能力。
- “无限制”不作为承诺或验收项；允许范围是虚构、明确成年、自愿内容，硬排除未成年人/年龄不明、强迫、乱伦、真人色情化、偷拍和性暴力。
- 敏感逐轮输出只保存在被 Git 排除的本地 `results/`；报告：`docs/SILLYTAVERN_ADULT_EXPLICIT_EVALUATION_20260814.md`。

## 2026-08-14：SillyTavern 首轮默认候选为 35B 调参档

- 五轮中性成年角色基线中，35B默认档和调参档均通过硬门禁；调参档平均单轮2.459秒、普通记忆3/3、过敏记忆通过、长度5/5，且比原默认档更紧凑。
- 推荐参数：temperature 0.8、top_p 0.95、min_p 0.05、repetition penalty 1.05；角色卡补充关键事实不得擅自补全、不得从健康信息推断心理状态、避免过激反应。
- 30B平均单轮0.903秒，但长度0/5且正式复跑漏掉过敏信息，仅保留极速短聊实验价值；实际上下文不得高于40960。
- 27B平均单轮7.403秒、普通记忆1/3，不进入默认路由。
- 本轮没有修改用户现有 SillyTavern 设置。长上下文、世界书优先级、跨会话状态和边界专项仍待验证。
- 报告：`docs/SILLYTAVERN_MODEL_EVALUATION_20260814.md`。

## 2026-08-14：30B / 35B 仍未通过内容增长 Agent 闸门

- 独立服务解决了原来的上下文配置阻塞：30B实际上限40960，35B为65536。
- 两者在180秒内均生成了三项要求文件并保留9项事实，但 Hermes 持续工具循环、没有最终答复，均以超时退出，严格闸门失败。
- 35B产物质量最好；这只支持语言质量排序，不足以批准完整 Agent 默认路由。
- 下一步优先修复/替换编排完成协议，再复测同一闸门；在正常退出前不运行完整四阶段。
- 报告：`docs/CONTENT_GROWTH_AGENT_EVALUATION_20260814.md`。

## 2026-08-14：语言模型改按真实业务 Agent 场景分项评测

- 核心用途收拢为三条工作流：内容增长、研究到决策、访谈到洞察；避免十余个零散场景重复评测。
- 代码、数据计算作为执行工具，PPT、网页与报告作为交付形式嵌入工作流；不计算跨工作流笼统总分。
- Hermes Agent + Qwen3.6-27B-Fable 的三道技术题仅降级为工具链冒烟：首次 2/3，不能外推业务能力。
- 数值型报告默认改成“确定性脚本生成 JSON 真值，Agent 负责解释，外部 checker 复核”。
- Qwen3-30B 当前 16K 服务配置低于 Hermes 的 64K 要求；只取得一个有效质量失败样本，不能记为完整 0/3。
- 第一批正式业务评测控制在一小时：用同一案例跑完整内容增长闭环，先测 27B。
- 计划：`docs/AGENT_BUSINESS_EVALUATION_PLAN_20260814.md`；工具链冒烟：`docs/AGENT_LLM_EVALUATION_20260814.md`。

### 内容增长闭环首测：27B 当前 Agent 路线停止

- 第一阶段首次与增量恢复均在600秒超时；两次都只完成事实表和内容策略，始终缺少提纲。
- 已完成内容9/9事实保留、无编造，策略基本可用；失败点是任务推进、收尾、增量恢复和效率，而不是完全不懂中文资料。
- 后三阶段按止损规则未运行；不得把本轮外推成“27B纯写作质量失败”。
- 27B 不进入内容增长默认 Agent。下一模型必须先通过“3项产物完整、事实正确、180秒内退出”的第一阶段闸门。
- 报告：`docs/CONTENT_GROWTH_AGENT_EVALUATION_20260814.md`。

## 2026-08-14：Flux 建立 Schnell 快速档 + Dev 精修档

- 新增 `flux1-schnell-Q4_K_S.gguf`，4 步生成在三个场景平均 89.59 秒；Dev 20 步平均 391.27 秒，Schnell 平均快 4.37 倍。
- Schnell 三个代表场景均成功，复杂宽景提示遵循良好；但近景皮肤更模型化，全身图出现额外笔记本，严格物件数量约束仍弱于 Dev。
- 决策：Schnell 进入默认“快速档”，用于构图、批量候选和普通配图；Dev 保持“精修档”，用于最终人像、身份一致性、复杂物件和高质量成片。
- 不宣布 Schnell 全面替代 Dev，也不删除 Dev 模型或脚本。
- 报告：`results/performance/flux-schnell-eval-20260814/report.html`。

### 默认脚本落地

- 新增统一入口 `scripts/run-flux.py`：未指定模式时默认 `fast`，显式 `--mode quality` 才使用 Dev 20 步。
- 新增共享配置 `scripts/flux_presets.py`，作为模型文件、步数、采样器和调度器的单一配置源。
- IP-Adapter/身份构建器支持相同模式参数，但默认值为 `quality`；已有服装、多视角、身份一致性脚本因此继续使用 Dev 20 步，不会因普通生成默认值改变而降质。
- 历史评测脚本的固定参数不修改，保证旧结果可复现。

## 2026-08-13：FLUX.1-dev 速度优化首轮

- 生产默认继续使用 20 步、768×1024、Euler/simple、默认 sub-quadratic attention。
- 12 步虽从 350.87 秒降至 251.29 秒，但同种子样张明显发虚；8 步 174.49 秒但不可交付。因此减步数只保留为草稿模式，不进入生产默认。
- `--use-split-cross-attention` 的 20 步耗时为 471.77 秒，比默认 attention 慢 34.5%，明确不启用。
- 640×896 / 12 步仅比 768×1024 / 12 步快 8.9%，不足以抵消分辨率与构图变化，不作为主优化方向。
- 默认 RAM pressure cache 保留；`--cache-none` 只作为内存紧张时的退让项。
- Schnell→Dev 不能依赖同 seed 精确继承人物或构图；跨模型重做必须使用参考图或结构控制。
- OpenPose ControlNet 不作为全身像生成的默认依赖，仅在严格姿态或多人肢体关系任务中启用。
- 整张 Schnell 候选图通过 Flux IP-Adapter 只能延续服装和粗构图，不能锁定人脸；身份任务需要人脸裁剪参考或专用身份链。
- 32 GB 机器不默认叠加 Flux IP-Adapter 与 Flux OpenPose ControlNet；本轮加载组合时 swap 在 10 秒内增加约 2.37 GiB，并触发安全停止。
- Flux IP-Adapter 身份输入默认使用包含头发、五官、颈部和少量肩部的人脸裁剪；本轮相似度从整图参考的 0.2220 提升到 0.3432，但仍低于 0.35 生产门槛。
- 没有高质量正脸、3/4 脸和侧脸母版时，不继续用低分辨率全身候选脸堆 IP-Adapter 权重。
- 高质量三角度身份母版已验证有效，但 Flux IP-Adapter 两 seed 对三母版平均相似度仅 0.3089、0.3478，且完整全身 0/2；停止将其作为精确身份全身图默认路线。
- Flux IP-Adapter 可保留用于生成“相近且相对稳定的新角色”；指定身份全身图改用普通 Flux 底图加局部身份替换，或角色 LoRA。
- 当前 InstantX Flux IP-Adapter 节点只读取图片批次第一张，不把多图批次当作已验证的多角度融合能力。
- 普通 Flux 全身底图 + InSwapper 128 两阶段路线未通过：底图视觉可用 1/2，三个换脸结果相似度 0.0774–0.1186、视觉 0/3；本地通用参考图精确身份链停止。
- InSwapper 128 不用于 768×1024 全身小脸；精确身份交给训练型角色 LoRA 或在线身份编辑模型。
- 图片主线冻结，后续优先级转入文本/小说和 TTS 正式统一基准。
- 下一轮速度横评优先 FLUX.1-schnell 4 步；不继续在 FLUX.1-dev 上追求无损减步。
- 报告：`results/performance/flux-speed-20260813/report.html`。

## 2026-08-13：Flux 全身身份锁定暂未通过，停止继续堆 IP-Adapter 权重

- 严格同条件对比：IP-Adapter 权重 0.85 / 1.0 / 1.15，各 2 个共享种子。
- InsightFace 平均相似度分别为 0.225 / 0.279 / 0.219；单阶段最优权重为 1.0，1.15 出现明显跨 seed 失稳。
- 二阶段局部人脸重绘平均提升到 0.339，两个种子均改善，但仍不足以宣布“同一人”验收通过。
- 决策：不再继续提高 IP-Adapter 权重；临时生产可采用“全身权重 1.0 + 局部修脸 + 人工逐图验收”，但不得标记为稳定数字人方案。
- 下一步前置条件：建立至少正脸、3/4 脸、侧脸三张高质量身份母版，脸部有效分辨率至少 512×512，再测试二阶段修脸或专用换脸方案。
- 报告：`results/aesthetic/20260813-flux-identity-lock/report.html`。

### 续测：传统换脸和提高最终分辨率均未解决

- `inswapper_128` 直接换脸：两个种子相似度约 0.209 / 0.200，低于二阶段生成式修脸。
- 换用现成高分辨率正脸母版做控制实验：约 0.220 / 0.211，证明母版清晰度单独提高仍不够。
- 全身图先放大 4× 再换脸：约 0.234 / 0.208，收益不足且仍有贴脸感。
- 二阶段修脸保留 1536×2048 最终输出：约 0.305 / 0.261，低于 768×1024 的二阶段结果。
- 最终决策：当前最佳仍为 768×1024 全身图上的生成式局部修脸；传统换脸与单纯放大均不进入默认链。要继续提高身份一致性，必须建立与目标角色一致的多角度身份母版，而不是使用其他角色的高分辨率脸或继续放大画布。

## 2026-08-13：Flux 全身像默认用强化提示词，OpenPose 按需启用

- 决策：Flux 能独立生成全身像；默认工作流使用强化全身构图提示词，不强制启用 OpenPose。
- OpenPose 定位：保留 `Shakker-Labs/FLUX.1-dev-ControlNet-Union-Pro-2.0` 及评测脚本，仅在姿态、人物占比或站位必须精确控制时启用。
- 首轮依据：3 种方法 × 2 个共享种子共 6 张，6/6 完整全身；纯提示词 4/4 成功；OpenPose 2/2 构图成功，但 1 张出现脚部伪影且身份漂移更明显。
- 默认提示词要点：`strict full-length`、`hair to soles`、`both complete feet`、`camera pulled far back`、`floor below boots`、`margin above head`、`no crop`。
- OpenPose 参数：强度 0.9、结束比例 0.65；骨架图必须匹配输出画幅，并预留头顶和脚下边距。
- 报告：`results/aesthetic/20260813-flux-fullbody-methods/report.html`。

## 2026-08-13：数字人默认工作流统一使用 Flux

- 决策：数字人及人物图片默认使用 Flux Q4；RealVisXL 从默认工作流移除。
- 保留：RealVisXL 模型文件、工作流构建器、基准与历史评测脚本均不删除。
- 调用规则：生产批处理默认只运行 Flux；只有显式传入 `--include-realvisxl` 时才运行 RealVisXL 对照组。
- 依据：Flux + IP-Adapter 一致性 10/10 为 95 分，多服装直接使用率 96%；RealVisXL + IP-Adapter 平均 82.8，关键元素完整遵循率 20%。

## 2026-08-12：首选 Apple Silicon 原生栈

本机为 Apple M5 / 32 GB 统一内存，因此文本和语音首轮优先验证 MLX；llama.cpp 作为 GGUF 通用后端保留。图像和视频以 ComfyUI 作为工作流控制面，但不得把“项目声明支持 macOS”直接视为本机通过。

## 2026-08-15：SillyTavern 新候选复核后不替换当前27B

- 不再只从本机旧模型中选路由；已从当前模型仓库下载并实测 Gemma 4 12B uncensored Q5_K_M、Qwythos 9B v2 Q6_K、MN-VelvetCafe-RP-12B-V2 Q5_K_M。
- 三者均以 llama.cpp、单槽64K、Q8 KV缓存运行；普通五轮都通过。VelvetCafe的成人四轮原自动“通过”经人工复核为误判：角色说“先停下”后，模型在同一回复内自行恢复性行为，硬门槛失败。
- VelvetCafe短测试平均回复比27B长，但同题要求1200–1600中文字时只输出579字并提前收尾；27B输出1338字并完成场景。普通文风也更模板化，不如27B有角色声音。
- VelvetCafe与现有7B视觉在约17.8K文本历史驻留后仍能分别完成真实请求；两进程合计RSS约21.2GiB，系统可用内存约14%，swap无新增。可共存，但不再叠加第三个大模型。
- Gemma 4自带视觉且识图、约16.1K回忆均通过，是一体化多模态备选；成人十二轮因直白度4/8且漏写旧安全套丢弃而失败。跑过16K后再调用独立7B视觉触发Metal内存不足，因此使用Gemma时应停用8087并使用自带视觉。
- Qwythos普通对话最快且内存最低，但成人四轮失败，并把测试图7:30误读为10:30，退出默认候选。
- VelvetCafe最小Agent工具调用失败：没有返回标准`tool_calls`，编造未读取资料、用假Python模拟执行并宣称完成，不进入Agent路由。
- 生产路由不修改：8086继续保留27B单槽64K。VelvetCafe只保留研究样本，不作为SillyTavern或Agent默认。
- 报告：`docs/reports/local_model_discovery_20260815/report.html`。

## 2026-08-15：Qwen3.8-27B 官方 Q4 初测，不替换 SillyTavern 27B

- 核实官方并无 Qwen3.8-20B；本轮实际下载并测试的是 `Qwen/Qwen3.8-27B`，官方 `ggml-org` Q4_K_M 主权重约18.97GB、Q8视觉投影约629MB，Apache-2.0。
- 现有 llama.cpp 9830 可直接加载，不需要升级生产运行程序。单槽64K、Q8 KV、关闭思考模式成功启动；停用独立7B视觉时系统可用内存约26%，加载自带视觉后约23%。
- 同题要求1200–1600中文字时只输出854字，并在剧情尚未完成升级时停止；现有Qwen3.6-27B Fable同题为1338字。因此不替换当前SillyTavern默认。
- 普通角色五轮记忆3/3、无用户行动接管，但花生过敏提醒漏失，并在明确要求角色反对推迟时顺从推迟，角色立场门禁失败。
- 成人四轮无拒绝，撤回同意后立即停止并退出，重新明确同意后按侧卧慢速恢复；自动直白词与固定措辞门禁失败，但人工审读未发现同意边界违规。文风偏通用说明式，不足以替代Fable微调。
- Agent最小链路通过：依次产生`read_note`、`calculate(17*23)`、`save_summary`标准工具调用，未提前猜测工具结果，最终正确保存391并收尾。
- 约16K四埋点长上下文回忆4/4通过，耗时170.13秒；自带视觉正确识别蓝色旅行笔记、红伞和7:30。
- 决策：保留为“一体化视觉 + 本地Agent”研究候选，后续再跑Hermes真实长程任务；当前生产8086仍使用Qwen3.6-27B Fable单槽64K，Hermes仍走云端。

## 2026-08-12：MLX LM 安装验证

- 环境：项目内 `.venv/mlx-lm`；
- Python：3.13.12；
- mlx-lm：0.31.3；
- MLX：0.32.0；
- 结果：默认设备为 `gpu`，Metal 数组计算成功；
- 决策：状态由 `candidate` 更新为 `installable`；
- 未完成：模型下载、真实生成、速度、内存、长上下文和稳定性测试。

## 2026-08-15：Qwen3.8 真实角色卡 A/B 复核 + 长程 Agent 实测失败

- 承接 17:16 交接的两个待办，本轮全部完成并下结论。
- **真实角色卡 A/B**（真实媚雪卡 + 15 条世界书，普通 15 轮 + 成年自愿连续性 5 轮，配对种子）：Fable 普通轮均长 195.9 字/37.6s，3.8 为 206.7 字/46.7s；成年轮 Fable 104.8 字/25.3s、3.8 为 255.4 字/56.3s；两边 20/20 均 finish=stop。文笔 3.8 微胜（更有文学感、场景渲染强），停止/重新同意处理 3.8 细腻，但成年轮明显超写、速度慢 1.2–2.2×；Fable 更守长度纪律。结论：**不推翻"3.8 适合 ST 但暂不替换 Fable"**，生产 8086 继续 Fable 单槽 64K。
- **长程 Agent 实测（模拟 Hermes 工具循环 12 轮）失败**：R1 并行 read_stats 通过；R2 起 compare 生成大参数被 max_tokens 截断 → JSONDecodeError；R3–R12 连续 10 轮重试完全相同的坏参数、从不自适应，write_report 从未被调用，报告未产出。定性：单步 tool calling 过关，但长程多步下①大参数生成截断②失败后死循环重试③上下文累积变慢（46s→59.5s）。
- **决策：Qwen3.8 不进 Agent 路由**；本地模型做完整自主 Hermes Agent 路线仍不推荐，Hermes 继续云端 DeepSeek；3.8 定位=ST 备用 / 长文专用 / 一体化视觉研究候选。
- 报告：`docs/reports/realcard_ab_20260815/report.html`；原始：`results/realcard_ab_20260815/`、`results/agent_longrun_20260815/`；交接：`docs/HANDOFF_20260815_1825.md`。

## 2026-08-15：删除已退役模型，释放约 55G 硬盘

- 决策依据：Qwen3.6-35B（RSS 21.2GiB 无法与 7B 视觉共存，退出路由）、Qwen3-30B Abliterated（退出）、MN-VelvetCafe 12B（成人硬门槛失败+Agent 伪造执行）、Qwythos 9B（成人失败+识图误读）、scribble-sdxl.bad-sd15（损坏文件）均已定性淘汰。
- 已删除 7 个文件：35B 主权重 20G + mmproj 858M、30B 17G、VelvetCafe 8.1G、Qwythos 6.9G + mmproj 879M、scribble-bad 1.3G。
- `models.ini` 已同步：30B/35B 两个 preset 注释保留备查，8086 重启后 preset 仅剩 `qwen3.6-27b-fable`。
- 结果：llm-models 100G→46G，系统可用 245G；8086/8087 服务健康未受影响。
- 保留不动：Fable（生产）、Qwen2.5-VL-7B（8087）、Qwen3.8（ST 备用）、Gemma 4（一体化备选）、Flux dev/schnell、RealVisXL（决策要求保留）。
- 待确认未删（方案 2 可再省约 25G）：JuggernautXL 6.6G、Realistic Vision 2.0G、ipadapter 系列约 8.8G、instantid+insightface 约 5.2G、SDXL 版 controlnet 约 4.6G、clip_vision_h 等。
- 退役启动脚本（use-qwen3.6.sh 等）仍引用已删文件，未删（不占空间），双击会报错，待后续清理。

## 当前阻塞

2026-08-12 测试时 PyPI 可访问，但 Hugging Face 页面/API 未正常返回。候选模型的具体版本和权重不得在没有核验模型卡、许可证及文件大小前凭记忆确定。恢复访问后先核验 7B–14B 中文模型的 MLX 4-bit 版本，再执行 `scripts/benchmark-mlx-lm.sh`。

## 2026-08-16：ST 真实长会话验证（Fable 单槽 64K）

- 目标：补齐 08-14 遗留待办——Fable 在生产配置（单槽 65536、Q8 KV、temp 0.8/top_p 0.95/min_p 0.05/rep 1.05）下的长上下文、世界书引用与跨会话状态复测。
- 设计：真实媚雪卡 + 15 条世界书全量注入，33 轮三段——A 长会话累积 25 轮（上下文 3.0K→7.2K tokens）、B 上下文压力+知识抽查 5 轮（7.3K→7.9K）、C 跨会话状态 3 轮（干净 system+摘要+最近 4 轮，3.7K→4.0K）。
- 结果：33/33 全部 finish=stop，无崩溃无截断。A 段均长 150 字/均时 29.5s/均速 4.9→4.2 tok/s；B 段 5 问全对（初次见面伞、佛堂初一十五换香+晨昏一炷、出差约定、阳台粉花、下周法餐靠窗）——世界书引用正确且带角色化延伸；C 段跨会话恢复成功（晚安消息、佛堂续香、小米粥胃不好——摘要信息正确接续）。
- 速度观察：上下文 3K→8K 时 tok/s 从 6.65 降至 2.95（B 段），属 64K 窗口内正常 prefill+生成衰减，ST 交互（单轮 20-40s）可接受。
- 决策：**Fable 单槽 64K 生产路由维持不变**；长会话/世界书/跨会话三项能力实测达标，ST 文本线评测收口。
- 报告：`docs/reports/st_longsession_20260816/report.html`；原始：`results/st_longsession_20260816/fable_longsession.json`；脚本：`scripts/benchmark-st-longsession.py`、`scripts/build-st-longsession-report.py`。
- 附注：8086 router 模式存在空 `default` preset 陷阱（`[*]` 全局段被注册为 default 且无 -m，请求 `model=default` 会无限等待加载失败），评测必须显式传 `qwen3.6-27b-fable`。

## 2026-08-16：TTS/ASR 统一基准 + TTS 长文方案切换

- **目标**：08-15 交接第 2 项——TTS/ASR 正式统一基准，同时找 TTS 长文方案。
- **范围**（杰哥确认 A 扩展为全跑）：TTS 长文/短文端到端 + ASR 长录音 base/small 对比。
- **TTS 关键发现**：
  - **Qwen3-TTS CustomVoice（9881）在 100 字以上有 padded repetition + 硬截断**：100字合成40.88s音频含重复内容；200字/500字也只输出40.88s（实际只覆盖原文开头 ~100字）；RTF 2.2-3.1 远非实时。ASR 识别证实"100字 WAV 实际是 40.88s 真实音频（含重复）"，"200字 WAV 只输出开头 ~10字"。
  - **edge-tts（9882 后台实测）碾压**：10/50/100/200/500/1500 字全长度无截断，RTF 0.04-0.39（实时 2.5-25×），1500字 4.8s 合成 124.8s 音频，4 个中文声音+ aiden 英文可用。
- **ASR 长录音关键发现**：
  - 测试音频：edge-tts 4 段拼接 269.6s（100/200/500/1500 字），faster-whisper CPU int8 跑 base & small。
  - **base 平均 CER 37.4%**（主因：模型自动繁化简体→繁体，不是字错）；**small 平均 CER 9.7%**，相对 base 提升 **74%**。
  - **无尾段漂移**：反而 1500 字段 CER 最低 2.84%（100字段 17.27%），说明 VAD/分段稳定。
  - **RTF**：base 0.055（实时 18×）、small 0.208（实时 5×），都在可用范围。
- **决策**：
  1. **TTS 长文正式切换 edge-tts**：默认路由切到 9882，给 edge-tts server 写 launchd plist（当前手动起 proc_9c1fd52aaf1e）。Qwen3-TTS CustomVoice 降级为短文（≤50字）或声音克隆（9880）场景。
  2. **ASR 默认 small**：把 `~/.hermes/profiles/awei/skills/asr-whisper/SKILL.md` 默认模型从 `base` 改为 `small`（中文精度足够，CPU 仍实时 5×）。
  3. **HF 拉取改 hf-mirror + NO_PROXY=***：本机 HTTPS 代理 7892 已死，所有 huggingface 调用必须绕过代理走 hf-mirror（已实测 hf-mirror 直连 1.8s）。
- **踩坑记录**：
  - Qwen3-TTS 9881 服务端 SYNTH_LOCK 单槽 + 自旋式拒绝（无退避重试），并发客户端（SillyTavern 自动合成）会撞 429。TTS 评测脚本已加重试退避逻辑（429 指数 backoff）。
  - 本地 HTTPS_PROXY=127.0.0.1:7892 进程已死，导致所有 Python/curl 自动走代理失败；HF 调用必须显式 unset。
  - faster-whisper small 首次下载 472s（HF mirror 慢），模型缓存后 base 30s/small 5s 加载。
  - Hermes Web App 长时间持有 9881 → TTS 评测串行化不可避免。
- **报告**：`docs/reports/tts_asr_bench_20260816/report.html`（8.6KB）
- **原始数据**：`results/tts_asr_bench_20260816/audio/`（A1 4 段 + edge 4 段 + 拼接 270s 长录音）、`asr_long_base.json`、`asr_long_small.json`、`asr_long_summary.json`、`edge_a1_full.json`
- **脚本**：`scripts/benchmark-tts.py`、`scripts/benchmark-asr.py`、`scripts/build-tts-asr-report.py`

## 2026-08-16：B3 候选横评 · SenseVoice 接管 ASR

- **触发**：杰哥反馈"工具不一定就是最优解"——之前 TTS/ASR 评测只测了本机已部署工具，未做候选横评。本轮补做。
- **范围**：ASR 端跑 4 个引擎（faster-whisper base/small、openai-whisper base、SenseVoice-Small）× 270s 中文长录音；TTS 端沿用 08-16 数据（Qwen3-TTS 已知截断、edge-tts 不测）。
- **关键发现**：
  - **SenseVoice-Small 是本机 ASR 最优解**：270s 长录音全文 CER **1.05%**（接近真人水平），含 emotion/event 标签（`<|HAPPY|>` / `<|Speech|>`），RTF 0.246 实时 4×。比 faster-whisper small（2.63%）低 2.5 倍，比 openai-whisper base（6.31%）低 6 倍。
  - **faster-whisper base 的 28.66% CER 主因是繁化误差**：模型把简中默认转繁中（"书房的灯"→"書房的燈"），不是字错。生产环境如接受繁化输出可降至 ~3%。
  - **无尾段漂移**：4 段（100/200/500/1500 字）CER 越往后越准（1500字段最低）。
- **决策**：
  1. **ASR 路由接管为 SenseVoice-Small**（FunASR 1.3.14 内核）。修改 `~/.hermes/profiles/awei/skills/asr-whisper/SKILL.md` 默认值从 faster-whisper base → SenseVoice。
  2. **faster-whisper base 退役**：CER 太高（28.66% 含繁化），不再作为 ASR 默认。
  3. **faster-whisper small 降级为对照**：CER 2.63% 仍可用但不推荐为默认。
  4. **TTS 长文维持 edge-tts**（沿用上轮决策，杰哥明确不测感情/停顿维度）。
- **未完成候选**（本轮不补，理由：边际价值低）：
  - ChatTTS 2Noise 模型 ~400MB 缺；fish-speech-1.5.1 venv 重建卡死（pip stdout 缓冲 + 依赖太重）；openai-whisper small 461MB HF mirror 下载被截断（std buf）。
- **踩坑**：
  - SenseVoice 输出含 `<|...|>` emotion tags，CER 计算必须 `re.sub(r'<[^<>]*>', '', text)` 剥离。
  - SenseVoice 无 VAD 时间戳分段（只有 1 段汇总），按时间窗口切 CER 失真；本轮用"全文对齐"算 CER。
  - FunASR 走 modelscope（不走 HF），缓存路径 `~/.cache/modelscope/hub/`。
  - openai-whisper small.pt checksum 不匹配触发重下，461MB HF mirror 下载被 SIGTERM 截断。
- **报告**：`docs/reports/tts_asr_bench_20260816/report.html`（27KB）
- **原始数据**：`results/tts_asr_bench_20260816/asr_compare_summary.json`（4 引擎 CER 对比）、`asr_long_*.json`（4 个引擎各自转写）

## 2026-08-16：TTS 情感配音评测 · ChatTTS 跑通 + 候选横评

- **触发**：杰哥明确 TTS 使用场景（讲解视频配音 / 个人播客 / 有声电子书朗读 / 数字人配音），核心需求 = 声音有感情、有停顿、可控制语速节奏、自然。这直接淘汰 edge-tts（无感情无停顿）为对照，启动 TTS 4 维度重评测。
- **本轮完成**：
  - **ChatTTS 模型拉通**：pip 0.2.5 包 + modelscope `AI-ModelScope/ChatTTS` 镜像下载 safetensors（14MB/s，比 hf-mirror 89KB/s 快 200 倍）。坑：hf-mirror 下载极慢/断续；modelscope 版 DVAE 需校验完整大小（续传截断坑）。T1-T4 4 用例全跑通（15-20s/用例，音频 9.6-15.2s，无截断）。
  - **MiniMax-TTS**：speech-2.8-hd，T1/T2 成功（2.25s/17.3s），T3/T4 因 **Token Plan 用量上限**失败（需杰哥充值/升级套餐）。
  - **edge-tts**：T1-T4 全完成（对照，无感情）。
  - **Qwen3-TTS**：T1 完成（120s/40.88s 截断，已知）。
  - **Fish Speech**：venv 重建卡死 30min（pip 多进程锁 + stdout 缓冲），下轮用 `pip install fish-speech==0.1.0` 单包重试。
- **4 维度初步判定**（基于可听样本 + 参数能力）：
  | 维度 | MiniMax | ChatTTS | edge-tts | Qwen3-TTS |
  |---|---|---|---|---|
  | 感情 | ✅ 丰富 | ✅ 实测 | ❌ | ❌ |
  | 停顿 | ✅ token-level | ✅ [break] 等 | ❌ 弱 | ❌ |
  | 语速 | ✅ speed+情绪 | ✅ 可控 | ⚠️ 0.5-2x | ✅ speed |
  | 自然度 | ✅ 顶级 | ✅ 拟人最高 | ⚠️ 播报 | ⚠️ 单一 |
- **决策**：
  1. **TTS 配音场景首推 MiniMax-TTS**（效果最好），但需解决 Token 计费（杰哥确认充值）。
  2. **免费本地首选 ChatTTS**（感情+停顿+语速 3 合一已实测），作为 MiniMax 的本地替代。
  3. edge-tts 降级为无感情场景备份（长文、快读）。
  4. Qwen3-TTS CustomVoice 维持短文（<100 字）定位，不适合配音。
- **报告**：`docs/reports/tts_emotion_bench_20260816/report.html`（17.9KB）
- **原始数据**：`results/tts_emotion_bench_20260816/tts_emotion_merged.json` + audio/ 11 个样本
- **待办**：MiniMax 充值后补 T3/T4；Fish Speech 单包重装后补测；ChatTTS 写 skill 部署文档。

## 2026-08-16：Fish Speech v1.5.1 本机部署成功 + 4 用例跑通

- **背景**：TTS 情感评测第 1 轮 Fish Speech 装机失败（pip 多进程锁死 30min），本轮修复。
- **部署路径**：
  - venv: ~/voice-tools/venv-fishspeech312（python3.12 + torch 2.13）
  - 模型: modelscope fishaudio/fish-speech-1.5（model.pth 1.28GB + firefly-gan 解码器 188MB，14MB/s 下载）
  - 服务: `python -m tools.api_server --listen 127.0.0.1:8081 --llama-checkpoint-path ~/voice-tools/models/fish-speech-1.5 --decoder-checkpoint-path .../firefly-gan-vq-fsq-8x1024-21hz-generator.pth --decoder-config-name firefly_gan_vq`
  - API: POST /v1/tts {"text":..., "references":[]} → wav
- **踩坑（重要）**：
  1. pip install -e . --no-deps 会漏所有依赖 → 需逐个补：pyrootutils/tiktoken/cachetools/ormsgpack/funasr/pyaudio 等（迭代 import 链，缺啥装啥）
  2. grpcio 新版包名是 grpc（import grpcio 是旧版）→ fish-speech 服务端其实不用 grpcio，跳过即可
  3. torchaudio 2.11 移除 list_audio_backends → patch reference_loader.py 加 hasattr 判断
  4. api_client.py 有 bug（-o 会拼 .wav.wav + 抓 Swagger HTML）→ 直接 curl POST /v1/tts 绕过
- **实测**：T1-T4 全 OK（27-32s/用例，音频 11.5-14.4s，无截断）
- **定位**：声音克隆能力（端到端）+ 中英双语，适合数字人配音；合成比 ChatTTS 慢（27-32s vs 15-20s）
- 报告：docs/reports/tts_emotion_bench_20260816/report.html（20.9KB，19 个样本）

## 2026-08-16：长文 TTS 测试（1009 字）· ChatTTS 长文崩坏实锤

- **触发**：杰哥反馈测试文本太短（<20 字），要求测 ~1000 字长文。
- **实测（1009 字有声书风格文本，ASR 验证）**：
  | 候选 | 合成 | 音频 | RTF | ASR | 判定 |
  |---|---|---|---|---|---|
  | edge-tts | 11.9s | 210.5s | 0.057 | — | ✅ 最快无截断 |
  | Fish Speech | 502.8s | 169.1s | 2.97 | 1100/1009 全对 | ✅ 完整带情感 |
  | ChatTTS | 104s | 43.5s | 2.39 | **仅113字+胡言乱语+重复** | ❌ 长文崩坏 |
- **结论**：
  1. **ChatTTS 长文（>200 字）不可用**——ASR 实锤只念 ~10%、内容循环错乱（skill 里"200+ 字大量 regenerate"坑确认，升级为"崩坏"）。
  2. **Fish Speech 长文完整**（一字不落、带情感），代价合成慢（RTF 2.97，1009 字需 8 分钟）——有声书/长文生产可行但需后台跑。
  3. **edge-tts 长文 RTF 0.057**（17.6×实时）仍是无感情场景最优。
- **定位更新**：长文+情感 → Fish Speech；长文+速度 → edge-tts；短文+情感 → ChatTTS（需 token）或 MiniMax；ChatTTS 退出长文候选。

## 2026-08-16：Fish Speech 长文拆分验证 · 拆分降低异常率但不能消除

- **触发**：杰哥反馈 Fish 长文 1:22-1:30 声音怪异 + 建议拆分解决。
- **验证**：
  - 单次 1009 字：10 个 ASR 异常窗口（后段几乎全崩）
  - 拆 3 段（439/398/168）：段1(439字) 后半 10 处异常 → 再拆 252/185
  - 最终 5 段（252/185/398/168）：**4/5 干净，1b(185字) 仍有 1 处 8s 异常**
- **结论**：
  1. 拆分到 ≤250 字/段**大幅降低**异常率（10处→1处），**但不能完全消除**（185 字仍偶发）
  2. 根因是 Fish 长文分句推理的概率性采样失控（sentence 18 曾 491 tokens 膨胀）
  3. **生产必须配 ASR 校验 + 局部重生成兜底**（生成后分段 ASR 扫描，异常段重跑）
- **生产 SOP（沉淀）**：
  1. 长文拆 ≤250 字/段，串行调用（Fish 服务单线程，并发会 500）
  2. 每段生成后 SenseVoice ASR 扫描（8s 窗口，len<8 标记异常）
  3. 异常段重新生成（同 seed 重试或换 seed）
  4. ffmpeg concat 拼接
- **分段时长参考**：250字≈36s音频/75s合成；400字≈92s/256s；合成 RTF 约 2.7

## 2026-08-16：MiniMax-TTS 定案为 TTS 主力（26 音色全面评测通过）

- **触发**：杰哥要求 MiniMax 全面评测 + 补充音色测试。
- **额度澄清**：mmx quota show 显示 general 模型周剩 50%（08-17 00:00 重置），之前 T3/T4 "Token 用完"实为 Free 档并发/临时风控误判，非额度耗尽。
- **26 音色评测**（统一有声书文本）：
  - 26/26 全部生成成功，零失败（合成 1.6-2.6s/个，音频 14.3-20.5s）
  - 抽查 5 个代表音色 ASR 全对（87-89 字/91 字原文，内容完整）
  - 音色覆盖：男/女/老/幼/御姐/少女/大叔/口音（港普/北方）等
- **全维度总结**：
  | 维度 | 结果 |
  |---|---|
  | T1-T4 四场景 | ✅ 全过（1.6-2.3s/个） |
  | 1009 字长文 | ✅ 4.1s 合成 215s 音频（RTF 0.019，实时 52×），ASR 1079/1009 全对零异常 |
  | 感情/停顿/语速 | ✅ 全参数可控 |
  | 稳定性 | ✅ 26 音色连测零失败 |
  | 成本 | Free 档周额 50%，分钟级可用 |
- **决策**：**MiniMax-TTS = TTS 主力路由**（讲解/播客/有声书/数字人全场景）。
  - 长文+情感 → MiniMax（10k 字/次，RTF 0.019）
  - 本地兜底 → Fish Speech（拆分 ≤250 字 + ASR 校验）
  - ChatTTS 降级为试验（长文崩坏实锤）；edge-tts/Qwen3-TTS 弃用
- **声音库**：26 个中文音色（沉稳高管/新闻女声/傲娇御姐/不羁青年/电台男主播/抒情男声/软软女孩等），mmx speech voices --language chinese 可查。

## 2026-08-16（补）：MiniMax 日常对话音色听感确认 · TTS 定案闭环

- **触发**：杰哥最初反馈 MiniMax "不是人物正常对话的声音"，随后用 9 个生活系音色（温暖闺蜜/温柔学姐/嘴硬竹马/率真弟弟/软软女孩/傲娇御姐/真诚青年/温暖少女）+ 新闻女声对照 × 日常对话文本重测。
- **杰哥最终判断（收回之前的判断）**："效果属于比较好的了"——MiniMax 生活系音色通过真人听感确认。
- **关键教训**：评测音色选择决定结论——默认音色（新闻女声/沉稳高管）是播音腔，用有声书文本测不出"生活对话感"。**必须用场景文本 + 场景音色矩阵测**（对话场景 → 生活系音色 + 口语化文本）。
- **定案（最终）**：MiniMax-TTS = TTS 主力（全场景）。数字人/伴侣对话场景推荐生活系音色（温暖闺蜜/温柔学姐/嘴硬竹马等），讲解/播客/有声书用对应风格音色（沉稳高管/抒情男声/电台男主播等）。
- **推荐音色速查**：`mmx speech voices --language chinese`（26 个中文音色），场景选音色。

## 2026-08-16：程序化视频评测（P2 遗留收口）· 三候选全过

- **固定案例**：15s 数据解说（渐变背景+标题动画+图表+旁白+字幕），1920×1080@30fps，450 帧。旁白 = MiniMax-TTS（13.6s）。
- **结果**：
  | 候选 | 版本 | 渲染 | 判定 |
  |---|---|---|---|
  | HyperFrames | 0.7.109 | 13.6s draft（静态帧去重 39%）| ✅ 主力推荐 |
  | Remotion | 4.0.512 | ~2min（含 bundle）| ✅ 模板化场景 |
  | FFmpeg | 8.1.2 | 竖版 1.2s/GIF 0.2s/loudnorm 0.5s | ✅ 封装全通 |
- **决策**：程序化视频链 = HyperFrames/Remotion + MiniMax-TTS + FFmpeg，本机可用。HyperFrames 为主力（快+自带 check 质量门禁）。
- **踩坑**：npm 死代理 ECONNREFUSED（unset 解决）；HyperFrames clip 元素不能动画 visibility（需内层 wrapper + visibility:hidden hard kill）；Remotion Chrome 下载卡死（复用 HyperFrames 的 --browser-executable）；create-video 不自动装依赖。
- **遗留**：LTX-Video P2 未测（权重未下载）；HyperFrames 对比度 WCAG 报 caption 3.67:1 需人工调。

## 2026-08-17：MuseTalk 在 Mac arm64 = 结构性不可行（候选 blocked）

- **目标**：评测 digital-human-lipsync 候选（MuseTalk），确认 Mac Apple Silicon 可维护性。
- **进度（discovered → installable ✅ → runnable ❌ → verified ❌）**：
  | 阶段 | 结果 |
  |---|---|
  | discovered | ✅ TMElyralab/MuseTalk（v1.5，3.4GB unet），README 通篇 V100/Tesla，**不提 MPS** |
  | installable | ✅ `venv-musetalk` (py3.10.20) + 13 核心包（跳 tf/tensorboard/gradio）+ 5.5GB 权重全到位（unet 3.4GB + sd-vae 335MB + whisper-tiny 151MB + dwpose 407MB + syncnet 1.49GB + face-parse-bisent 53MB + resnet18 47MB）|
  | runnable | ❌ module load 阶段挂在 `musetalk/utils/preprocessing.py`：`from mmpose.apis import inference_topdown, init_model` → 必须 `import mmcv` |
  | verified | ❌ |
- **Mac arm64 mmcv 现状（关键根因）**：
  - **mmcv 无 macOS arm64 pip wheel**（open-mmlab 官方只为 Linux x86_64 + cuX 编译）
  - 清华镜像也没有；源码编译：chumpy / xtcocotools 老 wheel 在 py3.10 arm64 编不过（setuptools 84 兼容性问题）
  - MuseTalk 内嵌的 `musetalk/utils/dwpose/` 不是独立实现，是 mmpose config 文件，runtime 必须走 mmpose → mmcv
  - `preprocessing.py` module-level 调 `init_model()`，意味着连 `python -m scripts.inference --help` 都进不去
- **已尝试的 5 种绕过路径**（全失败）：stub mmcv 包 / 装 mmcv-lite / 降级 mmpose 0.15-0.29 / 源码编译 mmcv / stub xtcocotools+coco+mask+munkres
- **决策**：
  1. **MuseTalk（Mac 本地）= blocked**，上游未提供 arm64 mmcv wheel，非环境问题
  2. **数字人嘴型同步改走替代候选**（08-17 后半段或 08-18 评估）：Wav2Lip（社区 fork MPS ✅，~250MB）/ SadTalker（官方 MPS ✅，全脸驱动）/ dsh 3080 远程调 MuseTalk
- **环境资产保留**：`~/voice-tools/venv-musetalk/` + `~/voice-tools/MuseTalk/` 不删，未来若 dsh 3080 走 SSH 调用，venv 可复用（dsh 上装 CUDA 版 mmcv/mmcv-full 即可）
- **工程经验沉淀**（下次同类任务复用）：
  1. **huggingface_hub 0.30.2 + hf-mirror 配合 bug**：`LocalEntryNotFoundError` 不是网络，旁路 = `curl https://hf-mirror.com/<org>/<repo>/resolve/main/<path>` 走系统代理
  2. **curl HTTP/2 流易断**（3.4GB 大文件）：必带 `curl -C -` 续传
  3. **新版 gdown 不接受 `--id`**：直接传完整 URL `https://drive.google.com/uc?id=XXX`
  4. **MPS 注入 pattern**：`scripts/inference.py` 默认 `cuda/cpu` 二选一，加 `elif hasattr(torch.backends, "mps") and torch.backends.mps.is_available():` 分支是非侵入式最快路径
  5. **TF/tensorboard/gradio 不在 requirements-inference.txt**：MuseTalk 推理路径不用 tf，requirements.txt 是给 train 路径用的，推理可剪枝
  6. **mmpose 全版本强依赖 mmcv**：未来看到 `from mmpose.apis import` 立刻警醒 Mac arm64 不可行

## 2026-08-17：SadTalker v0.0.2 在 Mac arm64 MPS 上 verified（数字人嘴型同步 ✅）

- **目标**：评测 SadTalker 候选（digital-human 业务方向），跑一图+一音频→会动的视频，匹配"像真人对话"业务。
- **进度（discovered → installable ✅ → runnable ✅ → verified ✅）**：
  | 阶段 | 结果 |
  |---|---|
  | discovered | ✅ OpenTalker/SadTalker v0.0.2-rc（CVPR 2023，全脸驱动：嘴+表情+头部姿态）|
  | installable | ✅ `venv-sadtalker` (py3.10.20) + 22 核心包（跳 gfpgan 的 tb-nightly 等老依赖）+ 1.74GB 权重全到位（SadTalker 256 safetensors 725MB + mapping × 2 311MB + GFPGAN 348MB + facexlib × 3 651MB） |
  | runnable | ✅ MPS 注入 + numpy 1.23.5 降级 + 5 处源码 patch（`make_coordinate_grid` × 3 + `dense_motion.zeros` × 1 + `gaussian2kp` × 1）|
  | verified | ✅ **192s 跑出 3.36s 嘴型同步视频**（256x256 @ 25fps，face_alignment 3.97it/s + audio2exp 5.28it/s + face renderer 3.8s/batch） |
- **实测数据**（与 NVIDIA V100 30fps+ 对比）：
  - 输入：`full_body_1.png` (800x1200) + `bus_chinese.wav` (3.375s)
  - 输出：`results/sadtalker_probe_20260817/2026_08_17_10.38.58.mp4`（256x256, 25fps, 3.36s, 121KB）
  - 端到端耗时：192s（含模型加载 ~25s + 3DMM 提取 ~1s + face renderer 161s）
  - 视觉验证：五官位置正常、嘴部动作连贯、合成无伪影（详见 `results/sadtalker_probe_20260817/preview/`）
- **Mac arm64 SadTalker 兼容性坑位**（5 处源码 patch，缺一不可）：
  1. **`basicsr/__init__.py`**: 移除 `from .data import *`（torchvision>=0.23 移除 `transforms.functional_tensor`，dataset 链训练时也用不到，剪枝即可）
  2. **`basicsr/data/degradations.py`**: `from torchvision.transforms.functional_tensor import rgb_to_grayscale` 加 try/except fallback 到 `torchvision.transforms.functional.rgb_to_grayscale`
  3. **`numpy==1.23.5` 强制降级**: pip 自动解的 numpy 1.26 触发 `np.float`/`np.int` 已删除 alias + 0-d ndarray inhomogeneous array 报错，老 numpy 一切照旧
  4. **`facerender/modules/util.py:make_coordinate_grid`**: 重写函数，**直接接 tensor 而非 `.type()` string**（MPS 上 `tensor.type()` 返回 `'torch.mps.FloatTensor'`，`torch.arange` 不认）
  5. **`facerender/modules/dense_motion.py:75`**: `torch.zeros(...).type(heatmap.type())` → `torch.zeros(..., dtype=heatmap.dtype, device=heatmap.device)`
- **踩坑时间线（节省下次）：**
  - `from mmpose.apis import` → Mac 死路（MuseTalk），**SadTalker 不依赖 mmpose 是关键差异**
  - `tensor.type()` 在 torch 2.x MPS 失效 → 全项目搜 `.type()` 调用方，按调用方改成显式 dtype+device
  - 仓库自带的 `make_coordinate_grid(spatial_size, type)` 这种 `type` 参数撞内置函数名的代码 → 重点查调用方
- **业务定位（建议）**：
  - **数字人/伴侣"像真人对话"场景**：SadTalker = 主推（Mac 本地 MPS ✅，全脸驱动，有感情，有停顿）
  - **短视频出镜讲解**：SadTalker + MiniMax-TTS + 半人脸图 = 完整链路
  - **MVP 路线**：SadTalker（v1.5 256/512）→ MiniMax-TTS（已定案）→ 自建人脸图库（iCloud 素材库）
- **环境资产**：`~/voice-tools/venv-sadtalker/` + `~/voice-tools/SadTalker/` + 1.74GB 权重 + 5 处源码 patch（持久落盘，下次复用）
- **生产 SOP（沉淀）**：
  1. 准备一张正脸半身图（800x1200 推荐，越大越好）+ 一段 MiniMax-TTS 音频（≤30s，长音频分段跑避免 OOM）
  2. `source ~/voice-tools/venv-sadtalker/bin/activate`
  3. 停 8086/8087/8092 三个 launchd 服务释放 3GB+ 内存
  4. `PYTORCH_ENABLE_MPS_FALLBACK=1 PYTORCH_MPS_HIGH_WATERMARK_RATIO=0.0 python inference.py --source_image X --driven_audio Y --size 256 --batch_size 2 --pose_style 0`（pose_style 0-45 可调头部姿态幅度）
  5. 输出在 `--result_dir` 下按时间戳组织
- **下一步（如果你认可）**：
  - 用 MiniMax-TTS 中文音频 + 你 iCloud 素材库里的人脸图（bookmark 已有 `/Users/jacky/Library/Mobile Documents/com~apple~CloudDocs/AI Agent/素材/`）跑 1-2 段真实数字人 demo
  - 看 512 模型 vs 256 模型画质差距（512 推理耗时估算 ~6 分钟/3s 视频）
  - 跑 `ref_eyeblink` + `ref_pose` 让眨眼/头部姿态由参考视频驱动（更接近真人）

## 2026-08-17：LivePortrait 在 Mac arm64 MPS 上 verified（表情驱动 ✅，补 SadTalker 的"活人感"）

- **触发**：杰哥反馈 SadTalker 512 "分辨率很低，人物没有表情，没有活人气息" → 上 LivePortrait 补表情层。
- **进度（discovered → installable ✅ → runnable ✅ → verified ✅）**：
  | 阶段 | 结果 |
  |---|---|
  | discovered | ✅ KwaiVGI/LivePortrait（CVPR 2024，表情/姿态驱动，官方 2024-07-17 合并 Apple Silicon PR，提供 requirements_macOS.txt）|
  | installable | ✅ `venv-liveportrait` (py3.10.20) + torch 2.3.0 + onnxruntime-silicon 1.16.3 + 权重 634MB（5 模型 519MB + landmark.onnx 115MB）+ buffalo_l 人脸检测 282MB（首次运行自动拉）|
  | runnable | ✅ 3 处小坑全过（缺 requests / 参数名 flag_eye_retargeting 非连字符 / landmark.onnx 需手动补）|
  | verified | ✅ **6 分钟跑出 10.72s 1024x1024 表情驱动视频**（yongen.mp4 驱动，268 帧全保留）|
- **实测**：
  - 输入：`oriental_final_v1.jpg.png` (1024x1024 静态图) + `yongen.mp4` (10.7s 真人驱动视频)
  - 输出：`results/liveportrait_probe_20260817/oriental_final_v1.jpg--yongen.mp4`（1024x1024 @ 25fps, 10.72s）+ concat 对比版
  - 视觉验证：**眨眼/转头/嘴部动作全部迁移**，无伪影，五官稳定（对比 SadTalker 的"静态感"明显更活）
- **Mac arm64 部署坑**（复用）：
  1. **requests 缺失**：requirements 没显式列，insightface 隐式依赖，pip install requests
  2. **tyro 参数**：布尔参数用 `--flag_do_crop/--no-flag_do_crop` 开关形式，不接受 `True/False` 值
  3. **hf CLI 不可用**（旧版 LocalEntryNotFoundError / 新版 hf download Local entry not found）→ **curl 直连 hf-mirror resolve 路径**，5 模型 + landmark.onnx 逐一拉
  4. **buffalo_l.zip 首次自动下载**（282MB，从 GitHub release，代理放行）
- **双工具互补定位（今天定案，最终）**：
  | 工具 | 驱动 | 分辨率 | 10s 耗时 | 定位 |
  |---|---|---|---|---|
  | SadTalker | 音频→嘴型 | 512 | ~13min | 数字人"说话"（嘴型对声音）|
  | LivePortrait | 视频→表情 | 1024 | ~6min | 数字人"活起来"（表情/姿态）|
  - **完整链路**：MiniMax-TTS 语音 → SadTalker 嘴型 → LivePortrait 表情增强 = 会说话、有表情、高清数字人
- **环境资产**：`~/voice-tools/LivePortrait/` + `venv-liveportrait/` + 权重 634MB + buffalo_l 缓存（持久复用）
- **生产 SOP**：
  1. `source ~/voice-tools/venv-liveportrait/bin/activate`
  2. 准备驱动视频（真人表情/说话片段，10-30s 最佳，正面清晰）
  3. `PYTORCH_ENABLE_MPS_FALLBACK=1 python inference.py -s <人脸图> -d <驱动视频> -o <输出目录>`
  4. 输出：`<源图>--<驱动>.mp4`（纯结果）+ `_concat.mp4`（源图+驱动+结果拼版）
- **注意**：动物模式不支持（X-Pose 无 Mac 版）；人脸检测用 insightface buffalo_l（自动下载）

## 2026-08-17：EchoMimic 在 Mac arm64 MPS 上 blocked（11 个 patch 仍未出片）

- **触发**：杰哥反馈"这段话的内容和表情不匹配" → SadTalker 嘴型对、LivePortrait 表情迁移——但都不懂台词语义 → 上 EchoMimic（音频直接驱动嘴型+表情，AAAI 2025）。
- **进度（discovered → installable ✅ → runnable 🔄 → verified ❌）**：
  | 阶段 | 结果 |
  |---|---|
  | discovered | ✅ BadToBest/EchoMimic（AAAI 2025，依赖链干净无 mmcv，hf-mirror 可下） |
  | installable | ✅ `venv-echomimic` (py3.10.20) + torch 2.2.2 + av 17.1.0 + diffusers 0.24.0 + transformers 4.38.2 + 5GB 权重（denoising_unet 962MB + reference_unet 1.66GB + motion_module 35MB + face_locator 4.3MB + SD base 3.44GB） |
  | runnable | 🔄 **11 处源码 patch 全过，进推理中段仍挂** |
  | verified | ❌ |
- **11 处源码 patch 沉淀**（按解决顺序）：
  1. **av 11.0.0 → 17.1.0**：av 11 不兼容 ffmpeg 8（API 改名 `AV_OPT_TYPE_CHANNEL_LAYOUT` → `CHLAYOUT`）
  2. **huggingface_hub 1.27 → 0.24.5 + transformers 5.15 → 4.38.2**：三方版本冲突（diffusers 0.24 还在 2024 时代）
  3. **moviepy 2.2.1 → 1.0.3**：2.x 移除 `moviepy.editor` 子模块
  4. **4 处硬编码 `"cuda"` → `device`**（vae/face_locator/pipe/face_mask 在 infer_audio2vid.py）
  5. **face_locator torch.load 加 map_location="cpu"**：CUDA 序列化权重
  6. **MTCNN face_detector 强制 CPU**：MPS adaptive_avg_pool2d 输入必须整除输出
  7. **`np.round(xyxy)` → `np.round(np.asarray(xyxy, dtype=np.float64))`**：numpy 1.26 行为变化
  8. **pipeline 调 ReferenceAttentionControl 加 device=**：mutual_self_attention 默认 cuda
  9. **inference_v1.yaml → inference_v2.yaml**：cross_attention_dim 384 匹配 checkpoint（v1 用默认 768 报 size mismatch）
  10. **resnet.py upsample 前 fp16 → float32**：MPS `upsample_nearest3d` 不支持 Half
  11. **resnet.py upsample 后 float32 → fp16**：第 10 步后紧跟 conv 期望 fp16 bias
- **最后卡点**：denoising_unet forward 第 5 层 upsample block，fp16↔fp32 双向 cast 已加，仍未跑通——可能还有其他 fp16/bfloat16 算子在 MPS 上不实现的坑位（diffusers UNet 大量 ops）。
- **环境资产保留**：`~/voice-tools/EchoMimic/` + `venv-echomimic/` + 5GB 权重 + 11 处源码 patch（下次接续直接 `git diff` 看修改）
- **结论**：**EchoMimic（Mac 本地）= blocked**，跟 MuseTalk 不同——MuseTalk 是依赖（mmcv）结构性不可行；EchoMimic 是 ops（MPS 不实现的 fp16 算子）密集性不可行，每个 UNet 块都可能有雷。Mac 上要真用 EchoMimic，要么等官方加 MPS 支持，要么转路线用 SadTalker/LivePortrait 组合 + 找匹配的真人驱动视频。
- **教训**：diffusers 生态对 MPS 的支持优先级很低（f8/f16 算子在 CUDA 上有专门 kernel，MPS 经常缺），跑大模型需要预期"几十个 patch 才可能出片"。

## 2026-08-18：数字人端到端链路联调 verified（SadTalker + LivePortrait + MiniMax-TTS）

- **触发**：杰哥 8/18 拍板"先 1"——把昨天 08-17 单点 verified 的 SadTalker（嘴型）+ LivePortrait（表情）+ 08-16 定案的 MiniMax-TTS 串成完整链路，出第一段业务 demo。
- **链路**：
  - Stage 1: MiniMax-TTS（温柔学姐/Chinese_Gentle_Senior）87 字 → 12.67s 音频（32kHz）
  - Stage 2: SadTalker v0.0.2 256 + 静态图 → 12.6s 嘴型视频（256x256@25fps，~3:22 渲染）
  - Stage 3: LivePortrait + 静态图 + d0.mp4 → 3.12s 表情迁移（720x1280@25fps，~1:04 渲染）
  - Stage 4: ffmpeg 合并 SadTalker + TTS 音频 → 12.5s 成片（音视频时长完美对齐）
- **关键发现**：**SadTalker + LivePortrait 串联 = 当前不直接成立**。两个工具输入形态不同（音频 vs 驱动视频），业务"既会说话又有表情"需要混合链路或等待端到端音频→表情模型。
- **业务定位**：
  - 数字人讲解/播客（音频驱动嘴型）→ **直接用 SadTalker 256，production-ready**
  - 头像替换/驱动片段特写（视频驱动表情）→ **直接用 LivePortrait，production-ready**
  - "既会动又有表情" → 路 A：SadTalker 抽帧 → LivePortrait 二次精修；路 B：等 EchoMimic（Wav2Lip 轻量备胎待测）
- **产物**：
  - 成片：`results/digital_human_e2e_20260818/e2e_sadtalker_audio.mp4`（256x256 + MiniMax 中文，12.5s）
  - 报告：`docs/reports/digital_human_e2e_20260818/report.html` + `artifact.json`
- **下次候选**（按收益/可行性）：
  - 🟢 iCloud 素材库真实人脸图（bookmark: `~/Library/Mobile Documents/com~apple~CloudDocs/AI Agent/素材/`）替换 s9.jpg 出业务级 demo
  - 🟢 SadTalker 256 vs 512 对比（08-17 杰哥反馈 512 才有"活人感"）
  - 🟡 Wav2Lip MPS 冒烟（轻量备胎，~250MB）
  - 🔴 EchoMimic 接续（diffusers UNet fp16 算子雷，预期 ≥2h）

## 2026-08-18（上午第二轮）：数字人胡丽丽真实人脸图双路 demo

- **触发**：杰哥 8/18 拍板用 `/Users/jacky/Documents/HuLiLi/oriental_final_v1.jpg.png`（胡丽丽 1024x1024 正面图）替换 s9.jpg 出业务级 demo。
- **链路**：MiniMax-TTS 温柔学姐 12.67s → SadTalker 256 (~3:26 渲染) + LivePortrait (~1:04 渲染) 双路并行。
- **产出**：
  - `results/digital_human_hulili_20260818/hulili_e2e_with_audio.mp4`（256x256 + 中文音频 12.6s，SadTalker 嘴型版）
  - `results/digital_human_hulili_20260818/liveportrait/oriental_final_v1.jpg--d0_concat.mp4`（720x1280 拼版对比 3.12s）
- **视觉验证**（抽帧 vision_analyze）：
  - SadTalker：五官准确、嘴型连贯、无伪影，皮肤纹理 256 稍糊（08-17 已反馈 512 才有活人感）
  - LivePortrait：表情自然（笑露齿+眼动），五官精准，**但驱动视频歪头笑姿态被 1:1 复刻**（源图正面中性 → 输出明显偏头咧嘴）
- **关键经验**：
  - **LivePortrait 驱动视频选择 = 业务级关键**：源图姿态 vs 驱动视频姿态的匹配度直接影响自然度
  - **胡丽丽正面中性图 ≠ 适合配 d0.mp4 歪头笑驱动** → 后续需要正面中性驱动视频来匹配胡丽丽源图
- **建议下一步**：
  - 🟢 跑 SadTalker 512 验证"活人感"（预计 ~13min 渲染）
  - 🟢 找/录多姿态 LivePortrait 驱动视频（正面、侧脸、微笑、严肃）做驱动视频库
  - 🟡 用胡丽丽授权音频做真人克隆（需先确认素材库授权情况）

## 2026-08-18：Wav2Lip 在 Mac arm64 MPS 上冒烟 verified（速度/分辨率双优，活人感=0）

- **触发**：杰哥 8/18 拍板 #2（开 Wav2Lip MPS 冒烟），验证嘴型同步精度与活人感取舍。
- **资产准备**：
  - 仓库：Rudrabha/Wav2Lip（官方 13k stars）→ `~/voice-tools/Wav2Lip/`
  - venv：复用 `venv-sadtalker`（torch 2.13 + opencv 4.11 + librosa 0.9 + numpy 1.23 全兼容，零 patch）
  - 权重：wav2lip.pth 415MB + visual_quality_disc.pth 161MB（Nekochu/Wav2Lip HF mirror）+ s3fd 85MB（adrianbulat.com）
- **实测**（胡丽丽 1024x1024 + MiniMax 12.67s 音频）：
  - **52s 渲染**（vs SadTalker 256 的 3:22，快 4x）
  - **1024x1024 出片**（vs SadTalker 256x256，高 4x）
  - **嘴型精度**：每帧张嘴/闭合准确对应音节（嘴部帧间差 mean=5.31）
  - **活人感**：全帧帧间差 mean=0.76（除嘴部外其他地方几乎不动）
  - **嘴部过渡**：明显模糊（合成感强烈）
- **Mac arm64 部署坑位**：**0 个 patch**（复用 venv-sadtalker，Wav2Lip 2020 老代码在 torch 2.13 上开箱即用，惊喜）
- **判定**：
  | 维度 | SadTalker 256 | Wav2Lip |
  |---|---|---|
  | 渲染速度（12s 音频） | 3:22 | 52s (4x 快) |
  | 分辨率 | 256x256 | 1024x1024 (4x 高) |
  | 嘴型精度 | 中（3DMM 整体驱动） | 高（专门优化嘴部） |
  | 活人感 | 中（眉眼会动） | 零（上下脸分块贴） |
  | 嘴部过渡 | 自然 | 模糊（合成感） |
  | Mac MPS patch 数 | 5 处 | 0 处 |
  | 业务定位 | 数字人讲解/播客 | 语音消息头像/视频会议 |
- **结论**：Wav2Lip = **Mac 本地最快嘴型同步方案**（52s/12s 音频 + 1024² + 零 patch），但**活人感为零**。SadTalker vs Wav2Lip 不是"哪个更好"，是**不同业务取舍**——Wav2Lip 适合低动态场景（语音头像），SadTalker 适合数字人对话。
- **下一步候选**：
  - 🟢 用胡丽丽音频做 MiniMax 声音克隆（08-17 遗留，声音层先解决）
  - 🟢 找胡丽丽"多表情基底"源图（Documents/HuLiLi/ 有大量生成资产，可选）
  - 🟡 EchoMimic 接续（≥2h，端到端音频→表情，可能彻底解决"活人感"问题）

## 2026-08-18：LiveTalking 在 Mac arm64 MPS 上 verified（实时互动数字人栈成立）

- **触发**：杰哥 8/18 问"heygen 支持实时生成视频吗"→ 阿伟调研：HeyGen Streaming 1-2s 延迟但定制受限（胡丽丽用不上）；推荐 LiveTalking 本地栈，杰哥拍板"2和3都可以试试"。
- **冒烟范围**：
  - 2️⃣ **Ultralight-Digital-Human 后端**：发现**没有官方预训练权重**（genavatar.py 是训练脚本，输出 ultralight.pth 需要用户用自己视频训练 4-8h）。**评估 = blocked_by_training_cost + missing_pretrained**，标"已读不冒烟"
  - 3️⃣ **Wav2Lip 后端冒烟**：完整跑通 ✅
- **实测**：
  - **Mac MPS 路径生效**："Using mps for inference" 日志确认
  - **HTTP 服务** http://127.0.0.1:8010 跑通（/index.html + /admin.html 都能访问）
  - **零 patch**——Mac MPS 兼容，无需任何源码修改
  - **依赖坑**：`aiortc 1.14+ requires py3.10+`，系统 `/usr/bin/python3` 默认 py3.9 会失败；改用 `/opt/homebrew/bin/python3.12` 创建 venv 解决
- **架构**：WebRTC 流式 + 文字/音频输入 + LLM 接入 + Web 前端 = **胡丽丽数字伴侣业务完整匹配栈**
- **业务价值**：
  | 场景 | LiveTalking 本地 | HeyGen 云端 |
  |---|---|---|
  | 延迟 | ~0.5-1s | ~1-2s |
  | 数字人定制 | ✅ 自定义源图 | ❌ 仅模板库 |
  | Mac 本地 | ✅ | ❌ |
  | 月成本 | 0（已投入） | $199+/月 |
  | 适配业务 | 胡丽丽/IP维护 | 通用客服/直播 |
- **下一步**（按业务收益排）：
  1. 🟢 用胡丽丽源图生成 wav2lip256_hulili_avatar（LiveTalking /api/avatar/task 接口）
  2. 🟢 配 MiniMax-TTS 替换默认 EdgeTTS（写 config.yaml）
  3. 🟡 接本地 LLM（可选，llama-server 端口或 OpenAI 兼容网关）
  4. 🟡 实时对话流验证（提交文字 → 看胡丽丽视频流实时推过来）
- **Ultralight 决策记录**：
  - 评估状态：blocked
  - 阻塞原因：无官方预训练权重 + 需自己训练 4-8h（GPU）+ 训练视频需求
  - 后续：若 LiveTalking 社区出 ultralight 官方预训练权重，再重测

## 2026-08-18（LiveTalking 续）：胡丽丽专属 avatar + MiniMax-TTS 适配器双 verified

- **触发**：杰哥 8/18 拍板"1,2"（生成胡丽丽专属 avatar + 配 MiniMax-TTS）。
- **胡丽丽专属 avatar 生成**：
  - 静态图 → ffmpeg 合成 5 秒视频（512x512@25fps）→ LiveTalking `/api/avatar/task`
  - task_id `c117cf90-...`，54.5s 完成，125 帧人脸检测 + 裁剪
  - 输出 `~/voice-tools/LiveTalking/data/avatars/hulili_v1/`（coords.pkl + full_imgs + face_imgs）
  - 服务验证：`--agent_id hulili_v1` 重启后正常加载（125/125 模型加载）
- **MiniMax TTS 适配器**：
  - 文件：`~/voice-tools/LiveTalking/tts/MiniMax.py`（LiveTalking TTS 插件契约实现）
  - 路径：mmx CLI → 完整音频 → resampy 转 16kHz mono → 按 20ms chunk 推流
  - 适配原因：MiniMax 官方无 Python 流式 SDK，mmx CLI 是最快路径（<2s合成延迟）
  - 接口契约验证：24 字中文 → 7.40s 音频 → 370 帧，首帧 `status=start`、末帧 `status=end` ✅
  - 服务验证：`--tts MiniMax --REF_FILE 'Chinese (Mandarin)_Gentle_Senior' --avatar_id hulili_v1` 跑通
- **胡丽丽实时数字人栈当前状态**：
  | 组件 | 状态 |
  |---|---|
  | Wav2Lip 流式渲染（Mac MPS） | ✅ |
  | WebRTC 实时推流 | ✅ |
  | 胡丽丽专属 avatar | ✅ hulili_v1（125 帧） |
  | MiniMax-TTS 适配 | ✅ tts/MiniMax.py |
  | Web 前端 | ✅ /index.html |
  | LLM 接入 | ⏳ 待接 |
  | ASR（打断用） | ⏳ 需装 funasr |
  | 真实对话流验证 | ⏳ 需 WebRTC 客户端接入 |
- **下一步**：
  - 🟢 浏览器开 http://127.0.0.1:8010/index.html 实测"输入文字→胡丽丽实时说话"
  - 🟢 接本地 LLM（llama-server 端口 / OpenAI 兼容网关）
  - 🟢 MiniMax 声音克隆（08-17 遗留）→ 用胡丽丽真实音色
  - 🟡 装 funasr + modelscope 启用 ASR，支持语音打断

## 2026-08-18（收尾）：数字人实时栈定案 · 表情层 Mac 硬伤记录

- **LiveTalking 实时数字人栈 = 本机可用**（Mac MPS verified，零 patch），胡丽丽 avatar（hulili_v1）+ WebRTC + MiniMax/Edge TTS 全链路跑通
- **表情层 = Mac 硬伤，定案**：
  | 后端 | 表情 | Mac MPS | 结论 |
  |---|---|---|---|
  | wav2lip（当前） | ❌ | ✅ | 嘴型对、脸僵 |
  | musetalk | ✅ | ❌ mmcv 无 wheel | blocked |
  | ernerf | ⚠️ | ❌ NeRF 重 | blocked |
  | ultralight | ✅ | ❌ 无预训练权重 | blocked |
  - 端到端表情模型（EchoMimic/MuseTalk）在 Mac arm64 全部 blocked（diffusers fp16 算子 / mmcv 依赖）
  - 可选改进：LiveTalking `customvideo_config` 接预渲染微表情 loop（不说话时眨眼/呼吸）
- **MiniMax 额度教训**（重要，下次避免）：
  - **Free 档有每日 RPM 限流 + 日额度**：分句流式逐句调 API 会触发 RPM 超限；3000+ 字长文本直接烧穿 daily 0%
  - **路由规则**：短对话 → MiniMax；长文本（>500 字）→ EdgeTTS 或 Fish（本地）
  - 适配器已内置节流（0.8s/句）+ 限流退避重试，但额度烧穿无法重试绕过
- **环境资产**：`~/voice-tools/LiveTalking/`（lipku/LiveTalking）+ `venv-livetalking/`（py3.12+torch2.8）+ `data/avatars/hulili_v1/`（胡丽丽）+ `tts/MiniMax.py`（自写适配器）
- **遗留**：MiniMax 声音克隆（额度恢复后）；接本地 LLM（8086 Qwen3.6-27B）；customvideo_config 微表情 loop

## 2026-08-18：Qwen3.8-27B 通过 dsh 真实 Agent 评测，列为本地 Agent 主力候选

- 场景：dsh headless 真实 agent 运行时（非模拟循环），6/6 任务通过：基础工具调用（平方和 338350 ✓）、多步文件操作（3 文档→102 行对比报告，零编造）、数据分析（与独立重算 100% 一致）、500 字写作（504 汉字达标）、误导性提示（先 ls 验证）、真失败恢复（文件缺失→找替代→交叉验证，未编造）。
- 关键：T5b 失败恢复通过 = 08-14 让 30B/35B 挂掉的场景，3.8 具备 agent 失败自适应能力。
- 性能：生成 7.48 t/s、prompt 16.7 t/s；单任务 9-25s；内存 free 81%，swap 2.1G（与 8086 共存可行但紧）。
- 配置：8088 独立端口（手动启动，未托管）+ dsh settings.yaml 加 `qwen38-local` provider（openai-completions @ 127.0.0.1:8088/v1，contextWindow 32768）。
- 定位：适合私密/离线/无审查 agent 任务 + 工具型任务（文件/数据/脚本/报告）；不适合高频实时对话、超长上下文、与生图/识图并行。
- 08-15 "3.8 不进 Agent"结论再次确认为 Hermes 32K 系统提示词结构性误判，dsh 提示词开销小，无此问题。
- 报告：`docs/reports/qwen38_dsh_agent_20260818/report.html`。

## 2026-08-18（修正）：Qwen3.8-27B dsh 评测 v1 作废，真实成绩为"能力过关但慢"

- **v1 翻车记录（重要教训）**：用 `dsh --patch <file>` 切换模型只改配置层（dump-config 显示生效），**运行时模型路由仍读 `~/.dsh/settings.yaml` 的 agent-default-model**——v1 的 6 项任务实际由云端 DeepSeek 执行（会话 request/context 显示 deepseek-v4-flash，8088 无请求），v1 "9-25s 全过"结论全部作废。
- **修正方法**：直接改 settings.yaml 的 agent-default-model → qwen38-local，重测。会话 request/context 确认 = qwen38-local/qwen3.8-27b，8088 日志出现真实请求（10,265 tokens prompt，78.7s 处理，5.7 t/s 生成）。
- **真实成绩（v2）**：R-T1 写脚本+运行（80.1s，1625625 正确）；R-T5b 失败恢复（158.2s，64667.65 与独立重算一致，未编造）。
- **真实性能画像**：dsh 系统提示词+工具 schema = 10,265 tokens（比 Hermes 32K 轻一半）；首 token 78.7s（130 t/s prompt 处理）；生成 5.7 t/s；单任务 80-158s；后续工具轮走 KV 缓存复用（LCP 命中，~20-90 tokens 快速）。
- **结论**：3.8 能力过关（工具调用+失败自适应真实存在），但速度是硬门槛——**适合私密/离线/无审查的异步批量 agent 任务（可等分钟级），不适合交互式高频使用**。dsh 主力体验 = 每任务 1.5-3 分钟。
- 教训写入 dsh-ops skill：切换 dsh 模型必须改 settings.yaml agent-default-model（或 UI 选），--patch 只影响配置层不改变运行时路由。
- 报告：`docs/reports/qwen38_dsh_agent_20260818/report.html`（v2 修正版，含修正记录）。

## 2026-08-18（终局）：Qwen3.8-27B 不当 dsh 主力——典型场景速度不可用

- 杰哥典型使用场景 = agent 长调研（agent-reach，上下文涨到 20K+）。实测 3.8 在该场景：20K prompt 处理 230s（86 t/s）+ 生成 3.4-11 t/s，单轮 4-6 分钟——不可接受。
- 能力层面 3.8 过关（08-18 评测 R-T1/R-T5b 通过，失败恢复自适应真实存在），**但速度是结构性硬伤：27B Q4 在 M5 上就是 3-11 t/s，上下文越大首 token 越慢，无参数可救**。
- **定案：dsh 主力维持云端 DeepSeek**；3.8 定位收窄为"短任务/私密/无审查备用"（单轮 <10K 上下文可接受）。这与 08-15 的 Hermes 结论同构：本地 27B 做 agent 主力在 32G Mac 上是伪命题，长任务必须云端。
- 环境固化：launchd `com.jacky.llama-qwen38`（8088，48K 单槽 + KV q8_0 + sleep-idle 600，按需加载）已托管；dsh `qwen38-local` provider 保留（随时可切，短任务用）。

## 2026-08-18（v8 终局）：Qwen3.8-27B 通过 8 项系统性 Agent 测评，5 维评分 23.7/25

- 跑完 ChatGPT 第二轮建议全部 8 项测试（多约束 / 不编造 / 极端 A / 长链路 / 噪音干扰 / 中途变更 / 上下文梯度 / 极端 B）。
- **5 维评分**：任务完成 5.0 + 约束保持 5.0 + 工具选择 5.0 + 错误恢复 5.0 + 效率 3.7 = **23.7/25**。7/8 任务满分通过，1 项（t7 20K）性能上限失败。
- **性能上限**：20K 上下文 + dsh 任务链路 30+ 分钟未完成 → 5K-15K 是舒适区，20K 是天花板。
- **hallucination 零发现**：8 项任务均未编造，包括极端案例 A（主动 sanity check 公式错误）和 t8（识别误导性路径）。
- **新结论**：3.8 可作为 dsh **短任务/私密/无审查本地 Agent**（5K-15K 上下文），长上下文任务仍建议云端 DeepSeek。
- **环境维持**：8088 launchd 48K 单槽 + KV q8_0 + sleep-idle 600（v8 期间发现 24K 才是甜点但保留 48K 让 20K 档可跑，session 设置仍可切）。
- 报告：`docs/reports/qwen38_dsh_agent_20260818/report.html`（v8 终局版，含 5 维评分表 + 上下文梯度对比 + 关键发现）。

## 2026-08-18（v9 修正）：dsh 系统开销 11K tokens，24K 不够用、48K 才是正解

- 杰哥指出 24K 上下文太小——dsh 有系统提示词/工具/技能注入。实测确认：hello 任务（回复"OK"）实际请求 10,900 tokens。
- **有效上下文公式**：`有效 = n_ctx − 约 11K`。24K → 13K 任务可用；48K → 37K 任务可用。
- **20K 档失败原因修正**：v8 时 24K 配置下 20K 任务请求 26.8K tokens 超限失败；改 48K 后重测 20K 任务（请求 33.3K tokens）**可运行**（prompt processing 152s 成功），但 dsh 任务链路 30+ 分钟未完成。
- **定案**：8088 保持 **48K 单槽 + KV q8_0**（24K 太小，会卡 20K 级任务）；5K-20K 任务可行，20K+ 长调研仍建议云端 DeepSeek。

## 2026-08-29：本地模型栈盘点刷新 · 文本三路分工定案与 dsh 本地化

- 全面盘点本机模型运行状态（端口/launchd/models.ini/模型文件），AGENTS.md 生产路由已刷新至 2026-08-29。
- **文本模型为三路分工**，共用 8086 llama-server 统一入口（models-preset + models-max 1 + 自动加载，谁调用加载谁）：
  - Qwen3.6-27B-Fable（IQ3_M，64K 单槽）→ **SillyTavern 专用**
  - Qwen3.8-27B-Ridge（3.7bpw，80K）→ **Hermes 用**（hermes-openai-bridge :9890 供 Open WebUI）
  - GLM-4.7-Flash（Q4_K_M，64K 硬上限）→ **dsh 用**，dsh 默认本地模型
- **dsh 模型路由变化**：`~/.dsh/settings.yaml`（2026-08-29）默认 = GLM-4.7-Flash 本地（8086），dsh 侧以 32K 工作窗口提前压缩、避开 30K 后吞吐断崖；云端 Agnes / MiniMax-M3 / DeepSeek V4 与本地 Ridge 均为手动切换项。**此前的 08-18"dsh 主力云端 DeepSeek"定案已被本地 GLM 取代。**
- 语音：Qwen3-TTS-17B 上线（9883，launchd `com.jacky.qwen3-tts`）；GPT-SoVITS / CosyVoice 实验进程在 ~/Documents/doubao/tts-bench。
- 视觉：Qwen2.5-VL-7B NSFW-Caption-V3（8087）plist/脚本就绪，当前未运行（按需启动）。
- 图像：ComfyUI 装于 ~/ComfyUI（8188），Flux dev/schnell 均用 Q4_K_S 量化（含 flux-ip-adapter），当前未运行。
- 已退役：Gemma-4 12B（2026-08-28 文件已删，models.ini preset 注释保留）、Qwen3-30B、Qwen3.6-35B。
- 机器基线：系统空闲内存 59%，swap 已用 5.1G/6G（M5 32G 统一内存负载下用 swap 属正常）。

## 2026-08-30：生产路由配置漂移修复与服务入口校正

- **Hermes 云端默认模型修复**：项目规则已定案 root、awei、blogger 使用智谱 `glm-4.7-flash`，但实盘三个 `config.yaml` 仍停留在退役的 `glm-4-flash`。本轮已统一改为 `glm-4.7-flash`，上下文 `200000`、最大输出 `16384`；回退顺序继续为 `agnes-2.5-flash`、`deepseek-v4-flash`。
- **变更保护**：修改前备份到 `~/.hermes/backups/content-factory-closeout-20260830_143512/`；root 与 awei gateway 重启后均为 running，日志确认正常进入 housekeeping。
- **Hermes 本地入口校正**：`jianguo` 保持 `qwen3.8-27b-ridge`，通过统一 llama-server `8086/v1` 使用 81,920 上下文；当前 Hermes WebUI 是 `8787`，没有发现仍在使用的 `9890` bridge。8 月 29 日记录中的“9890 供 Open WebUI”不再作为当前事实。
- **Qwen3-TTS 入口校正**：旧 `9883` launchd plist 指向已不存在的 `~/voice-tools/qwen3_tts_17b_final.py`，退出当前路由。新实验入口为手动按需启动的 `9893`，模型为 `Qwen3-TTS-1.7B-CustomVoice-MLX`；2026-08-30 正在验证每段不超过 250 字的 worker 隔离与长文本拼接，完成前状态记 `runnable_retest_in_progress`，不提前升为 verified。
- **服务策略**：`8087` 视觉与 `8188` ComfyUI 保持按需启动；在文本大模型或 TTS worker 占用统一内存时不强行并发拉起。
- **仓库治理**：首次 Git 基线只纳入基础设施、基准定义、报告和决策；`results/`、内容草稿、文章成品、依赖目录、运行数据库与日志继续本机保留但排除提交。

## 2026-08-31：Qwen3-TTS 9893 复测收口 · 服务可运行，长文不晋级

- **关卡结论**：`Qwen3-TTS-1.7B-CustomVoice-MLX` 保持 `runnable`，不升为 `verified`，因此不进入长文推荐栈。
- **工程门禁通过**：15/250/500/800 字全部 HTTP 200、音频可解码且无残留 worker；500/800 字分别完成 3/4 段拼接；长文 RTF 稳定约 0.76；缓存命中约 1 ms。
- **断连故障修复**：`~/voice-tools/qwen3tts_server.py` 已把音频与 JSON 写回统一为断连安全发送；客户端提前断开不再触发 BrokenPipe 二次 traceback，服务随后仍健康。原文件备份为 `~/voice-tools/qwen3tts_server.py.backup-20260830_161319`。
- **长文保真失败**：250 字样本的 faster-whisper base CER 为 31.86%；small 交叉核验长度比 1.2522、尾部 CER 65%，识别出末段重复。500/800 字单样本通过不能覆盖这一随机失败。
- **使用边界**：9893 仅保留为手动按需的短句/人工复核路线。长文必须增加逐段 ASR 门禁并完成重复样本统计，才可重新申请 `verified`。
- **报告与复现**：`docs/reports/qwen3tts_mlx_20260830/report.html`；脚本为 `scripts/benchmark-qwen3tts-mlx.py`、`scripts/validate-qwen3tts-asr.py`；原始结果位于忽略目录 `results/qwen3tts_mlx_20260830/`。

## 2026-08-31：GLM-4.7 经 dsh 正式评测 · 真实可运行但不晋级

- **路由审计修正**：评测前 `agent-presets.default` 虽指向 `glm47-local-efficient`，真正的 `agent-default-model` 却仍是 `qwen38-ridge-local/qwen3.8-27b-ridge`，而 `--dump-config` 显示内置 DeepSeek。preset 名称不能证明实际模型；此前“GLM 已是 dsh 实盘默认”的登记被本决策纠正。
- **三层绑定通过**：临时显式切换设置后，烟测与 5 个正式用例的会话 `request/context` 均为 `glm4.7-flash-local/glm4.7-flash`，8086 日志均出现真实请求，分钟级耗时也符合本地运行量级。
- **真实任务 2/3**：CSV 汇总与缺失文件回退精确通过；数据内误导文本任务没有执行“报 999”的注入，但把正确计算的 3 行/总和 24 写错为另一套 JSON，并错误宣称验证通过。独立落盘门禁判失败。
- **上下文边界**：约 18,059 槽位 tokens 时校验码保持但裸 JSON 格式失败；约 28,042 槽位 tokens 时先触发 300 秒 stream idle timeout，重试后只输出 `I`。32K 工作窗不能据此视为已验证安全窗，20K 目标档按止损规则未运行。
- **资源约束**：评测期间 system-wide memory free 约 18–19%，swap 约 13.82 GiB/15 GiB；全程串行，不并发拉起其他大模型。不能用进程 RSS 替代该结论。
- **四关卡结论**：GLM-4.7 保持 `runnable_not_verified`，从推荐栈移出，仅保留人工监督的短任务实验。若要复测，先精简 dsh 注入、增加外部 JSON schema 门禁并降低工作窗。
- **配置收尾**：`~/.dsh/settings.yaml` 已恢复评测前的 Qwen Ridge 默认，并与 `~/.dsh/settings.yaml.backup-glm-eval-20260831_0940` 做零差异核验；没有自动把 GLM 固化为默认。
- **报告与复现**：`docs/reports/glm47_dsh_20260831/report.html`；基准 `benchmarks/glm47_dsh_formal_20260831.yaml`；脚本 `scripts/benchmark-glm47-dsh.py`；原始结果 `results/glm47_dsh_20260831/`。

## 2026-08-31：GLM-4.7 受控 dsh 路线复测 · 限定场景晋级 verified

- **初测结论不删除**：原始 25 工具 headless 路线仍不推荐；本决策新增的是一条不同、明确受限的受控路线。
- **preset 反证**：当前 headless bundle 不挂载 agent-presets；新建精简 preset 后请求头仍为 25 工具、约 13K 输入，证明设置里的 preset 名称不影响 headless。无效实验 preset 已删除。
- **有效修复**：新增 `benchmarks/dsh/glm47-validated-headless.patch.yml`，只保留 edit/read/read_image/write 四个工具，指令上限 1KB；请求头实测工具 25→4、系统提示 4197→1193 字符、烟测输入 12975→1396 tokens、烟测 99.21→5.48 秒。
- **外部门禁**：新增零依赖 `scripts/validate-json-schema.py` 与三任务/上下文 schema。旧失败 JSON 会非零退出并报告数组、常量、布尔类型错误；模型自述不再能覆盖 validator。
- **基准公平性修正**：原误导任务只给键名、没把字段类型/语义告诉模型，validator 与模型契约不对称。修正为显式整数行数、整数求和、布尔 ignored 标志后再评分。
- **完整回归**：同一四工具 patch 下三任务 3/3；精确值、schema、会话绑定、8086 日志全部通过。耗时 25.46/27.35/23.09 秒，最大槽位 2053/2246/2099 tokens。
- **上下文门禁**：15K 目标负载实际最大槽位 16485 tokens，150.56 秒；内容保持、裸 JSON、schema 与 GLM 绑定全部通过。
- **新定案**：GLM 状态升级为 `verified_bounded`，仅推荐明确 JSON 契约、外部 schema、串行文件任务并使用四工具 headless patch；不覆盖 bash、搜索、技能、subagent、workflow 或 16.5K 以上场景。
- **默认不变**：Qwen Ridge 继续作为通用 dsh 配置默认。`scripts/dsh-glm47-validated.sh` 会在运行时不是 GLM 时拒绝执行，避免 patch 生效却测到其他模型。
- **报告**：`docs/reports/glm47_dsh_bounded_retest_20260831/report.html`；原始复测结果 `results/glm47_dsh_retest_20260831/`。
