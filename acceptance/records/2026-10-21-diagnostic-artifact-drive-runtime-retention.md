# 驱动与运行时诊断批量保留核定

## 适用范围

用户选择继续核定驱动/运行时报告及旧诊断包，沿用不删除范围。对应 [诊断整理事项](../../work/active/diagnostic-artifact-lifecycle.md)。本轮只修改既有路由索引，实读原证据与现有消费者；没有新建整理框架、修改机器人/驱动源码、起仿真、迁移或删除产物。

## 验收条件

- 分类来自实际 report/failure/plan 及消费路线，不据名称、完成字段、较新/verified 字样宣布物理通过。
- 原失败、旧判词、源码快照和配套日志有具体保留理由；日志摘要只用于身份，不单独证明完成或退出码。
- 跨目录绑定实际计算，区分材料摘要匹配、工作源码漂移和当前可重跑性；不修改旧索引或哈希抹掉差异。
- 代表性真实读者可读取保留材料；读者拒绝或 invalid 按实际保留，不以 exit 0 替代判定。
- 新输出保持未知或原事项在办状态，不为了降低 pending 数自动升级类别、关闭或删除。

## 结果

### 本批分类规模与具体用途

旧索引 170 条中，64 个 pending 得到保留判定：31 个包（22 历史对照、9 当前依赖）和 33 个配套/绑定日志（历史对照）。同时发现并登记 14 个后来新增条目，其中胸部 280 报告包及日志 2 条按已有记录核为历史保留，另外 12 条待原执行者交接。当前 184 条：80 pending、82 历史对照、20 当前依赖、2 容器。

pending 的可比口径是旧存量 132→68，加上本批登记的 12 个新 pending 后为 80；不是“132 条全部处理完”。索引是观察时的路由，不保证执行后新产生文件已被收录。

| 组（完整前缀为 `rl_exp/out/`，B 行名称省略 `lizard2_b_`） | 路由判定/保留用途 |
|---|---|
| standing_run01、standing_run02 | 历史 startup 布尔序列化拒绝、物理失败/退出码对照；失败保留，未补写为成功 |
| standing_exitfix、standing_legs6、standing_neck2、combined_tracking | 当前依赖：真实 standing CLI 的 load_reference / neck_load_reference / tracking_report、以及 gain/lift loader 输入；失败中间样本仍可作为实际输入，不因失败移除 |
| loaded_pd_regression | 历史改增益后有限固定基回归，不是承重行走能力 |
| chest2_standing、chest2_wrist1_lift | 历史旧胸部水平判词、力矩接口审计原件及实际失败抬腿；不把已撤销阈值当当前失败标准 |
| level_leg_original、level_leg_wrist6 | 成对原增益失败/有限修改比较；保留两个包及共同 fixture，不批准一般载荷能力 |
| lf_lift_wrist6、lf_lift_legs12 | 失败抬腿及判词/序列化对照、计划与源码；有完整 report 不等于通过 |
| lift_plan（首跑）、lift_plan_wrist6 | 首跑历史预算被当前 loader 实际拒绝；wrist6 计划实际读通且被 chest/lift CLI 消费，分别保留历史和当前依赖 |
| transfer_plan、transfer_tail_plan、transfer_tail_lift | 历史几何反例、序列化尾部计划、失败实际移重及规划器回归；不拆其绑定材料 |
| transfer_lift | 当前依赖：尾部 planner 实际 load_reference 消费的失败报告，不改旧判词 |
| tracking_run02 | 历史旧输入 20 逐轴小幅跟踪及与新身份对照，非当前全部受载批准 |
| rf_wrist_original、rf_wrist6 | 原报告实际分别 joint_self_weight_tracking_failed / verified；保留失败/有限比较，纠正前次只读探索误称 original 成功的判断 |
| rf_wrist_settle_video、all_joints_video_observe | settle_observation_completed 只指观察完成，不指跟踪通过；free_base_ground 是另一个工况，不混成固定基或30主动 case批准 |
| all_joints_video、all_joints_video_full | 实际 failure.json 分别 unexpected speed/contact；无完整报告、部分视频，历史失败材料保留，不按 full 名称宣布覆盖 |
| `lizard2_e_20261013_final` | 当前依赖只限旧命名 P0 的 source/target；shared/split 旧身份不是当前动力学输入 |
| `lizard2_e_spatial_20261015` | 当前 runtime 的 REGISTERED_INPUT 仍从 attempt06 消费 USD/URDF/manifest，保留转换失败及全部尝试，不移动混合子树 |
| `lizard2_e_registered_20261015` | 当前 baseline/reset/过滤读写链的材料与反例；原 baseline 为短窗 smoke，不是性能通过 |
| `rl_exp/tools/diagnose/out/gait_probe`、`joint_plots` | 混合历史 gait/退出码/关节限位证据保留；只复验两份具名 gait 输入，未核定每个子文件 |

26 个 B 包、3 个 E 包先核定；再核历史 gait/plot 两包，合计 31 包。目录名以索引逐项全路径为准，以上组表只说明类别与用途，不取代精确路由。配套日志共 33 条：22 个上述 B 同名日志、2 个撤销阈值破坏日志、4 个 fresh 同名日志、3 个旧 v10 producer 日志，以及 2 个记录逐字绑定的 fresh baseline/obs 日志。没有只因日志包含环境初始化就标完成；digest 字段没有自证 `match=true`。

新增 14 条包括 chest280 包及日志、loaded_suite 原/续跑目录和日志、自检日志及独立索引/候选源码/diff。loaded_suite 和 resume 仍在原事项在办，failure/progress 和尚无最终 report 的现场保留，未代做继续采集、续跑或预算决定。胸部 280 两项按 `2026-10-19-lizard2-spatial-small-tracking.md:148,175-193` 的原报告摘要核定，未重跑胸部物理，也未把直接复核称独立批准。

### 实际摘要、旧源码与漂移

实算 6 个原 evidence_index（standing、chest、level、lift、transfer旧与final）的 105 条文件引用：100 匹配，5 不匹配均是后来已变化的工作源码路径；原 report/source.py/manifest/对照 JSON 等材料未因本轮改变。胸部、level、transfer index 对当前 standing/tracking/transfer.py 的引用分别漂移，原 source.py/相应 planner_source 快照摘要仍可按实际报告解释。

这不是“旧索引全部通过”，更不是“当前源码可直接重现旧判词”。旧 evidence_index 未改；本轮审计把 expected/actual/路径及是否工作源码另存新 JSON。其它未在这六份索引中的包只核其 report `code_sha256` 与 source.py 字节，未外推全部资产/环境绑定。

四份 lift/transfer 计划的 standing_report 与 pose_report 实算摘要均匹配。实际 `_load_standing` 读取 standing_neck2 的报告、绑定 manifest 与 URDF 成功；实际 `_load_lift_plan` 读取 wrist6 计划成功。首跑旧计划因 lift_settings 与当前设置不同被断言拒绝，记录已明确历史两次预算不直接喂当前 loader。保持拒绝，不修改历史预算或放宽断言来降低 pending。

### 真正的磁盘读取与图表复读

1. 真实 `plot_joints.py` CLI 对原 `gait_v2_shank.json`、`gait_v2_spine.json` 各生成三档图，共12张 PNG及两份索引，全部在 tempfile 内。新索引每档逐关节读数与原 joint_plots 索引完全相等。图像内容/PNG bytes 未比较，不宣称原图可删、再生成的视觉内容正确，原图与索引保留原位。真实输入 SHA256 为 `d7bd52bb093068266e146e9e664bb1e81d621feda0bb598947da8077778003aa` / `ad5639200db284eedb30361a55df11d4ab129170a884b7080bb5adb714719977`。
2. 真实 `baseline_metrics` CLI 分别读取旧 connections_verified 的 `baseline_smoke_20261016.frames.pt`、fresh reset 的 `baseline_smoke_20261020.frames.pt`，均返回0但原 reader 判词是 **invalid**：唯一原因是10步×0.02 s短窗不满足20 s冻结协议，八 gates 全为 null。与原报告 `reader_validation` 的 verdict/invalid_reasons/gates/metrics/diagnostics/per_env 逐项相等；writer 外层 smoke_only 与 raw reader invalid 不混淆，不宣布评测性能通过。
3. 当前 reader 所用输入原摘要均与已有记录相符；新物理采集没有启动。上述 loader 身份断言仍限普通 Python 模式，本轮不声明它们优化模式安全，也不解除活跃链迁移前置。

### 审核与验证

独立有界只读上下文核 RF 失败/观察边界与索引，建议进一步明确 PNG存在不等于图像正确、源码字节相同不等于能重跑；已补索引限制，并在本记录分开说明。关于“无汇总字段无法核计数”的判断不成立：计数可从 packages[] 按类别复算，结果唯一归本记录，不增第二份索引统计账本。该审核未读完全部B/E原件，不冒称全量独立验收；只是阶段性交接。

完整仓库闸门 `ALL_OFFLINE_CHECKS_PASSED (37/37 in 52.8s, jobs=4)`。本轮没有修行为代码、没有新增默认闸门或测试；真实复读及失败拒绝就是本轮保留能力证据，闸门绿不等于清单闭合或归档可迁移。

## 证据引用

- 路由：`rl_exp/tools/diagnose/artifact_index.json`，SHA256 `f9f65106dcc1b5b234aa8bc99df4e01151de553c4df58b3460fdef7297005bfd`。
- 责任记录：`2026-10-19-lizard2-loaded-standing.md`、`2026-10-19-lizard2-chest-standing-pd.md`、`2026-10-19-lizard2-level-leg-pd.md`、`2026-10-19-lizard2-single-leg-lift.md`、`2026-10-19-lizard2-load-transfer-lift.md`、`2026-10-19-lizard2-spatial-small-tracking.md`、`2026-10-15-lizard2-e-spatial-runtime-wiring.md`、`2026-10-13-lizard2-body-drive-plan-review.md`，均位于 `acceptance/records/`；引用既有结论不复制或改写其原判词。
- 本机审计/复读日志位于 `rl_exp/out/runs/diagnostic-artifact-lifecycle/20261020-preflight/`：
  - `drive-runtime-binding-review-20261021.json`，SHA256 `949c0c2a7c34bbb9c73fe397aa88b9c15d4797334d27451119bdbe9259476a70`。
  - `drive-runtime-plot-review-20261021.log`，SHA256 `ae99fc8a1c13c9844e79133a1009037c15f76d1ffaaadc7343eb09ea67d26605`。
  - `drive-runtime-baseline-read-20261021.log`，SHA256 `86de4930da73d36e637ad4b7bd79439f9c8bdf897ef168758adfb692d098419a`。

仓根复读，绘图输出必须选择全新目录，不覆盖原材料：

```text
<配置解释器> -B rl_exp/tools/diagnose/plot_joints.py --report rl_exp/tools/diagnose/out/gait_probe/gait_v2_shank.json --out_dir <新临时目录> --at_stop_rad 0.02
<配置解释器> -B rl_exp/tools/diagnose/plot_joints.py --report rl_exp/tools/diagnose/out/gait_probe/gait_v2_spine.json --out_dir <另一新临时目录> --at_stop_rad 0.02
<配置解释器> -B -m ablation_harness.baseline_metrics rl_exp/out/lizard2_e_registered_20261015/connections_verified_20261016/baseline_smoke_20261016.frames.pt --protocol ablation_harness/protocols/lizard2_flat_v5.json --naming palm_spatial
<配置解释器> -B -m ablation_harness.baseline_metrics rl_exp/out/lizard2_e_fresh_reset_20261020/baseline_smoke_20261020.frames.pt --protocol ablation_harness/protocols/lizard2_flat_v5.json --naming palm_spatial
python -B -c "import json,collections; from pathlib import Path; d=json.loads(Path('rl_exp/tools/diagnose/artifact_index.json').read_text(encoding='utf-8')); print(len(d['packages']),collections.Counter(e['classification'] for e in d['packages']))"
```

最后一条只复算当前索引类别，不证明后来所有新输出已登记、分类或暂停写入。原索引六份文件可按键路径使用 `runrecord.binding.sha256_file` 对照；旧 `.py` 工作路径漂移须与 source 快照分开解释，不修改原索引。

## 未覆盖边界

- 本轮新增归档为0、删除为0；累计仍是此前四包历史归档。被核定包的传递路径、混合子树和运行消费者未接通迁移前，不冒险移动为“归档进度”。
- 80 pending、其它输出根、容器子文件与执行后新增产物仍需处理；writer_status 保持 unknown，不据 frozen report 推没有活跃实验。
- 本机单副本及外部备份问题未解决；保留分类不是可靠备份，不清唯一或昂贵证据。
- 原预算旧计划、raw baseline invalid、RF原增益失败和作废胸部门槛均照原材料保留，不用新源码/状态摘要冒充原成功证据。
- 新运行布局登记、生产入口切换和日常收尾机制仍未落实，整个事项保持 in_progress，未进入全事项关闭审核。
