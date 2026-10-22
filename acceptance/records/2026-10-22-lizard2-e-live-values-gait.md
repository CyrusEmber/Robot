# E 在线观测拒错与 fresh gait 写读复验

## 适用范围

用户要求继续修复 `lizard2-candidate-wiring`。本轮只补 E 消费者：独立在线检查器拒绝非有限观测；在既有 measured manifest 的固定根、禁重力、零增益候选中验证各列不同的非零位置/速度/动作及命令；复验同一 fresh 输入的 gait writer → reader → 绘图。没有修改正式资产、v3、配方、驱动、求解器设置或协议，没有训练，也没有新增默认套件条目。

速度来源与受载工况的另一切片归[速度/观测记录](2026-10-22-lizard2-velocity-observation.md)，本轮不代替该切片的因果判断。原导出、转换、过滤、reset 证据归[新输入记录](2026-10-15-lizard2-e-spatial-runtime-wiring.md#追加新正式导出身份接入隔离-usd-与真实消费者2026-10-20)。

本轮在线与 gait 启动日志均保留 `enable_external_forces_every_iteration=False` 警告，与当前训练配置的时序相同；没有采用 true 对照设置。状态注入无物理推进及零增益中立 gait 不证明该时序下受载速度正确，相关边界仍按速度记录承接。

## 验收条件

实际 `check_task()` 遇 NaN/Inf 必须失败；非零 q/dq 分别与后端相等，七项 policy 按实际 clip/scale 独立逐值核对，动作列与关节列分别留序；报告须保存原始读数、源码身份和未验边界。gait 须消费 fresh 绑定及完整五角色列，拒绝缺来源、缺 twist、混名和外来末端；不把零动作短窗作为步态或 terminal hook 验收。

## 结果

`obs_protocol_live.py` 原来只检查 term 顺序、宽度和 shape，reset tensor 含非有限值仍可报通过。`test_obs_protocol_gate.py` 用 AST 加载真实 `check_task()`，仅替换环境/协议服务，传入同 shape 的 reset tensor：修复前 NaN/Inf 两项均未产生 problem，测试退出 1（`OBS_PROTOCOL_GATE_FAILED (2)`）；增加 `value_problems()` 后同两例被拒绝，有限值正例保持通过。非零比较器另核同宽度排列、反号、shape、NaN、Inf 五类拒错；这些是离线消费者反例，不是向物理环境注入 NaN。

新增显式 `--value_report`，只接受一个隔离 task/environment、固定根、禁重力、零 Kp/Kd 和无噪声/历史/修改器的七项 policy。写状态而不调用 `sim.step/env.step`；恢复原关节状态、raw action 与命令后关闭环境。命令缓冲区的人工注入只验证命令到观测的消费，不验证采样器或可行动作。保留默认 CLI，正式配置不被改写。

真实在线运行两次，均正常退出 0；首次核对通过后，为便于独立复算增加 backend 原始数组和实际 clip/scale 留存，再执行同条件第二次。两次均没有在注入阶段推进物理；启动/reset 本身不属于“新增物理步为零”的断言范围。第二次完整证据为 `attempt02/report.json`，`completed=true`：

- runtime 30 个关节每列分别注入两种符号的 `q[i]=sign*(i+1)*0.001 rad`、`dq[i]=-sign*(i+1)*0.002 rad/s`，均在实际位置限位内；后端 q/dq 与输入相等。
- raw action 按实际 action-manager 顺序注入倒序数列，最大幅度 0.09；命令为 `sign*[0.17,-0.23,0.31]`。policy 102 维，七项逐值最大误差均为零。
- 两符号下对实际 joint_pos/joint_vel/actions 片段各做排列破坏，六例均由同一个比较消费者拒绝。原始 q、dq、backend、raw action、命令、最终 observation、切片及变换均已保存。
- 四足端仍为 `lf_wrist/rf_wrist/rl_ankle/rr_ankle`；输出保留 `102(unapproved)`，没有批准新协议。根速度为零、根姿态中立，当前默认 q/dq 全零，故本轮不单独证明非零根坐标变换或非零默认值扣除；另一个工况的相应证据只按其原记录复用。

gait 实际 CLI 退出 0，采集 10 个控制步、0.2 s；该工具将 episode 长度设为采集窗，done 序列是九个 False 后一个 True。首局严格在 done 前的有效/记录帧均为 9，没有把末帧复活。实际 writer 输出腿部 60 列（四腿五角色，各 actual/target/vel）及躯体 30 列，保存的列均为 9 帧且 finite；当前值全零，不据此证明非零运动映射。

`plot_joints.report_naming()` 与 CLI 实际消费该报告，`JOINT_PLOT_OK (palm_spatial)`；两张 PNG 和 index 已生成并目视核对，仍只展示原三个面板，twist 原始列完整校验。对实际报告的内存副本分别清空 source、删一列 twist、将 naming 改 split、将末端改为 `lf_finger`，四例均拒绝，原始报告字节未变。gait 的 done 只核其原首局掩码，不能代替 baseline `_reset_idx` 前快照 hook。

## 证据引用

本机工件不承诺入仓。输入 measured manifest 为 `rl_exp/out/lizard2_e_fresh_reset_20261020/measured_manifest.json`，SHA256 `d876713b1a4aa6a4fef51f39bed284f4a15a01d562815eefefcf74eebfb77137`；其中 USD/URDF 身份继续取原新输入记录。

| 工件（路径相对仓根） | SHA256 |
|---|---|
| `rl_exp/out/lizard2_e_obs_values_20261022/attempt02/report.json` | `6b6be92e7971f14dfbc318da8ed27ae1e167ba15a0342f18a78c0af3a6a431bb` |
| 同目录 `report.json.source.py` / 本轮在线入口 | `7632693e83e542110552fdd5d832fe268fb9981af4071a8aa703798f6b2c0853` |
| `rl_exp/out/lizard2_e_gait_20261022/attempt01/report.json` | `1828d065d3e5b1f7e8001c7b9add33be4e2f1eaf65c906ed845b2acd35286e1c` |
| 同目录 `plots/report_index.json` | `6c4b7dcc00dfbf61806f7e61c0db0d6d6fcecd5ea1eac167703198af0d204182` |

gait 和绘图源码本轮未改，采集后核对与 HEAD 无差异：`gait_probe.py` SHA256 `ae3addafe300aa86d7dc3656302c07cc6f596a6dbaf54817d5a86463d7501d8f`，`plot_joints.py` 为 `c840be6a0c3680a6a0ae8f606c7205c742095de31b99f4130db6568b1a680d96`。在线观测实测保留完整源码快照，不以最终测试文件身份冒充历史采集源码。

修复前/后回归日志 `rl_exp/out/lizard2_e_obs_regression_before_20261022.log` / `lizard2_e_obs_regression_after_20261022.log`，首次与第二次实际在线日志 `lizard2_e_obs_values_20261022_attempt01.log` / `lizard2_e_obs_values_20261022_attempt02.log`，gait/绘图/反例日志 `lizard2_e_gait_20261022_attempt01.log` / `lizard2_e_gait_plots_20261022.log` / `lizard2_e_gait_audit_20261022.log`。最终新增比较器反例并入原套件自检，不以较早 after 日志冒充最终测试源码身份。

从仓根运行；重新采集、绘图须换不存在的输出路径：

```powershell
& E:/IsaacLab/env_isaaclab/Scripts/python.exe -B rl_exp/tools/verify/test_obs_protocol_gate.py
& E:/IsaacLab/env_isaaclab/Scripts/python.exe -B rl_exp/tools/verify/obs_protocol_live.py --headless --device cuda:0 --tasks Lizard2-Flat-Play-v3 --envs 1 --target_config rl_exp/out/lizard2_e_fresh_reset_20261020/measured_manifest.json --naming palm_spatial --value_report rl_exp/out/lizard2_e_obs_values_replay/report.json
& E:/IsaacLab/env_isaaclab/Scripts/python.exe -B rl_exp/tools/diagnose/gait_probe.py --task Lizard2-Flat-Play-v3 --target_config rl_exp/out/lizard2_e_fresh_reset_20261020/measured_manifest.json --policy_mode zero --speeds 0 --seconds 0.2 --viz none --out rl_exp/out/lizard2_e_gait_replay/report.json
& E:/IsaacLab/env_isaaclab/Scripts/python.exe -B rl_exp/tools/diagnose/plot_joints.py --report rl_exp/out/lizard2_e_gait_20261022/attempt01/report.json --out_dir rl_exp/out/lizard2_e_gait_replay/plots
```

无需起物理的原始数值复算入口（PowerShell，将脚本经 stdin 交同一 venv Python）：

```powershell
@'
import json
from pathlib import Path
import numpy as np
from rl_exp.tools.runrecord import binding
from rl_exp.tools.diagnose.plot_joints import report_naming
base = Path('rl_exp/out/lizard2_e_obs_values_20261022/attempt02')
raw = (base/'report.json').read_bytes()
assert binding.sha256_bytes(raw) == '6b6be92e7971f14dfbc318da8ed27ae1e167ba15a0342f18a78c0af3a6a431bb'
r = json.loads(raw)
assert r['completed'] and r['added_physics_steps'] == 0 and len(r['samples']) == 2
assert binding.sha256_file(base/'report.json.source.py') == r['code_sha256']
assert binding.sha256_file(Path(r['target_binding']['source'])) == r['manifest_sha256']
for s in r['samples']:
    np.testing.assert_array_equal(s['backend_q_rad'], s['q_rad'])
    np.testing.assert_array_equal(s['backend_dq_rad_s'], s['dq_rad_s'])
    values = dict(base_lin_vel=[[0,0,0]], base_ang_vel=[[0,0,0]], projected_gravity=[[0,0,-1]], velocity_commands=s['command'], joint_pos=np.array(s['q_rad'])-r['default_joint_pos'], joint_vel=np.array(s['dq_rad_s'])-r['default_joint_vel'], actions=s['raw_action'])
    obs = np.array(s['observation'])
    assert np.isfinite(obs).all() and obs.shape == (1,102)
    for name, (begin,end) in s['slices'].items():
        value = np.array(values[name], dtype=np.float32)
        transform = r['transforms'][name]
        if transform['clip'] is not None: value = np.clip(value, *transform['clip'])
        if transform['scale'] is not None: value *= transform['scale']
        np.testing.assert_allclose(obs[:,begin:end], value, atol=1e-6, rtol=0)
g = json.loads(Path('rl_exp/out/lizard2_e_gait_20261022/attempt01/report.json').read_text())
report_naming(g)
e = g['envs'][0]
assert e['done_series'] == [False]*9+[True] and e['frames_alive'] == e['frames_recorded'] == 9
print('E_VALUES_GAIT_REPLAY_OK')
'@ | & E:/IsaacLab/env_isaaclab/Scripts/python.exe -B -
```

### 仓库检查

首次完整离线套件 36 项通过、一项失败，57.4 s：另一事项的本机临时脚本 `rl_exp/out/inspect_velocity_final_20261022.py:41` 直接计算摘要，被单一来源闸门拒绝。本轮没有修改该文件或放宽闸门；随后读取时该处已换成共享 `sha256_file()`。重跑发现本记录的节标题未按模块文档命名，fail-fast；已更正标题，不豁免格式闸门，最终完整套件结果另行回填。

更正后再跑 36 项通过、一项失败，52.2 s，指向新出现的本机提交辅助脚本 `rl_exp/out/commit_velocity_work_20261022.py:41` 使用 `rev-parse --short`。确认对应提交已完成后，仅将该未跟踪脚本的导入和 revision 输出改成既有 `binding.git_rev(root)`；没有执行该脚本、修改其已生成记录或纳入提交。保持原闸门不变，继续核验本轮四个归属文件。

最终完整套件退出 0：`ALL_OFFLINE_CHECKS_PASSED (37/37 in 56.9s, jobs=6)`，日志 `rl_exp/out/lizard2_e_wiring_offline_verified_20261022.log`；原默认套件条数未变，包含新增 NaN/Inf 和比较器反例。记录内无物理复读代码实际执行退出 0，`E_VALUES_GAIT_REPLAY_OK`，日志 `rl_exp/out/lizard2_e_values_gait_replay_20261022.log`。本轮路径 diff 格式通过，提交前钩子结果随收尾保留。

代码提交 `78282f0`，仅两个 verify 源码；提交前显式钩子及 commit 内正常钩子均退出 0，日志 `rl_exp/out/lizard2_e_precommit_code_20261022.log`、`lizard2_e_commit_code_20261022.log`。证据记录与事项指针另笔同次提交，不包含其它事项源码或工件。

## 未覆盖边界

本项继续 `in_progress`：baseline terminal hook、完整 E3 出口与受影响旧基线清点、旧资产 ownership 回交、B 默认驱动有效边界和 D 新上下文集成审核仍未完成。此记录为执行者自检，不是事项关闭审核；不据本轮局部通过批准开训或 S6 性能。
