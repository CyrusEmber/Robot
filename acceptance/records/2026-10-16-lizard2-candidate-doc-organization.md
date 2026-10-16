# lizard2 候选计划文档整理

## 适用范围

2026-10-16 用户要求整理 `work/active/lizard2-body-drive-candidate.md`。本次仅重排活跃计划与交接指针，不执行候选实验、不改变工程取值、不关闭事项。整理前基线为本次提交父版本的总项；本记录是执笔者迁移自检，不是 D 的独立审核。

## 验收条件

- 总项保留当前目标、A–E 路由、A/P1–P4 出口、B/C 标定前置、D 最终比较与关闭条件。
- 接线方案完整迁入脚手架创建的活跃专项；原处删除详细正文并留路由，未完动作不归档、不取消。
- 历史要求合并后仍能定位当前约束及决定依据；已有专项继续维护详细构型、限位 PD 方法和相位契约。
- 文档格式、引用及提交所需静态检查通过；检查只证明文档/机制一致性，不证明候选能力。

## 结果

### 正文迁移对照

| 原总项内容 | 当前唯一落点 | 处理 |
|---|---|---|
| 骨骼改名表、命名兼容及采用边界 | `work/active/lizard2-candidate-wiring.md` 的骨骼改名节 | 原文迁移，前后肢角色、前后缀、末端 link 与旧名退出要求保留 |
| E1–E5、消费者清单、绑定拒错、当前切片/共用文件归属 | 接线专项同名节 | 原文迁移；增加自身路由与关闭条件，最终仍随总项 D 一次审核 |
| 下一步、A–E 当前执行关系 | 总项同名节 | 合并重复叙述，路由到现有重构/限位 PD 专项及新增接线专项 |
| 目标及 A1 多次用户决定 | 总项“目标与当前结构要求”及 evidence 指向的原始决定记录 | 合并为当前朝向、骨架/掌根、实体一致性、中立外形及依据边界，不重复历史读数或作废状态 |
| A2/P1–P4 | 总项 A2 | 按阶段统一列验证内容、前提、失败回交，保留几何可先于完整 PD 推进 |
| A3/C0–C4 | 总项 A3 | 保留旧回归命令、负例、隔离写入约束及当前入口路由；不虚构尚未核定的命令 |
| A4 | 总项 A4 | 保留用户确认、P1–P3 出口及 P4/采用边界，证据手续改指接线专项 E4 |
| B/C/D、关闭条件、边界 | 总项同名节 | 原文保留，仅把关闭条件集中放到 D 后 |
| 接触协议的 E3 writer 交接 | `work/active/lizard2-contact-protocol.md` 动作 7 | 改为接线专项的具体链接 |

整理不改变总项或现有专项状态。接线专项以 in_progress 承接原 E 在办动作；不增设 D 前的审核闸门。标定与最终比较分离、S5 阈值先于 D、正式采用/训练归 S6 的关系保持。

### 自检

- 总项由 248 行、21666 字符收敛到 114 行、9495 字符（统一 LF、忽略末尾换行），字符量减少约 56%；详细接线计划改为按需读取。
- 逐字比对确认原“骨骼改名”至 E5 的正文完整进入接线专项，B/C/D 原文保留；关闭条件与边界亦未改变。A 的压缩按上表人工核对保留结构要求、正反例、前置与停止条件。
- 三份活跃文档中的 14 个本地 Markdown 链接目标均存在；E3/E5 锚点对应接线专项实际标题。`git diff --check` 通过。
- `check_work_docs.py` 通过；`hooks/pre-commit` 全部通过：仓根/脚本横幅、framework pin 严格检查及 self-test、DR parity、版本文档、work 文档、obs 协议（含 live cfg 比较）。保留既有告警：IsaacLab 工作树有未提交改动、退休 lizard 版本缺少旧 tag；没有绕过闸门。

## 证据引用

- 整理前后内容：本次文档提交与其父提交的差异；复读 `git show <本次文档提交> -- work/active/lizard2-body-drive-candidate.md work/active/lizard2-candidate-wiring.md work/active/lizard2-contact-protocol.md`。
- 新建入口：`rl_exp/tools/verify/check_work_docs.py --scaffold lizard2-candidate-wiring --title "lizard2 候选接线与真实消费者验证" --scope "rl_exp/blender, rl_exp/tasks, rl_exp/tools, ablation_harness" --landing "rl_exp/tasks/joint_names.py, rl_exp/tools/diagnose/palm_spatial_runtime.py, rl_exp/tools/verify/obs_protocol_live.py, ablation_harness/baseline_metrics.py" --apply`。
- 工程证据继续从总项、重构专项、限位 PD 专项及接线专项各自 evidence 取用，原始记录不改写。

## 未覆盖边界

未重跑 Blender、IsaacLab 诊断、动作周期或动力学；未确认外观、容差、阈值或训练预算。本次迁移自检及静态检查不代替专项/总项的独立工程审核。
