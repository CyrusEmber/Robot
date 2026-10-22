# E：旧 shared 边界、旧对象回交与消费者出口

## 适用范围

对应 `work/active/lizard2-candidate-wiring.md` 剩余的旧 shared 工具边界、旧对象回交和 E3 出口清点。本轮修改 `pose_slider.py`、`fit_gait_target.py`、`check_leg_reachability.joint_effect` 的可选父系参数及既有回归；未修改共用导出器、正式资产、冻结配方、接触判据或协议。E 保持 in_progress，接触归属事项保持 open；本记录是执行者自检，不是 D 的关闭审核。

当前 spatial 接线输入仍为 `rl_exp/out/lizard2_e_fresh_reset_20261020/measured_manifest.json`，URDF 身份取[接触与支撑入口记录](2026-10-22-lizard2-e-support-contact.md)。旧 shared 则由 `versions/lizard2/assets.json` 指向 `rl_exp/lizard2_candidate/`，URDF SHA256 为 `da05432efd5d3c3dd9302682286825869b289d5f912cb5703bd0d32642e0c52b`，USD 为 `fceaf55be1f045572121c464cb32e1eb0ae7d5d0ba63dfbe9a0d943f84df3b6c`；本轮实读与[历史双目标记录](2026-10-13-lizard2-body-drive-plan-review.md)一致。两者不能凭同为五轴或相同腕/踝词根互换结果。

## 验收条件

1. 旧工具明确使用 shared 角色，拒绝把当前 palm_spatial 当作已支持输入；不能先派生写入再拒绝。
2. 保存姿态经实际入口载入时核对声明的机体；新格式同时核 URDF 摘要和逐腿真实关节顺序。保留历史读取边界，不能伪称旧无绑定文件已验真。
3. 发现缺陷须有修复前失败、修复后通过；旧工具实际自检复验，既存红项不因命名边界核对而消失。
4. 旧 cap/ownership 绑定原对象和接收事项；出口表区分已测切片、性能边界和未交付项，不将新候选正例作为旧对象解除依据。

## 结果

### 四项实际缺陷与修复

| 缺陷 | 修复前实证 | 修复及实际复验 |
|---|---|---|
| 保存姿态只核角度数量 | `pose_slider --load foreign_spatial_pose.json --backend Agg` 默认画旧 shared，却接受声明新 spatial URDF 的五轴姿态，退出 0 | 实际 build 传入目标 URDF，错声明退出 1；生产 formatter 新增 pose_binding（URDF SHA256、逐腿关节名），同目标真实 CLI 仍退出 0 |
| 不支持输入先写派生文件 | `fit_gait_target` 对 spatial 输入 `--scale hip_twist=1.001 --asset-only` 先写 scaled URDF，再因旧 `rl_foot` 缺失退出 1 | main 在 scale 及任何派生目录创建前校验 A/B 的 shared 链；相同请求退出 1，`scale_after` 目录不存在 |
| 旧求解默认自检的可达点漏解 | 原始字节快照及边界修复后的默认自检均为 2.836458 mm，超过既有 2 mm；目标角度实际在限位内，源自同一 FK | 内存对照只将末级 8 mrad 后再细化到 2 mrad，误差为 0.648195 mm；真实 solver 补该档后七项控制全部通过，未抬 2 mm 判据 |
| 摆姿器把腿父系当机身系 | 实际旧 shared 的两前腿父级为 chest_pitch，父级相对 base_link 平移 −5 mm；原 UI setup 与独立整树 FK 前腿各差 5 mm，后腿零差 | UI 的零位、实体绘制、文字读数及导数均组合 chain_parent_transform；终版实际 setup 与整树 FK 四腿零差 |

姿态读取函数保留原参数及三元返回值，仅增加可选 keyword-only `urdf`；实际 CLI 显式传目标。原无 pose_binding 的文件继续沿用 legacy 读取，有 URDF 声明时仍核路径；连 URDF 声明也没有的历史文件保留未验证语义，不能升级为新候选绑定证据。新格式的错摘要、关节顺序互换、不完整绑定、NaN 角度和无限高度均拒绝；同路径 URDF 内容变化也拒绝。当前路径检查是本机明确目标的严格检查，未提供跨工作区路径迁移能力，也未将 URDF 摘要升级成 mesh 摘要。

`fit_gait_target` 继续使用 shared hip/haa/hfe/kfe/foot 角色及其显式插入轴 fixture，不扩成 palm/spatial 求解器；`pose_slider --urdf <fresh spatial>` 仍拒绝。新增细化会增加旧求解的计算量，且可能改善原数值输出；本轮不是承诺所有目标全局可达/不可达，也不改历史报告。七项控制包含不可达点、限位、B 不差于 A 的 seed、A 嵌入 B 等值，以及无法满足的骨段方向判据，全部按原控制要求通过。

四项回归先红后绿：姿态旧 CLI 的静默接受有真实现场；派生前拒错回归在旧 main 实际触发 writer；可达点回归在旧 solver 实际报 0.002836458 m；实际 UI setup 的整树对照在 lf 数值断言失败，终版通过。`pose_slider --self-check --backend Agg` 的 FK、保存读回及视图保持检查通过；生产 formatter 保存的 shared_bound_pose 经真实 CLI 载入也通过。Agg 的 non-interactive warning 仅说明未显示窗口，不作异常通过依据。

父系修复复用已有 `pad_state(parent_transform=...)`，给 `joint_effect` 增加可选 keyword-only 同名参数；默认仍是局部父系。与提交 `434ccd5` 原函数 AST 对照，四腿各五轴、零/非零姿态共 40 例原默认结果逐值完全一致；非零旋转/平移父系另经解析 dp、dn、axis、倾角导数核对。独立整树 FK 的对照先核实际 URDF 的全部 origin rpy 为零，未把忽略 rpy 的实现泛化到任意资产。首次两次对照误用了模型/API，后按真实接口修正再得到数值红例；向上法线倾角符号的测试编写错误也保留日志，不归为产品故障。

摆姿器的上游关节保持零位。旧 fitter 保留其目标相对量的腿父系定义，并在 CLI 明示实际父级；默认后腿是 base_link，前腿覆盖不再被文字默认为整机 base_link，未擅自改写旧 target 的坐标约定。

### 旧对象回交

`gait_probe --self-check` 本轮仍退出 1，lizard2 的 rl cap 实读 `0.1192821488 m²`，原预期 `0.013352 m²`。按实际家族声明重算四脚 mesh-local 水平贴地 2 mm 带 cap：lf/rf 约 `0.01335187 m²`，rl/rr 约 `0.11928215 / 0.11928233 m²`。旧 lizard 的 rl 约 `0.11928244 m²`。这些是该自检定义的网格几何读数，不是运行时接触面积、滑移或承重结论；不能仅据差异判断必须改网格还是必须改断言。

原 `rl_exp/out/lizard2_e_20261013_final/shared.json` / `split.json` 及各 USD/URDF 摘要仍匹配历史记录。保存的 `shared_contact.json` / `split_contact.json` 给出当时实际 resolved 处罚对象；本轮以原 URDF 静态交叉核对：shared 的 lf/rf/rl/rr_kfe 均无 collider，split 对应 lf/rf_wrist、rl/rr_ankle 均无 collider，与原报告 no_collider 集合交集一致。**本轮没有重跑这两个旧对象的 PhysX ownership**，历史实际失败继续由原记录负责；manifest 未显式覆盖处罚配置不表示实际选择为空。

回交 `work/active/floor-contact-attribution.md` 的判据为：明确原对象身份和 cap 期望的资产前提；按原 resolved body/collider 修清空处罚对象，配置/资产变更仍走原负责线；给同一对象的实际入口、正反例、绑定与复读命令再回交 E。当前 spatial 的腕/踝是具 collider 的真实末端，不能拿其非零地面正例解除旧 split 同词根中间段的失败。

### E3 消费者出口表

表内“已有”只对其记录绑定的输入和范围成立；源、树、轴、零位、网格、惯量或配置变化后重验受影响链。

| 消费者/链 | 可用输入与正反例证据 | 出口边界及后续 |
|---|---|---|
| Blender → URDF → USD | [A 正式导出](2026-10-19-lizard2-a-delivery-plan.md)、[fresh 身份/转换/reset](2026-10-15-lizard2-e-spatial-runtime-wiring.md) | A 维护共用源；本轮未重跑导出，不代表候选正式采用 |
| 目标 loader / runtime selector | 上述 fresh 记录及[实际支撑错命名拒绝](2026-10-22-lizard2-e-support-contact.md) | 四端/全关节/动作来源绑定，不能用名表或同数量替代 |
| URDF FK / 碰撞构姿 | [非零构姿与独立数据](2026-10-22-lizard2-e-nonzero-gait-collision.md)、[父系/轴修复](2026-10-22-lizard2-e-fk-parent-frame.md) | 独立矩阵及角色反例已有；不判全部壳碰撞安全 |
| check_joint_layout | [独立入口](2026-10-22-lizard2-e-independent-entries.md)：零 env.step 纯 FK、真实动作覆盖与缺 twist 拒绝 | 不是原动态/承重组合的通过证明；逐轴驱动与载荷边界仍交 B/C |
| stance_step_probe | 同记录：真实 action 目标、缩放偏置和限步入口 | 零增益切片不证明跟踪/静站 |
| gait_probe / diag_metrics | [非零 gait](2026-10-22-lizard2-e-nonzero-gait-collision.md)：真实 writer、非零列、独立 backend 值及错误数据拒绝 | 首次终止掩码保留；注入数据不判有效步态 |
| obs_protocol_live / baseline_probe | [fresh 在线分支](2026-10-15-lizard2-e-spatial-runtime-wiring.md)、[非零观测](2026-10-22-lizard2-velocity-observation.md)、独立入口记录 | 有限采样/具名足端分支已有；102 维及训练一致 false 不升级正式协议 |
| check_contact_ownership | [物理子步与非零过滤力正反例](2026-10-22-lizard2-e-support-contact.md) | 两前腕冲击，后踝零力；不判稳态四足承重 |
| diagnose_support | 同记录：独立两步零动作、真实输出及错命名拒绝 | 无 checkpoint/预热；不判长时策略/支撑性能 |
| baseline_eval writer / terminal | [非零写读](2026-10-22-lizard2-e-live-values-gait.md)、[人工终止切片](2026-10-22-lizard2-e-baseline-terminal.md) | 不外推自然 timeout/跌倒；严格 invalid 不洗为有效性能 |
| plot_joints / baseline_metrics | 非零 gait、baseline、FK 记录的真实 reader/绘图及值/绑定破坏例 | 接口连通，不批准完整性能协议 |
| fit_gait_target / pose_slider | 本轮旧 shared 正例、spatial 拒绝、四项修补及原始失败 | UI 用 base_link，旧 fitter 明示腿父系；未迁新候选，不列作已支持 spatial 的出口 |
| 旧 shared/split 回归与资产前提 | 历史双目标记录、本轮 cap/原 ownership 对象静态核对 | cap 与实际 ownership 回交仍未完成，阻止 E 完整出口；不得豁免或换成新候选结果 |

首轮离线套件 `37/37` 通过，70.9 s。追加父系补丁后的一次验证被并行会话尚未写全章节的验收记录拦下；该记录完整后文档闸门通过，再跑时行为均通过，但 baseline 自动单独复核 25.9 s，超过原 25 s 成本预算。两次失败现场分别保留，不归为父系数值故障，也不跳过成本闸门。

逐测试计时定位到真实 FK 求解回归约 0.99 s；对实际 solve 的固定 geometry/target/phase，新增局部角度评分缓存，不改搜索顺序或代价公式。与提交 `434ccd5` 的原 solve AST 对照，四腿返回角度逐值完全相同，residual 评估次数分别由 2042/2042/1437/2042 降至 1199/1112/461/1324；七项控制日志与缓存前逐字节一致。优化后最终完整套件 `37/37` 通过，63.3 s，原预算不变；不是删除测试、抬预算或无改动重跑到绿。旧 cap 的显式诊断自检仍红，不由离线套件通过解除。

wall time 同时受主机负载影响，不把整套时间差全部归因于缓存；受控证据是相同输入、相同角度输出与实际评分次数下降。最终记录内复读得到 `LEGACY_EXIT_EVIDENCE_REPLAY_OK`。代码提交 `434ccd5`、`a23e25a` 及实际暂存内容的 pre-commit 均通过，日志分别保留在 code_commit*.log / precommit*.log；没有改写已提交历史。

## 证据引用

本机根目录 `rl_exp/out/lizard2_e_legacy_boundary_20261022/`，最终 `artifact_digests_v2.json` 绑定 114 个已完成文件及实际源输入，SHA256 为 `89cb58c3f6a8d108d645e218865970bb88dbf431426142637ffe1c2229e0bab5`。包含 before/final/release 字节快照、实际红绿日志/退出码、派生写入反例、cap/旧 ownership 对象报告和完整离线日志；创建、复读及后续提交日志不纳入索引。首版 artifact_digests.json 属追加父系/成本修复前阶段，保留但不作为最终复读入口。制品为本机留存，不承诺随仓库分发。

最终源码 SHA256：pose_slider `b76cc3d7f4c156eb785937edf408050c45fd5660af62887711e244bebd57cd2e`；fit_gait_target `627f6f07b0d491af2ec7d27a03bb839eef9deb3a34125562d9462a5deef0658c`；check_leg_reachability `4be7e4bdbe2dc7de82fb1f8698c9f707753ba34bbeaaac4d9ed376f3c5120b23`；回归文件 `9aed2e97b2a4539eb9e2f394ab76a5f37f1ba38382f2fdfa9006595700f42c30`。最终字节快照以 *_release.py 保存，先前 *_final.py 是追加父系修复前的阶段快照，均保留。

可重复的实际入口（仓根、IsaacLab Python）：

```powershell
python -B rl_exp/tools/diagnose/pose_slider.py --self-check --backend Agg
python -B rl_exp/tools/verify/fit_gait_target.py --self-check
python -B rl_exp/tools/diagnose/pose_slider.py --load rl_exp/out/lizard2_e_legacy_boundary_20261022/foreign_spatial_pose.json --backend Agg
python -B rl_exp/tools/verify/fit_gait_target.py --urdf rl_exp/out/lizard2_e_fresh_reset_20261020/palm_spatial.urdf --scale hip_twist=1.001 --asset-only
python -B rl_exp/tools/diagnose/gait_probe.py --self-check
```

前两条预期 0，后三条预期 1；不把拒错/旧 cap 失败作为执行器失败忽略。已有错误派生副本保留在现场的 scale_before，下方复读核对 scale_after 未创建。以下 Python 只读核对全部摘要、实际退出码与旧对象几何，不补写结果。

```python
import json
import sys
from pathlib import Path
import torch
from rl_exp.tools.runrecord.binding import sha256_file
sys.path.insert(0, 'rl_exp/tools/diagnose')
import diag_metrics
root = Path('rl_exp/out/lizard2_e_legacy_boundary_20261022')
index = root / 'artifact_digests_v2.json'
assert sha256_file(index) == '89cb58c3f6a8d108d645e218865970bb88dbf431426142637ffe1c2229e0bab5'
for path, digest in json.loads(index.read_text(encoding='utf-8'))['files'].items():
    assert sha256_file(Path(path)) == digest, path
for name, expected in [('slider_before', 0), ('slider_after', 1), ('slider_bound_positive', 0),
                       ('slider_shared_positive', 0), ('slider_spatial_reject', 1),
                       ('fit_scale_before', 1), ('fit_scale_after', 1), ('fitter_default_before', 1),
                       ('fitter_default_final', 0), ('fitter_precision_before', 1),
                       ('regression_final', 0), ('gait_old_cap', 1), ('offline_suite', 0),
                       ('slider_frame_before_v3', 1), ('regression_release_v2', 0), ('slider_release', 0),
                       ('offline_suite_release', 1), ('offline_suite_release_v2', 1),
                       ('fitter_cache_equivalence', 0), ('fitter_cached', 0), ('offline_suite_cached', 0)]:
    assert int((root / (name + '.exit')).read_text().strip()) == expected, name
assert list((root / 'scale_before').rglob('*.urdf'))
assert not (root / 'scale_after').exists()
for row in json.loads((root / 'slider_base_frame_release.json').read_text(encoding='utf-8')):
    assert row['after_max_abs_error_m'] < 1e-10
    assert abs(row['before_max_abs_error_m'] - (.005 if row['leg'] in ('lf', 'rf') else 0.)) < 1e-10
for row in json.loads((root / 'fitter_cache_equivalence.json').read_text(encoding='utf-8')):
    assert row['uncached']['q_rad'] == row['cached']['q_rad']
    assert row['cached']['evaluations'] < row['uncached']['evaluations']
assert (root / 'fitter_release.log').read_bytes() == (root / 'fitter_cached.log').read_bytes()
equivalence = json.loads((root / 'joint_effect_legacy_equivalence.json').read_text(encoding='utf-8'))
assert len(equivalence['cases']) == 40 and all(row['identical'] for row in equivalence['cases'])
a = json.loads((root / 'old_asset_caps.json').read_text(encoding='utf-8'))
for row in a['caps']:
    mesh = Path(row['mesh'])
    assert mesh == diag_metrics.collision_mesh_dir(row['family']) / (row['leg'] + '_foot_collision.obj')
    vertices = diag_metrics.mesh_triangles(mesh)
    grounded = vertices - torch.tensor([0., 0., float(vertices[..., 2].min())])
    cap = float(diag_metrics.ground_contact_area_m2(grounded, .002, 0.)[0].sum())
    assert abs(cap - row['cap_2mm_m2']) < 1e-6
expected = {'shared': {'lf_kfe', 'rf_kfe', 'rl_kfe', 'rr_kfe'},
            'split': {'lf_wrist', 'rf_wrist', 'rl_ankle', 'rr_ankle'}}
for row in a['historical_ownership_inputs']:
    assert set(row['urdf_missing_colliders']) == expected[row['label']]
    report = json.loads(Path(row['historical_runtime_report']).read_text(encoding='utf-8'))
    selected = {name for names in report['terms'].values() for name in names}
    assert selected & set(report['no_collider']) == expected[row['label']]
print('LEGACY_EXIT_EVIDENCE_REPLAY_OK')
```

## 未覆盖边界

本轮未运行旧资产长时支撑、冻结 checkpoint、历史全 ROM 碰撞或新候选动态训练。只读 mesh cap 不证明实际 USD 碰撞形状或运行时力；历史 ownership 的本轮动作是原输入/报告和 URDF 的静态交叉核对，实际解除仍须原对象真跑。legacy 无来源姿态不作身份已验证声明，URDF 摘要不覆盖单独变动的 mesh。

旧 cap、空处罚对象、地面/自碰及接触测量对照由原接触归属事项继续执行，未删除、取消或迁走。A/B/C 源与载荷/驱动、D 的训练前集成审核、S6 的学习策略协调/性能仍按原分工。E 不因本轮出口表或格式通过而进入关闭；接旧对象回交并复验变更链后，才由新上下文随 D 审核。
