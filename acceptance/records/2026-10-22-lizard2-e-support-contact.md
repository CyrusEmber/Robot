# E：非零地面接触与 diagnose_support 独立入口

## 适用范围

对应 `work/active/lizard2-candidate-wiring.md` E 的两个剩余证据切片。沿用 `rl_exp/out/lizard2_e_fresh_reset_20261020/measured_manifest.json` 与原 `palm_spatial` USD/URDF，task 为 `Lizard2-Flat-Play-v3`；不是正式 v3 采用。前轮入口及更早写读、终止、FK、碰撞证据取[独立入口记录](2026-10-22-lizard2-e-independent-entries.md)。本记录是执行者自检，未完成 D 的新上下文审核。

原 manifest SHA256 `d876713b1a4aa6a4fef51f39bed284f4a15a01d562815eefefcf74eebfb77137`，URDF `e8896feb8b0dbdbeaa35e74a01c2ffcb4ab38d89b52f221831b3f287943edd00`，USD `0c5ffd157b39faf9b65907877badbe069ae5af69585124a1097f94956df3fe76`。全部运行保持 fixed base、31 body 禁重力、零 stiffness/damping、force timing=False；不改资产、碰撞过滤或接触阈值。

## 验收条件

1. 实际 ownership 入口观测非零足端接触；原生行名、地面过滤列、逐物理步净力、传感器历史和最终判词相互对照，离地反例仍拒绝。
2. 若发现漏采，须同工况保留修复前失败、修复后通过；回归验证首子步冲击，不以声明一致替代实际采样。
3. `diagnose_support` 实际 CLI 经过目标加载、具名选择、真实采集及 writer，限制预算且不借 checkpoint 或长时策略运行证明接线；错命名拒绝。
4. 保留源码、输入和现场摘要、可执行复读入口、过程失败及未验边界；相关离线检查与仓库提交闸门通过。

## 结果

### 接触漏采的实证与修复

原先 1 mm 入地派生输入的两步观测 `floor03`：八个子步中一次原生净力约 0.628 N，但控制步末为零，既有 1 N 判据拒绝正确。不能因此宣称完全无接触。

预先限定的冲击输入 `impact_input/manifest.json` 仅从前轮根位姿派生再降低 9 mm；根 pitch 保持 0.02 rad，解析最低前足为 −0.010 m，其它 body 最低约 +0.0368 m。其 SHA256 为 `08ff1ae10feddff9a26ae46429cf8aa6d9cac01bad885f2f71fadf3a5c8de65b`，保留具名 config_delta。直接运行 `impact01` 时，初始化物理步骤已把脚推回接近地面，随后八子步均零；没有把这一失败升级成正例。

`palm_contact_wiring.py` 明示在 `gym.make` 后重写绑定的默认 q/dq 为零，并调用 forward 更新 FK，**不增加物理步**；保存初始化后的旧 q、请求值、backend 新 q 和准备器字节快照。重置后的 backend 网格最低值约 −0.010001 m；USD authored transform 只作属性清点，不代替 backend 几何。执行真实 ownership 入口，后续动作全零，两控制步共八物理步。

| 工况 | 实测与判词 | 判定范围 |
|---|---|---|
| `impact_reset01`，修复前源码 | 首子步 lf/rf_wrist 到地面约 810.434 / 810.315 N；原 producer 峰值全零，FAIL、退出 1 | 真实漏采反例，不能按进程失败忽略其原生力 |
| `impact_reset02`，中间失败 | preset 容器无直接 history_length，建场前 AttributeError、退出 1 | 保留失败，未声称该版本通过 |
| `impact_final`，修复后最终源码 | producer 与原生峰值一致，touching 仅 lf/rf_wrist，blind=[]，PASS、退出 0 | 足端—地面非零接触接线正例 |
| `air_final`，原 2 m 离地输入 | 同样准备器与采样，所有八子步净力/地面矩阵为零，FAIL、退出 1 | 真空接触反例，未洗成通过 |

根因是历史只在控制步末触发惰性传感器更新，第一子步冲击未进入可读历史。修复只在 `check_contact_ownership.py` 诊断配置中解析实际 contact preset，设 update_period=physics dt、history_length 至少 decimation，并关闭 scene 惰性采样；物理步长仍 0.005 s、decimation=4，阈值仍 1 N。会使该诊断的其它传感器也按自身周期及时更新，存在额外诊断采样开销；不修改训练配置或物理求解设置。

观察器对每个精确腕/踝 owner 分别建立一行、一个地面 collider 列的只读 filtered view，核对实际 sensor_paths/filter_paths/count/shape；逐子步记录矩阵与原生全 body 净力。最终原生列顺序另与实际传感器名表逐一对照。两前腕地面矩阵与净力一致，其余 body 为零；这不是用净力猜接触 pair。法向 aggregate 不含摩擦、接触点或稳定承重判词。

离线回归执行 producer 的实际采样配置和峰值循环，独立样本首子步 810 N、余下三步零。作用于提交 `00cab6a` 的旧源码时实际失败 `sampled=[3], peak=0`，修复后直接 cfg 与 preset cfg、短/长历史均捕获首步。观察器零/两步及八子步预算、非法动作、行列错配拒绝也通过。

### diagnose_support 实际独立入口

新增显式 `--wiring_steps 1/2`：要求 target_config、phases=0、heights 为空，不允许 checkpoint；启动前拒绝越界/缺前提。仅一次零动作测量，无 25 步预热、不创建策略 runner；报告标明 wiring 与作用范围，不复制同一窗口冒充策略/零动作两个样本。默认 checkpoint 仍必填，默认预热及策略/零动作双窗口保持原行为。

`support_final` 实际进程退出 0，观察器记录两 env.step、八物理步、30 真实动作列、31 传感器 body；四足列为 rl/rr_ankle、lf/rf_wrist。原 2 m 机体离地，实际力全零，报告中的逐 body 排名、脚位及 contact_sampling 消费上述真实名称。新 `p0_measure_check.json` 为唯一产物，run.json 状态 completed，输入、源码及输出摘要经原 `artifact_run --inspect_run` 检查通过。这里没有策略、接触承重或长时诊断合格结论。

`support_wrong_naming` 实际指定 shared，loader 在建场前以 `--naming shared disagrees with target palm_spatial` 拒绝，进程退出 1，无伪造报告。短窗回归在旧 main 上实际因 checkpoint=None 失败；修复后完整支撑输出回归 27 项通过，包含无 runner、单窗口、非法预算/配置及原生命周期路径。

### 检查与身份

完整离线套件 `37/37` 通过，46.0 s，见现场 `offline_suite.log`。实际制品临时副本的隐藏峰值、错地面列、原生顺序反转、缺过滤列、缺子步五种破坏全部拒绝；原制品未修改。记录内只读代码实际复读得到 `SUPPORT_CONTACT_EVIDENCE_REPLAY_OK`；仓库 pre-commit 全部通过，代码提交 `78ad4e6` 的提交钩子也通过，见 `precommit.log` / `code_commit.log`。

最终源码 SHA256：ownership `4befb633ee13809515d5640ceb2bea9ce9bc76ffa9c0fddc0f7d9975e5f8014c`；support `d3c99238a3f23a72f4c0315ba64d70bc906f8c19a5c4be8be2ba574c7b3a8e2e`；观察器 `fb43516bd515730bdb4d571337cdc5ddd23bfed7f7d0d14530c88985c64386de`；准备器/只读复核入口 `2cd1848b570cbf0828168207d6fc0096cbaa1a058c47310fd8742ac25fb100b9`。每次执行按原始字节保存自己的源码，旧失败快照不覆盖。

## 证据引用

现场根目录 `rl_exp/out/lizard2_e_support_contact_20261022/`；`artifact_digests.json` 绑定 99 个已完成文件，SHA256 为 `afe25062ce46c320ba8ea0098b4921e5c48516ea2b3f8fbcd44d29539d3ede83`。包含正反例、过程失败、最终支撑报告/run、原输入及索引复核快照。创建摘要时排除仍会写入的创建/提交/复读日志，旧文件不再覆盖。本机制品不承诺随仓库分发；缺输入应拒绝，不能回退正式资产。

复读（仓根，使用 IsaacLab Python）：

```powershell
python -B rl_exp/tools/diagnose/palm_contact_wiring.py --out rl_exp/out/lizard2_e_support_contact_20261022/impact_final --inspect contact
python -B rl_exp/tools/diagnose/palm_contact_wiring.py --out rl_exp/out/lizard2_e_support_contact_20261022/air_final --inspect air
python -B rl_exp/tools/diagnose/artifact_run.py --inspect_run rl_exp/tools/diagnose/out/runs/support/lizard2-e-wiring-final-20261022 --index rl_exp/out/lizard2_e_support_contact_20261022/artifact_index_at_review.json
```

真实重新执行必须换新目录/label；正例命令如下，离地反例只把 target_config 换回原 manifest，预期退出 1。

```powershell
python -B rl_exp/tools/diagnose/palm_contact_wiring.py --out rl_exp/out/lizard2_e_support_contact_20261022/contact_replay_new --target_config rl_exp/out/lizard2_e_support_contact_20261022/impact_input/manifest.json -- --task Lizard2-Flat-Play-v3 --num_envs 1 --steps 2 --headless --json rl_exp/out/lizard2_e_support_contact_20261022/contact_replay_new/report.json
python -B rl_exp/tools/diagnose/palm_entry_wiring.py --entry support --out rl_exp/out/lizard2_e_support_contact_20261022/support_replay_new --target_config rl_exp/out/lizard2_e_fresh_reset_20261020/measured_manifest.json -- --task Lizard2-Flat-Play-v3 --phases 0 --heights= --wiring_steps 2 --label runs/support/lizard2-e-replay-new --work_id lizard2-candidate-wiring --headless
```

以下只读复核摘要、预算和实际 support 输出；不会补写缺失证据。

```python
import json
from pathlib import Path
from rl_exp.tools.runrecord.binding import sha256_file
root = Path('rl_exp/out/lizard2_e_support_contact_20261022')
index = root / 'artifact_digests.json'
assert sha256_file(index) == 'afe25062ce46c320ba8ea0098b4921e5c48516ea2b3f8fbcd44d29539d3ede83'
for path, digest in json.loads(index.read_text(encoding='utf-8'))['files'].items():
    assert sha256_file(Path(path)) == digest, path
a = json.loads((root / 'support_final/audit.json').read_text(encoding='utf-8'))
report_path = Path('rl_exp/tools/diagnose/out/runs/support/lizard2-e-wiring-final-20261022/p0_measure_check.json')
r = json.loads(report_path.read_text(encoding='utf-8'))
assert a['closed'] and a['fixed_base'] and a['force_timing'] is False
assert a['max_joint_stiffness'] == a['max_joint_damping'] == 0
assert len(a['body_disable_gravity']) == 31 and all(a['body_disable_gravity'].values())
assert len(a['env_steps']) == 2 and len(a['physics_steps']) == 8
assert len(a['action_names']) == len(set(a['action_names'])) == 30
assert len(a['sensor_body_names']) == 31
feet = {'lf_wrist', 'rf_wrist', 'rl_ankle', 'rr_ankle'}
assert set(r['contact_sampling']) == set(r['naming_spawn_base_frame']) == feet
assert set(r['target_binding']) == set(a['target_binding']) | {'joint_order'}
assert all(r['target_binding'][key] == value for key, value in a['target_binding'].items())
assert r['target_binding']['joint_order'] == a['target_binding']['joint_names']
assert {row['body'] for row in r['load_closure']['per_body_desc']} == set(a['sensor_body_names'])
assert r['wiring']['env_steps'] == 2 and r['wiring']['warmup_steps'] == 0 and r['wiring']['action'] == 'zero'
assert 'zero_action' not in r
assert all(v == 0 for step in a['env_steps'] for row in step['action'] for v in row)
assert all(v == 0 for step in a['physics_steps'] for row in step['net_forces_w_n'] for v in row)
for name, code in [('impact_reset01', 1), ('impact_final', 0), ('air_final', 1),
                   ('support_final', 0), ('support_wrong_naming', 1)]:
    assert int((root / (name + '.exit')).read_text().strip()) == code
assert not Path('rl_exp/tools/diagnose/out/runs/support/lizard2-e-wiring-wrong-naming-20261022').exists()
print('SUPPORT_CONTACT_EVIDENCE_REPLAY_OK')
```

## 未覆盖边界

冲击正例只涉及两前腕；后踝零力，不能说四足同时承重。显式重置会改变初始状态并沿用初始化 solver 历史，已记为冲击 fixture，不能升级为自然落地或稳态支撑。两步入口不验证长窗 policy、支撑、跌倒、自然 timeout、有效限速、全 ROM 接触或正式协议能力。

旧 shared 诊断的扩展边界、旧资产 cap/contact ownership 回交及最终消费者出口清点仍在 E；本轮未关闭或迁走任何未完动作。B/C 的加载/默认驱动与 D/S6 责任保持原事项边界。共享 artifact_index 中还有其它会话的迁移变更，本轮不把混合索引作为本轮代码提交；其实际登记内容在本机复核时另存只读索引快照。
