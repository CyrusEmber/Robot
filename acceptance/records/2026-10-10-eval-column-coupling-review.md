# eval-column-coupling 独立审核：探针成立，归因与结论边界退回补齐（2026-10-10）

## 适用范围

- 用户要求 `eval-column-coupling review`，随后选择“落盘并退回”；本审核来自新上下文，不带执行会话历史。
- 对象：`work/active/eval-column-coupling.md` 的 `close_when` 与 `next`，以及 `acceptance/records/2026-10-10-eval-column-coupling-probes.md`。不以事项的“已证/已做”摘要代替证据。
- 核对实现：`ablation_harness/eval.py`、`metrics.py`、`suites.py`、地形摘要的采集与投影；框架的地形生成、摆位及启动播种顺序。复用现有地形生成探针，不新增仪器或闸门。
- 实测动作：核对下列六个 run 的 `eval.json`、`record.json`、`terrain/geometry.json`，复算现存 checkpoint 摘要；独立重建两条探针的地形。没有重跑 policy eval，也没有采集新的动力学轨迹。

| 简称 | run 目录（相对 `ablation_harness/results/`） |
|---|---|
| v2a | `locomotion_eval_v2/runtime-acceptance/Lizard2-Flat-v3_v3ckpt5999_nominal_seed123` |
| v2b | `locomotion_eval_v2/runtime-acceptance/Lizard2-Flat-v3_v2ckpt5999b_nominal_seed123` |
| v3a | `locomotion_eval_v3/runtime-acceptance/Lizard2-Flat-v3_v3ckpt5999_nominal_seed123` |
| v3b | `locomotion_eval_v3/runtime-acceptance/Lizard2-Flat-v3_v3ckpt5999b_nominal_seed123` |
| ctrl | `locomotion_eval_v3/coupling-probe/Lizard2-Flat-v3_probe-ctrl_nominal_seed123` |
| rougha | `locomotion_eval_v3/coupling-probe/Lizard2-Flat-v3_probe-rougha_nominal_seed123` |

- 只新增本审核记录、更新事项状态与证据指针。不改冻结协议、原执行记录、原 run 工件、实现或另一会话的工作树改动。

## 验收条件

1. 按原 `close_when`，至少一条单变量探针跑完，能明确指出改变的变量与受影响列，并据此排除或坐实机制；若两探针都不改变 stairs，须撤销耦合说法。不能把“已观察到影响”直接替换成“机制已隔离”。
2. 按 `next`：ctrl 必须复现 v2 的指标与归档几何；rougha 的 rough_a relief 必须回到零。相同摘要的含义须由采集位置解释，不以配置相同替代实际地形相同。
3. “非局部但非全局”必须限定到实际干预、checkpoint、seed、模式及观察指标；机制未取证不能同时被写成已排除其他机制。报告的指标粒度应与实现一致。
4. 对“不动几何”的后续入口，判明它要控制什么，不把“换 env 排布”当成同时排除 RNG 与 spawn 的实验。原关闭条件未完成前，入口缺失可以留待处置，不能凭一次评审自动延期或关闭。

## 结果

### 总判定

**不通过，退回 `in_progress`，不关闭。** 两条探针的成立条件通过，跨列影响有可复读证据；退回的是归因未达原关闭条件、结论越界和指标口径错误，不否定原始数字。当前缺口可就地补齐，不属于现有结构无法表达需求的架构问题。

### 成立部分：对照忠实，单列干预确实改变其他列

- v2a/v2b、v3a/v3b 的 `eval.json` 均只差 timestamp；两臂各自全部指标与地形归档相等。
- ctrl 与 v2a/v2b 的 `global`、`segments`、`terrains` 全部指标精确相等，env cfg snapshot 也相等。ctrl/v2a 的顶层差异仅 protocol、git revision、timestamp。
- ctrl 的九格归档与 v2 相等，几何摘要为 `sha256:9f38cddb912dfb3999381adabcec12d23bb94ef8f9adf61bc88734c80e831028`。
- rougha 与 v2 比，env snapshot 仅 rough_b 的 `noise_range` 两端、`noise_step`、`downsampled_scale` 四个叶子改变；九格中只有 rough_b 的 cell 摘要改变。rough_a 的 relief 为 `0.0`，rough_b 为 `0.0650000050663948` m。
- 独立重建 ctrl、rougha，调用现有 `terrain_split_probe.generate_record` 与 `terrain_geometry.evidence` 投影后，两份归档逐字段相等；rougha 摘要为 `sha256:52b69c126146243f4ac78c019dfde7f5b74c33bf3276981a9be31a51cf8ad984`。这不是只相信存档内两个字符串相同。
- 全部六个记录的 checkpoint 加载前/后摘要相等；现存文件复算也相等：`sha256:954fb332bdd7c56d0ba6cb8bb7faec443006bb1a62cd9b619855cd664b7ae1aa`。同 task、nominal、seed 123、72 env，agent、命令、指标声明、资产记录、obs 身份及引擎环境相等。

rougha 相对 v2 的所有受影响地形如下（保留原始值，不以四位小数判断相等）：

| 列 | completion：v2 → rougha | fall_rate：v2 → rougha | success_rate：v2 → rougha |
|---|---|---|---|
| slope_10deg | 0.8439210057258606 → 0.8738948106765747 | 0.75 → 0.625 | 0.5543457269668579 → 0.5999173521995544 |
| stairs_10cm | 0.7394453287124634 → 0.8536579608917236 | 0.75 → 0.5 | 0.5521759986877441 → 0.6484419107437134 |
| stairs_20cm | 0.9542731046676636 → 0.9479382038116455 | 0.0 → 0.125 | 0.7876923084259033 → 0.7703274488449097 |
| rough_a | 0.9140691757202148 → 0.8660351037979126 | 0.125 → 0.25 | 0.8696866035461426 → 0.7761049866676331 |
| rough_b | 0.8984109163284302 → 0.7688684463500977 | 0.25 → 0.375 | 0.7752701640129089 → 0.7010296583175659 |

flat、slope_5deg、gap_20cm、gap_40cm 的全部地形指标相等。故可以保留“本次 rough_b 干预关联到四个未改地形列的读数变化”；两个 stairs 列确实改变，不适用原关闭条件中“都不动 stairs 就撤销”的分支。

### P1：原关闭条件要求机制判定，当前证据仍停在影响观察

落点：`work/active/eval-column-coupling.md:8`；执行记录第 59–71、133 行。

- “只改变 rough_b 一格的碰撞几何”比实际取证强。cell digest 在 `terrain_split_probe.py:175-200` 的 `_add_sub_terrain` 调用前捕获，包含局部 vertices、faces、origin（`terrain_geometry.py:55-80`）；它不归档 PhysX 烹饪后的碰撞形状、接触、求解器状态或每 env 的实际出生状态。
- 框架随后按 row/col 与 tile size 摆位、加边框、合并和居中。本次布局相同，未改 cell 的局部几何及 origin 摘要相同有意义；但“其他列碰撞/初始化条件完全不变”不能从该摘要独立推出。可用措辞是“生成器交出的几何＋origin 摘要只在 rough_b 改变”，不是“已隔离 PhysX 的单一碰撞变量”。
- 当前记录明确承认 reset/spawn 未排除、求解器未取证。匹配受影响列的直觉不是接触顺序机制证据；非物理路径尚未控制，原 `close_when` 的机制部分没有完成。
- 不要求此时增加 seed、probe 重复或直接深入求解器；那不是原判据。最小返工是保留已成立观察，写清受控变量与未控变量，再做能够区分候选路径的探针；若只想收束“影响是否存在”，须由用户明确缩小关闭范围，不能用“剩下的归因另立项”自行替换原条件。

### P1：未变的四列不是长期可比性的白名单

落点：执行记录第 63–65 行；`work/active/eval-column-coupling.md:14-15`。

- 本次可以说“改变没有遍及全部列”。不能推出“任何套件改动让全表不可比的说法已被证伪”，更不能据此授权 flat/gap 等未变列跨协议比较。一个干预中输出相等，不是对其他干预、模型或 seed 的不变性证明。
- 两个协议仍是不同测量契约，协议本身也禁止跨版本混表；本次不是放宽该规则的证据。应把“非全局”限定为“本次已观测输出并未全变”，保留跨协议只作诊断的边界。
- 一年后最容易失效的假设正是把这四列当成安全白名单：换 checkpoint 或 suite 内容后，今日未显现的路径仍可能显现。现有套件整体绑定已经能表达这个约束，不需要新增列级可比框架。

### P2：功效段的量化步长错误，success_rate 也不是逐 env 二值比例

落点：执行记录第 136 行；`metrics.py:139-161,175-181`、`eval.py:606-612`。

- completion 是每 env 连续位移比值再取均值，没有 `0.125` 的量化步长。fall_rate 才是每 env 二值 flag 的均值，在八 env 下按 `1/8` 变化。
- 现行 success_rate 是全部有效帧的成功 mask 加权比例，不是每 env 一个成功 flag；因此也不能把它列入固定 `1/8` 粒度。
- 上游执行记录已在勘误中收回 completion 粒度，本次探针记录又重复了同一错误。不能用“只看变没变”免除口径修正；纠错须明确保留旧句已失效的痕迹，不无痕改写旧判断。

### P2：探针绑定与复读条件缺少独立披露

落点：执行记录第 11、34–37、66–68、75–81 行；对应 run 的 `record.json.runtime`。

- ctrl 的 Robot rev 为 `efa2ba75db29`，rougha 为 `751a3a446ae3`，v2 两臂为 `e4d1ac7d0a04`；v3a 的 record rev 为 `0f4b2bf5317a`，eval rev 为 `e4d1ac7d0a04`。Git 核对 v2→两探针的提交树变化没有测量实现变更，故本次不据此否定指标；但六份归档没有 dirty/diff 或运行时代码载荷，不能宣称完整执行代码逐字相同。
- rougha 相对正常 v3，只改 rough_a 配置却使 rough_b 的实际 relief 从 `0.05999999940395355` 变为 `0.0650000050663948` m；全局 numpy 消耗通道有源码支持。它证伪的是“改 rough_a 配置而保持 rough_b 实现不变”这一探针前提，不是证明 hf 列单变量干预永远不可能。此次 rougha-v2 本身就有八个 cell 相等。
- 原记录给出的 `%TEMP%` 脚本正文可恢复启动动作，但其对账命令仍用 `<run>/<ref>` 占位符，没有完整的逐格断言与重建命令。本审核下节给出实际执行的复读命令；后续执行证据应显式引用，不依赖会消失的本机脚本。

### “不动几何”入口的审定边界

实际变化向量：v2→v3 更换 rough 配方，随后出现摘要未变列的读数漂移；当前需求是隔离测量路径，不是添加通用实验框架。

- 归类：**local code / evidence problem**。现有包装注入、地形探针和记录格式可以表达诊断，没有证据表明必须重构 `eval.py`。
- “只换 env 排布”会改变 env↔地形映射、出生位置、可能的碰撞过滤与批处理索引；它不是独立排除 RNG/spawn 的开关。即便结果不变，也不能反向坐实某一机制。应先定义控制矩阵：哪些实际初态、局部/世界几何、env 映射不变，哪一条路径被干预，输出如何映射回原 env。
- 不能把待决入口自动认作“协议下一版”：诊断不改冻结判分语义时无需强制升协议；若改变正式排布、reset 或采样语义，才走新协议。当前审核不授权其中任何实现，也不关闭未定动作。

## 证据引用

- 执行证据：`acceptance/records/2026-10-10-eval-column-coupling-probes.md`；上游对照与已有勘误：`acceptance/records/2026-10-10-cross-protocol-suite-readings.md`、`2026-10-10-runtime-acceptance-v3-review.md`。本审核不覆盖其旧判断。
- 以下是本次实际运行的命令，cwd 为仓根。第一条只读归档、核 checkpoint 并打印原始差异；第二条用本机 `paths.yaml` 登记的解释器生成两份地形，不启动 policy rollout、不写文件。

```bat
python -c "import json,pathlib;from ablation_harness import record;root=pathlib.Path('ablation_harness/results');dirs={'v2a':'locomotion_eval_v2/runtime-acceptance/Lizard2-Flat-v3_v3ckpt5999_nominal_seed123','v2b':'locomotion_eval_v2/runtime-acceptance/Lizard2-Flat-v3_v2ckpt5999b_nominal_seed123','v3a':'locomotion_eval_v3/runtime-acceptance/Lizard2-Flat-v3_v3ckpt5999_nominal_seed123','v3b':'locomotion_eval_v3/runtime-acceptance/Lizard2-Flat-v3_v3ckpt5999b_nominal_seed123','ctrl':'locomotion_eval_v3/coupling-probe/Lizard2-Flat-v3_probe-ctrl_nominal_seed123','rougha':'locomotion_eval_v3/coupling-probe/Lizard2-Flat-v3_probe-rougha_nominal_seed123'};load=lambda p:json.loads(p.read_text(encoding='utf-8'));e={k:load(root/v/'eval.json') for k,v in dirs.items()};r={k:load(root/v/'record.json') for k,v in dirs.items()};g={k:load(root/v/'terrain/geometry.json') for k,v in dirs.items()};metric=lambda a:{k:a[k] for k in ('global','segments','terrains')};assert all(record.read_state(a)['state']=='complete' for a in r.values());assert len({a['checkpoint']['sha256'] for a in r.values()})==1;assert all(a['checkpoint']['sha256']==a['checkpoint']['sha256_after_load'] for a in r.values());assert record.file_sha256(r['ctrl']['checkpoint']['path'])==r['ctrl']['checkpoint']['sha256'];assert all(metric(e[a])==metric(e[b]) and g[a]==g[b] for a,b in [('v2a','v2b'),('v3a','v3b')]);assert metric(e['ctrl'])==metric(e['v2a']);assert g['ctrl']['cells']==g['v2a']['cells'];changed=[a['sub_terrain'] for a,b in zip(g['v2a']['cells'],g['rougha']['cells']) if a!=b];assert changed==['rough_b'];assert g['rougha']['cells'][5]['relief']==0.0;assert r['ctrl']['env_cfg']['snapshot']==r['v2a']['env_cfg']['snapshot'];assert all(a['agent_cfg']==r['ctrl']['agent_cfg'] and a['commands']==r['ctrl']['commands'] and a['metrics']==r['ctrl']['metrics'] for a in r.values());print('RAW_PROBE_CHECKS_PASS');print('changed_cells',changed);print('changed_terrain_metrics',[(n,k,e['v2a']['terrains'][n][k],e['rougha']['terrains'][n][k]) for n in e['v2a']['terrains'] for k in e['v2a']['terrains'][n] if e['v2a']['terrains'][n][k]!=e['rougha']['terrains'][n][k]]);print('revision_pairs',[(k,r[k]['runtime']['git_rev_lizard'],e[k]['git_rev_lizard']) for k in dirs])"

E:\IsaacLab\env_isaaclab\Scripts\python.exe -c "import pathlib,json;from ablation_harness import suites;from rl_exp.tasks.terrain_geometry import seed_rngs,evidence;from rl_exp.tools.verify import terrain_split_probe;root=pathlib.Path('ablation_harness/results/locomotion_eval_v3/coupling-probe');exec('for mode,tag in [(\"ctrl\",\"probe-ctrl\"),(\"rougha\",\"probe-rougha\")]:\n p=root/(\"Lizard2-Flat-v3_\"+tag+\"_nominal_seed123\")/\"terrain/geometry.json\"\n a=json.loads(p.read_text(encoding=\"utf-8\"));cfg=suites._LIZARD_SUITE_V2_GENERATOR.copy()\n cfg.sub_terrains[\"rough_a\"]=suites._LIZARD_SUITE_V1_GENERATOR.sub_terrains[\"rough_a\"].copy()\n if mode==\"ctrl\": cfg.sub_terrains[\"rough_b\"]=suites._LIZARD_SUITE_V1_GENERATOR.sub_terrains[\"rough_b\"].copy()\n seed_rngs(a[\"identity\"][\"seed\"]);b=evidence(terrain_split_probe.generate_record(cfg),identity=a[\"identity\"])\n assert a==b,str(p)\n print(\"PROBE_GEOMETRY_REGENERATED_EQUAL\",mode,b[\"geometry_digest\"])')"

git diff --name-status e4d1ac7d0a04 efa2ba75db29
git diff --name-status e4d1ac7d0a04 751a3a446ae3
```

第一条返回 `RAW_PROBE_CHECKS_PASS`；第二条分别返回 ctrl、rougha 的 `PROBE_GEOMETRY_REGENERATED_EQUAL`，每次九格均有摘要、无 anomaly。以上只验证工件和地形，不宣称动力学机制已验证。

提交前验证：`rl_exp/tools/verify/run_offline_checks.bat` 返回 `ALL_OFFLINE_CHECKS_PASSED (37/37)`；`python rl_exp/tools/verify/check_work_docs.py` 返回 `WORK_DOCS_OK`；`git diff --check`、五节顺序与事项状态/证据路径断言通过。离线绿证明既有机器检查成立，不替代本次人工归因判定。

## 未覆盖边界

- 没有 policy 重跑、probe 自身重复、其他 seed/ckpt 或 robust；不把这些事后追加为原关闭门槛。
- 原工件没有逐 env 初态、轨迹或 first_done 载荷，无法定位分叉帧；cell 摘要不是 PhysX 碰撞烹饪/接触/求解器证据。
- 框架 `manager_based_env.py` 在 scene 创建前按 env seed 重新播种；`eval.py:801` 的 SUITE_SEED 不能从当前顺序保证覆盖非默认 eval seed。本次二者均为 123，地形重建相符，不把该风险当本次耦合根因。
- 现行配方 `lizard2_no_dr` 钉住 reset 的关节和根状态范围（`rl_exp/tasks/lizard2_recipe.py:297-333`），不能无取证地把全局 RNG 消耗直接解释成 nominal 的出生随机变化。
- 后续修订执行证据或新增探针后，应再次置 `pending_review`，由新上下文审实际控制变量与原关闭条件。本记录存在不等于返工已经完成。
