# Harness 版本锚点退回补证：逐笔覆盖与时态（2026-10-28）

## 适用范围

- 执行侧响应 `acceptance/records/2026-10-28-harness-version-anchor-independent-review.md` 的退回；不是独立审核结论。逐笔范围严格为 `git log --name-only 0c3ec25..925d997 -- ablation_harness`。
- 用户明确选择分别验收：历史 v1.10.0 快照和 v1.9.0/v1.10.0 旧远端锚点；现行 v1.11.0 基线和其远端锚点。不回滚、不重打 tag、不改写冻结记录。事项仍待不带执笔历史的新上下文复审。
- 只解释该范围测量语义或排除理由；“非测量语义”不意味着没有其他行为变化。本记录不作新编号裁决。

## 验收条件

1. 直接复核三个远端标签、对应提交身份及祖先关系；区分历史快照、现行基线和远端锚定树。
2. 对完整提交清单逐笔从各提交补丁和关联证据核对语义变化或不计测量语义的具体理由；代码概述不能冒充已有逐笔表证据。
3. 同一输入复跑 `601f1d6` 父子 reader 的耦合读数；按用户选择设置独立复审路由，未复审不关闭。

## 结果

### 锚点与时态

| 远端标签 | `ls-remote` 指向的完整提交 | `git show -s` 主题 |
|---|---|---|
| `harness-v1.9.0` | `0c3ec25ac92c0aaaf8bd8755ea26e43f0022eefb` | `harness-v1.9.0: declare the version, log the anchor it needs` |
| `harness-v1.10.0` | `925d99781a177d36b62db215f0ed949811f4f17a` | `harness-v1.10.0: declare the baseline, and anchor it together with v1.9.0` |
| `harness-v1.11.0` | `07e5d2f3cf4e5de302b4c28b57f6c9e27cc6e23d` | `harness-v1.11.0: add COM-based contact reader` |

两次 `merge-base --is-ancestor`（v1.9→v1.10、v1.10→v1.11）均退出 0。`925d997`、`5aaeb4b`、`7cbabee^`、`7cbabee` 的 `ablation_harness/HARNESS.md` 快照均声明 v1.10.0；`07e5d2f` 快照及当前工作树的 `ablation_harness/HARNESS.md:34` 声明 v1.11.0。远端 v1.11.0 指向声明提交，但当前工作树不是该标签整棵树：`git diff --stat 07e5d2f HEAD -- ablation_harness` 有后续变化，文档基线段仍相同，视频段不同。

`925d997..07e5d2f` 不只有 COM reader：`git log` 同时显示文档、运行、诊断消费者和其他变更，例如 `0f4b2bf` 补历史覆盖声明、`bcc5dda` 管运行版本、`2a9fd90` 绑定报告 reader。这里仅验证历史指定区间的覆盖及现行基线/锚点身份，**不声称 v1.10→v1.11 全部变更或测量语义已逐笔覆盖**；祖先关系也不证明完整语义覆盖。

### 逐笔核对：25 笔

范围由上述 `git log --name-only` 输出确定。每行的 `git show <提交> -- ablation_harness` 是直接可复查的补丁证据；表内文件为该补丁的具体落点。关联旧记录只支持各自声明的范围，不把基线概述充作旧表逐笔证据。

| 提交 | 归属与理由 | 直接落点 / 补充证据 |
|---|---|---|
| `925d997` | 非测量实现：声明 v1.10.0、移除锚点敞口并列覆盖引用；不是新 reader。 | `HARNESS.md` 补丁；锚点见上表。 |
| `ed40aaf` | 非测量实现：只调整 live-check 与资产 fail 授权事项指针。 | `HARNESS.md` 补丁。 |
| `2dda131` | 非测量实现：将 headless 挂账改为关闭指针。 | `HARNESS.md` 补丁；`acceptance/records/2026-10-10-ablation-harness-headless-flag-replacement.md`。 |
| `4ef9fb4` | 非测量公式：train/eval 启动旗标由 `--headless` 换为强制 `--viz none`；启动行为有变化，不据此证明任意配置物理等价。 | `run_ablation.py` 补丁；同上 headless 记录的 launcher 对照。 |
| `f1e6421` | 非测量公式：默认 task 从退休 lizard 改为 lizard2，另改示例与录像默认；不传 task 时被评对象改变，不能称所有运行等价。 | `baseline_eval.py`、`eval.py`、`specs/example_baseline.yaml`、`video_matrix.py` 补丁；`work/closed/2026/retired-family-code-prune.md`。 |
| `4d7aa26` | 非新判据：新增 `lizard2_flat_v5` 协议身份及锚表，复制 v4 的 judge、criteria、report_only；协议身份改变，文件不必字节相同。 | `protocols/lizard2_flat_v5.json`、`protocol_anchors.json`；下方字段对照。 |
| `f0d0401` | 非实现：只新增 v4 joints30 一份评测结果 JSON，不能由结果文件推断公式变更。 | `results/lizard2_flat_v4/v2/Lizard2-Flat-v2_9999_deterministic_seed123_joints30/eval.json`，`git show --name-status`。 |
| `601f1d6` | 测量语义：采集与 reader 的腿关节 token 均从三扩五，耦合最大相关的候选配对改变；不只是扩采集列。 | `baseline_eval.py` 的 `_gait_shape_joints`、`baseline_metrics.py` 的 `_LEG_TOKENS`；`acceptance/records/2026-10-10-harness-baseline-coverage-fill.md` ①②，本次对照见下。 |
| `97f50cb` | 非实现：只新增 v4 一份评测结果 JSON。 | `results/lizard2_flat_v4/v2/Lizard2-Flat-v2_9999_deterministic_seed123/eval.json`，`git show --name-status`。 |
| `3bce24c` | 测量语义：格式 3 加 joint_pos，采集及 reader 新增四条形态报告、依赖列拒绝，并新增 v4 协议。 | `baseline_frames.py`、`baseline_eval.py`、`baseline_metrics.py`、`frame_semantics.json`、`protocols/lizard2_flat_v4.json`；`acceptance/records/2026-09-29-gait-shape-in-the-eval-flow.md`。 |
| `525cc42` | 非实现：只新增 v3 一份评测结果 JSON。 | `results/lizard2_flat_v3/v2/Lizard2-Flat-v2_9999_deterministic_seed123/eval.json`，`git show --name-status`。 |
| `7168a86` | 非新判据：新增 `lizard2_flat_v3` 协议身份及锚表，复制 v2 的 judge、criteria、report_only；身份改变。 | `protocols/lizard2_flat_v3.json`、`protocol_anchors.json`；下方字段对照。 |
| `862e39f` | 非测量公式：绘图工具读取两种已有记录形态并生成 gate 图和表，不重跑 reader；展示方式变化不等于对判词的运行时验证。 | `plot_eval.py` 的 `_new_run`、`_gates`、`_record_rows` 补丁；旧补证③。 |
| `88f6bd9` | 测量语义：足端及非足 mesh 几何来源按任务家族解析，脚读数及 `foot_geometry` 摘要读取同一树。 | `baseline_eval.py` 的 `collision_mesh_dir(obs_protocol.family_of(args.task))` 补丁；旧补证①。 |
| `9fccecf` | 汇总行为变化，非测量公式：非 smoke 表中非 checkpoint `policy.kind` 拒绝，缺 kind 标 uncertified 不拒；smoke 豁免，图表不经该闸。历史基线明确列此能力，但不把它误当测量公式变化。 | `run_ablation.py` 的 `_identity_report`/`_summarize` 和 `HARNESS.md` 补丁；`acceptance/records/2026-09-23-diagnostic-row-identity-gate.md` 有真树与反例，不是旧补证①②③逐笔表。 |
| `c7ed3cd` | 测量语义：协议 scenes 给每 env 固定命令、冻结环境重采样；帧 meta 记录分配，reader 检查命令一致和有效帧并报告场景覆盖。 | `components/command_player.py` 的 `scene_assignment`/`scene_commands`、`baseline_eval.py`、`baseline_metrics.py` 的 `_scene_reasons` 补丁；`acceptance/records/2026-09-23-baseline-fixed-scenes.md` 有两次真跑及广播反例，不是旧补证①②③逐笔表。 |
| `b3243ff` | 测量语义：格式 2 加四列足端原始量及地面/几何 meta，新 footed judge 增 `foot_lift_v1`、`foot_slip_v1` 和报告依赖；先存帧再判、失败可离线重判。旧 slip reader 后来发现 COM/候选点参数顺序错误，不可把新增等同于物理正确。 | `baseline_frames.py` 的 `FOOT_COLUMNS`、`baseline_metrics.py` 的 `FOOTED_JUDGE_ID` / `CRITERION_KINDS`、`baseline_eval.py` 补丁；`acceptance/records/2026-09-23-baseline-frames-format-2-foot-reading.md` 仅证采集和来源，**明确不证明足端判据**；判据增量直接以本提交补丁及 `judge_semantics.json` 为证，后续缺陷见 `acceptance/records/2026-10-23-lizard2-contact-com-calibration.md`。 |
| `f5a2007` | 非实现：只新增 baseline v3 重跑结果 JSON。 | `results/baseline_flat_v3/v2-trained-9999-rerun/eval.json`，`git show --name-status`。 |
| `d086fc4` | 非测量公式：协议锚点表说明覆盖范围由目录导出而非手工声明，并补齐缺失条目，属于一致性检查数据。 | `protocol_anchors.json` 补丁；旧补证③。 |
| `21ec102` | 非测量公式：新增已有协议文件身份与摘要锚表，保护声明字节，不计算 rollout/判分。 | `protocol_anchors.json` 补丁；旧补证③。 |
| `775ed15` | 非实现：只新增 lizard2 v1/v2 三份评测结果 JSON，其中一份标 superseded。 | `results/lizard2_flat_v1/`、`results/lizard2_flat_v2/`，`git show --name-status`。 |
| `6de88a0` | 测量语义：settled reader 排除切换窗口、零命令漂移逐 env 最差，修 start_pos 设备混用；新增 v2 协议与 judge 用例。 | `baseline_metrics.py`、`judge_semantics.json`、`protocols/lizard2_flat_v2.json`；旧补证①。 |
| `1fba2b8` | 测量语义：分带 tracking/displacement、非足载荷求和、完整 swing；声明但未执行的 gate 判 invalid；冻结 banded 身份和 v1 协议。 | `baseline_metrics.py`、`judge_semantics.json`、`protocols/lizard2_flat_v1.json`；旧补证①。 |
| `e015cc4` | 非实现：仅补入 baseline 与 locomotion 的既有结果、记录、地形 JSON 和 summary CSV；数据本身不证明新算法。 | `results/baseline_flat_v3/`、`results/locomotion_eval_v4/`，`git show --name-status`。 |
| `d60bd3f` | 测量契约：增加 banded judge 身份、kind/参数/列及 gate 声明，绑定身份可读取种类；实现与冻结在后续提交，不能把声明当成已验证行为。 | `baseline_metrics.py` 的 `BANDED_JUDGE_ID`、`CRITERION_KINDS`、`JUDGE_KINDS`、`GATE_ORDER` 补丁；旧补证①。 |

协议字段对照：当前 `lizard2_flat_v1` judge 为 banded，v2–v5 为 settled；v2–v5 的 `criteria` 相等，v2/v3 与 v4/v5 的 `judge`、`criteria`、`report_only` 各自相等。v4 相比 v2 的 report-only 增加 `spine_leg_coupling`、`spine_yaw_travel_deg`、`stride_hip_corr`、`stride_knee_corr`。这是解析后声明字段对照，不是实际 rollout 或混表许可。

### 耦合行为复读

按旧补证②的 64 帧、1 env 同一输入，以项目解释器从 Git 取两个版本函数、AST 提取后执行：`601f1d6^` = `5.995425592306487e-18`，`601f1d6` = `1.0`。与旧记录一致，不起仿真。Windows `cmd` 会吞掉命令文本中的单个 `^`；首次内联调用因此误将两次都执行成 `601f1d6`、输出均为 `1.0`，该次无效；修正为通过 `chr(94)` 构造父提交后得到上列结果。

## 证据引用

从仓根复读；每个表行都可用该行 hash 带路径过滤取补丁：

```bat
git status --short --branch
git ls-remote --tags origin "harness-v1.9.0" "harness-v1.10.0" "harness-v1.11.0"
git show -s --format="%H %s" 0c3ec25 925d997 07e5d2f
git merge-base --is-ancestor 0c3ec25 925d997
git merge-base --is-ancestor 925d997 07e5d2f
git log --name-only --format="=== %h %H %s" 0c3ec25..925d997 -- ablation_harness
git show <提交> -- ablation_harness
git show --name-status <提交> -- ablation_harness
git show 925d997:ablation_harness/HARNESS.md
git show 5aaeb4b:ablation_harness/HARNESS.md
git show 7cbabee^^:ablation_harness/HARNESS.md
git show 7cbabee:ablation_harness/HARNESS.md
git show 07e5d2f:ablation_harness/HARNESS.md
git log --format="%h %s" 925d997..07e5d2f -- ablation_harness
git diff --stat 07e5d2f HEAD -- ablation_harness
git diff 07e5d2f HEAD -- ablation_harness/HARNESS.md
```

`^^` 是在 Windows `cmd` 输入的转义形式；在直接传参数的其他 shell 中使用 `7cbabee^`。耦合复读代码与解释器入口完整保留在 `acceptance/records/2026-10-10-harness-baseline-coverage-fill.md` 的“耦合报告对照”节；在 `cmd` 内联时同样需正确转义 `^` 或使用 `chr(94)` 构造。协议字段对照入口为 `ablation_harness/protocols/lizard2_flat_v1.json` 至 `lizard2_flat_v5.json`，逐字段解析比较上述三个键。

开始检查工作树为 `main...origin/main`，已有 `work/active/harness-version-anchor-missing.md` 修改及 `acceptance/records/2026-10-28-harness-version-anchor-independent-review.md` 未跟踪；它们是本任务输入，未覆盖审核记录。后续 `git status` 出现其他事项与诊断文件的并行改动，本任务未操作这些文件。远端访问成功，未绕过权限。

## 未覆盖边界

- 本记录是执行侧补证而非独立审核；新上下文须逐笔对照补丁、关项正文、现行落点及证据，复读耦合并决定通过或退回。证据改变须重审。
- 旧区间以外尤其 `925d997..07e5d2f` 不作语义完整性判断；当前工作树不等于 tag 树。tag 指向提交，不证明其后工作树的全部变化已重新锚定。
- 未起仿真、未跑 GPU rollout；耦合对照不证明策略性能、物理表现或判据质量。旧帧格式记录不证明 `b3243ff` 新足端判据的正确性；后续 COM 新 reader 的校准仍以其独立记录的边界为准。
- 不重评录像矩阵实现，不更改任何旧验收记录、冻结协议或远端标签；本轮不提交、不自行审核归档。
