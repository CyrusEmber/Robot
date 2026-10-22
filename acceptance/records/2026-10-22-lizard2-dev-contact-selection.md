# 开发配方移除无碰撞体的处罚选择

## 适用范围

用户在了解旧 v3 的空处罚选择后授权继续修改。本轮修改未冻结的 `rl_exp/versions/lizard2/main/main_params.yaml`，供后续配方采用；已训练 v3 的参数、资产锁、差异声明、记录与任务身份保持原样。版本边界按 `.codemaker/rules/versioning.mdc` §A，旧对象来源及先前隔离验证见 [原对象回交](2026-10-22-lizard2-e-legacy-contact.md)。

正式 `Lizard2-Flat-v3` / Play-v3 始终加载 v3 目录，不会因开发文件变化而变更历史含义。本轮未建立或冻结新训练版本，也未启动训练；正式版本接入归 S6 的采用流程。

## 验收条件

- 开发配置只移除四个无 collider 的 `kfe`，保留四个 `hfe` 与腹部处罚；train/play 完整配置差异只涉及处罚对象选择。
- 回归在修改前失败、修改后通过；恢复空项、清空有效选择、扩大选择均必须被拒绝，不将历史冻结配方改成新预期。
- 构建出的选择转写为具名隔离诊断输入，真实 CLI 做同资产正反对照，读取已解析对象与精确地面过滤力；静态选择检查不单独证明接触能力。
- v3 全目录逐文件摘要不变；相关检查与仓库闸门通过后分组提交。

## 结果

开发 YAML 删除 `names.undesired_contact_body_names` 下的 `.*_kfe` 一行。实际配置工厂分别构建 train/play 的开发态实例（显式 `params_version=None`）；完整 snapshot 的唯一差异都是 `rewards.undesired_contacts.params.sensor_cfg.body_names`，从 `[.*_hfe, .*_kfe]` 变为 `[.*_hfe]`。权重、腹部项、资产、驱动、动作、观测、终止与其余配置均未变化。

回归并入既有 `check_recipe_build.py`：实际构建开发 train/play，再由 IsaacLab 的匹配函数解析对象，与当前 URDF 的碰撞归属比较，并要求保留四个 hfe。此切片属于**构建和选择解析的行为检查**，不增加套件条目，不声称静态 URDF 检查替代 live collider/物理验证。新增反例恢复原 `hfe+kfe`、清空选择、选择全部 body，均在同一进程被拒绝。加入该回归、尚未改 YAML 时实际退出 1，报告四个无 collider 的 kfe；删除后退出 0，原六个冻结任务的 golden 比较仍成立，未刷新任何配方锁。

随后把实际构建实例的选择原样写入 before/after 隔离 manifest；这一步只将前述唯一差异应用到原 v3 的隔离诊断配置，没有将开发文件冒充正式 v3 配方。资产沿用已校验的 adopted shared 字节相同副本。生产者仍为 `check_contact_ownership.py`，由现有 `legacy_contact_wiring.py` 观察：1 env、零 action、初始化后 60 control/240 physics steps；保留原 PD、free base、重力开启、自碰撞关闭、force timing False，所有 live collider 使用精确 body→ground view。

修正前 CLI 退出 1、报告 FAIL，唯一失败为处罚对象含无 collider 的四个 kfe；修正后退出 0、报告 PASS。实际解析到的 `undesired_contacts` 只有四个 hfe，`belly_contact_force` 仍为 `base_link`。四足均测到非零地面力，18 个实际 collider 行的 URDF/USD extent 相符，原生净力与对应地面过滤力逐采样一致。两个窗口的完整 physics force 数组和初始/最终 q 相同。

v3 目录全部文件的前后 SHA-256 相同。首次完整套件由历史快照被当成当前源码扫描而失败，修复与反例归[扫描范围记录](2026-10-22-record-binding-source-scope.md)；修复后完整套件 37/37，在原条数与成本预算内通过（54.3 s）；recipe build 为 8.9 s，record binding 为 8.8 s。暂存本轮源码后执行 pre-commit，静态闸门通过。本记录为执行者自检，E/D 总项仍独立审核。

## 证据引用

- 开发配置与构建回归提交：`4865523`。
- 本机制品：`rl_exp/out/lizard2_dev_contact_20261022/`。`artifact_digests.json` 覆盖 29 个输出、71 个输入，SHA-256 `c77a647699c75bf34be53f42176c86e56b3c97c71d85f0992a62862061e963ef`；包含开发文件前后副本、两类配置前后 snapshot、完整差异、原 v3 目录摘要、回归红绿、两个真实运行及源码/观察器快照，输入还绑定实际 URDF/USD 与引用网格。制品本体不承诺入仓。
- `gate_before/after.log/.exit` 是同一新增检查对 YAML 修复前后的结果；`train/play_before/after.json` 与 `cfg_deltas.json` 记录完整构建差异；`before/after` 中的 report/audit 及根目录同名 log/exit 记录真实进程。
- 复跑开发选择及冻结 golden：`python rl_exp/tools/verify/check_recipe_build.py`。真实 CLI 的复跑使用本轮 after manifest 与新输出目录：

```powershell
& E:/IsaacLab/env_isaaclab/Scripts/python.exe -B rl_exp/tools/diagnose/legacy_contact_wiring.py --target_config rl_exp/out/lizard2_dev_contact_20261022/after.json --out rl_exp/out/lizard2_dev_contact_recheck
```

仓根执行下列 Python 只读复读，不启动 Kit：

```python
from pathlib import Path
import json
import numpy as np
from rl_exp.tools.runrecord.binding import sha256_file

root = Path('rl_exp/out/lizard2_dev_contact_20261022').resolve()
index = root / 'artifact_digests.json'
assert sha256_file(index) == 'c77a647699c75bf34be53f42176c86e56b3c97c71d85f0992a62862061e963ef'
data = json.loads(index.read_text(encoding='utf-8'))
assert len(data['files']) == 29 and len(data['inputs']) == 71
for name, digest in data['files'].items():
    assert sha256_file(root / name) == digest, name
for name, digest in data['inputs'].items():
    assert sha256_file(Path(name)) == digest, name
for name, digest in json.loads((root / 'frozen_v3_sha256.json').read_text(encoding='utf-8')).items():
    assert sha256_file(Path(name)) == digest, name
assert (root / 'gate_before.exit').read_text().strip() == '1'
assert (root / 'gate_after.exit').read_text().strip() == '0'
for deltas in json.loads((root / 'cfg_deltas.json').read_text(encoding='utf-8')).values():
    assert deltas == [{'path': 'rewards.undesired_contacts.params.sensor_cfg.body_names',
                       'before': ['.*_hfe', '.*_kfe'], 'after': ['.*_hfe']}]
for kind in ('train', 'play'):
    before = json.loads((root / (kind + '_before.json')).read_text(encoding='utf-8'))
    after = json.loads((root / (kind + '_after.json')).read_text(encoding='utf-8'))
    selector = before['rewards']['undesired_contacts']['params']['sensor_cfg']
    assert selector['body_names'] == ['.*_hfe', '.*_kfe']
    selector['body_names'] = ['.*_hfe']
    assert before == after
audits = []
for phase, status, exit_code in (('before', 'FAIL', '1'), ('after', 'PASS', '0')):
    audit = json.loads((root / phase / 'audit.json').read_text(encoding='utf-8'))
    report = json.loads((root / phase / 'report.json').read_text(encoding='utf-8'))
    manifest = json.loads((root / (phase + '.json')).read_text(encoding='utf-8'))
    assert sha256_file(root / ('main_params_' + phase + '.yaml')) == manifest['source_inputs']['dev_yaml_sha256']
    assert sha256_file(root / phase / 'source.py') == audit['source_sha256']
    assert sha256_file(root / phase / 'observer.py') == audit['observer_sha256']
    assert sha256_file(root / (phase + '.json')) == audit['manifest_sha256']
    assert audit['closed'] and audit['env_steps'] == 60 and len(audit['physics_steps']) == 240
    assert audit['decimation'] == 4 and audit['force_timing'] is False
    assert audit['gravity_enabled'] and not audit['fixed_base'] and not audit['self_collisions']
    assert report['status'] == status and (root / (phase + '.exit')).read_text().strip() == exit_code
    assert set(report['touching']) == set(manifest['target_binding']['end_links'].values())
    assert not report['blind'] and all(row['extent_match'] for row in report['bodies'].values())
    names = audit['sensor_body_names']
    assert [p.rsplit('/', 1)[-1] for p in audit['native_sensor_paths']] == names
    net = np.array([p['net_forces_w_n'] for p in audit['physics_steps']]).reshape(240, 31, 3)
    assert np.isfinite(net).all() and len(audit['ground_contact_mapping']) == 18
    peaks = np.linalg.norm(net, axis=-1).max(axis=0)
    assert {name for name, peak in zip(names, peaks) if peak > report['threshold']} == set(report['touching'])
    for name, row in report['bodies'].items():
        assert abs(row['peak_n'] - peaks[names.index(name)]) <= .00051
    for row in audit['ground_contact_mapping']:
        assert row['sensor_paths'] in ([row['source']], [[row['source']]])
        assert len(row['ground']) == 1 and row['filter_paths'] in (row['ground'], [row['ground']])
        ground = np.array([p['ground_forces_w_n'][row['body']] for p in audit['physics_steps']])
        assert ground.shape == (240, 1, 1, 3) and np.isfinite(ground).all()
        assert np.array_equal(ground.reshape(240, 3), net[:, names.index(row['body']), :])
    selected = set(report['terms']['undesired_contacts'])
    hfe = {leg + '_hfe' for leg in ('lf', 'rf', 'rl', 'rr')}
    assert report['terms']['belly_contact_force'] == ['base_link']
    if phase == 'before':
        assert selected == hfe | {leg + '_kfe' for leg in ('lf', 'rf', 'rl', 'rr')}
        assert report['problems'] == ['every penalty body carries a collider']
    else:
        assert selected == hfe and not report['problems']
    audits.append(audit)
assert audits[0]['physics_steps'] == audits[1]['physics_steps']
assert audits[0]['initial_q'] == audits[1]['initial_q'] and audits[0]['final_q'] == audits[1]['final_q']
assert sha256_file(root / 'offline_suite_scope_fixed.log') == 'cb1ffb9b6fa00442686c3fdd0081e10d5fc4041c35fce81bb6ea43f58450fdc0'
assert sha256_file(root / 'precommit.log') == '391523aed2dda995b424c93d3edc84c32a3122acab4dc7e6b975fd54ccc9db8a'
print('DEV_CONTACT_SELECTION_EVIDENCE_REPLAY_OK')
```

## 未覆盖边界

本轮证明开发选择的修正及原对象诊断接线，不是新版本训练或新机体正式采用。足端载荷窗口未主动制造非足端接触，不证明 hfe/腹部处罚已由非零非足端接触触发，也不外推稳定步态、ROM、自碰撞或驱动边界。后续正式版本须继承开发修正、更新相应身份与锁，并按 S6/版本流程验证；E/D 与地面接触的其余待办继续保留。
