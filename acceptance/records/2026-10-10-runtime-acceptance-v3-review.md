# runtime-acceptance-v3 独立审核：退回补齐判定（2026-10-10）

## 适用范围

- 用户要求评审并落盘；本审核来自新上下文，不带执行者会话历史。
- 对象：`work/active/runtime-acceptance-v3.md` 的 `close_when`、`next` 三个审核问题，以及 `acceptance/records/2026-10-10-cross-protocol-suite-readings.md`。
- 实现核对：`ablation_harness/eval.py`、`metrics.py`、`suites.py`、`record.py`、`HARNESS.md`，地形证据的采集与序列化；关联事项 `work/active/eval-column-coupling.md`。
- 实测核对对象是执行记录列明的四个 run。下文简称 v2a/v2b/v3a/v3b，依次对应该记录第 12–15 行中的 v2 首跑、v2 重跑、v3 首跑、v3 重跑。没有重新启动 policy eval；本次独立重建了四份地形并对账 JSON、CSV 和 checkpoint 文件。
- 不改冻结协议、实现、原 run 工件或原执行记录；判定与勘误留在本记录。

## 验收条件

1. 依原 `close_when`：同一 ckpt 在 v2/v3 各跑且各重跑一次；差异在原容限内可接受，超出必须列出差异并判断口径问题所在，不能事后把失败改称通过。
2. 依原事项文字，② 是有动作策略跑过后观察九列 completion；没有逐 env 方差、置信区间或策略成绩门槛。审核不事后追加这些门槛，也不把“已有逐列均值”升级为“逐 env 分布已验证”。
3. 四份 `record.json`、`eval.json`、`terrain/geometry.json`、组内 `summary.csv` 与现存 checkpoint 应自洽；源码的声明不替代对账与地形重建。
4. 未完成的归因可以独立立项，但若原关闭条件仍依赖它，不能同时称其“不阻塞”与“成立前提”。跨协议观察只能作测量差异诊断，不能成为跨协议策略排名或旧行可比性声明。

## 结果

### 总判定

**不通过，事项退回 `in_progress`，不关闭。** 运行与原始数字可信；阻塞来自①未完成的口径判定，以及事项宣称已经改写却没有给出有效新判据。②按原有“九列读数”范围成立，不是策略能力验收。

### P1：①的事后改写没有消除反例，超差后的判定仍未完成

落点：`work/active/runtime-acceptance-v3.md:7-8,19-20`；执行记录第 21、58–62 行；`work/active/eval-column-coupling.md:7-8`。

- 执行记录原验收条件已经限定“几何相同的列”；改称“只在 mesh digest 相同的列上比”不是能解释反例的新判据，因为反例就在摘要完全相同的列里。
- 独立重算的全部超容限项（v3 − v2，未取整）是：

  | 列 | 指标 | 差值 |
  |---|---|---:|
  | stairs_10cm | completion | +0.03867387771606445 |
  | stairs_10cm | fall_rate | −0.125 |
  | stairs_10cm | success_rate | +0.04099684953689575 |
  | stairs_20cm | success_rate | +0.0911596417427063 |

- 执行记录正确披露失败，未伪造读数；但“原因不是口径”“跨列耦合成立”超出目前隔离程度。可证明的是：在所记录条件下，改套件后，原始网格摘要相同的列读数改变；不能仅凭这点排除 reset/初始化、接触求解、指标依赖或归档之外的差异。
- 本次跨协议 cfg 快照逐字段核对，差异局限于 rough 两列；但每列实际 reset/spawn 与接触状态未归档。关联事项自己也承认机制未定，原①要求的超差归因/口径判断仍不能靠它的存在替代。
- 最小补齐：保留失败；补成明确的、有限范围的不可比/口径判定及依据，或用关联事项的隔离证据完成归因，再重新审核。若另行决定把本项缩成“真跑并发现问题”，必须明示这是关闭范围变更，不得把原容限验收说成通过。不要求借本审核重构实现或修改冻结协议。

### ②：按原范围成立；OOD 不判分没有使这个检查变空

落点：`ablation_harness/eval.py:601-612`、`ablation_harness/metrics.py:139-161`、`ablation_harness/HARNESS.md:20-24`。

- 四个 run 都是 checkpoint policy；九列齐全，completion 有非零、不同的逐列值。v3 的 rough_a/rough_b 均值为 0.7375637292861938 / 0.9135168790817261，满足原事项观察非零策略九列输出的检查。
- `eval.py` 把每 env completion 取均值后输出；现有报告没有逐 env completion 样本。因此可称“九列 completion 均值的形状”，不能称“每列逐 env 分布已验证”。这是一项表述边界，不是事后新增的关闭条件。
- OOD 不判分限制的是策略好坏的引用，不禁止用 OOD 数据核对测量链是否产出；所以②并非空判。反之，“不判分”也不能豁免①的协议差异核对。
- 执行记录第 87 行把 completion 说成量化步长 0.125，错误。0.125 是八 env 下 fall_rate 的计数步长；completion 是连续比值的均值。原“唯一变化即 noise_range”也漏了 noise_step 与 downsampled_scale（`suites.py:125-138`），需在后续勘误中明确。

### 工件对账：主要读数成立，首个 v3 run 有 revision 自述冲突

- 四个记录的 `record.read_state` 都为 complete；checkpoint sha256 及加载后重查一致，现存文件复算也是同一摘要：`954fb332bdd7c56d0ba6cb8bb7faec443006bb1a62cd9b619855cd664b7ae1aa`。
- 四臂均为 nominal、seed 123、72 env；suite 几何摘要与归档绑定一致。
- v2a/v2b、v3a/v3b 的 `eval.json` 去 timestamp 后均相等；各臂几何归档完全相等。各组 CSV 行与 JSON 的对应指标按输出四位小数相符。
- 跨协议七个未改列的整份 cell 摘要相等，只有 rough 两列不同。四份地形用自身 identity 的 suite+seed 重建，经 `terrain_geometry.evidence` 转成归档形状后与原件全部相等。v3 rough relief 为 0.029999997466802597 / 0.05999999940395355 m，v2 两列为 0。
- **revision 冲突**：v3a 的 `record.json:1566` 为 `0f4b2bf5317a`，但 `eval.json:9` 与 CSV 为 `e4d1ac7d0a04`。`eval.py` 在构建记录与输出指标时分别读 rev，中间发生提交即可形成此形状。本次用 Git 核对两 rev 之间只有 `work/active/lizard2-family-landing.md` 的散文变更，测量代码没有差异，所以这次不因此否定数字。但执行记录应披露双 rev，不能靠去掉 timestamp 后相等宣称记录条件也完全相同；原工件不得无痕回写。
- complete 是字段形状与加载绑定检查，不是所有事实已独立验证。上述对账与重建才支持本段结论。

### 风险限定，不把源码疑点冒充本次反例

- `eval.py:801` 的 SUITE_SEED 播种发生在 `gym.make` 前；实际框架 `manager_based_env.py:102-104` 先按 env cfg seed 重新播种，再于第 172–176 行构造 scene。故“地形永远不受 --seed 影响”不能从当前接线推得；非默认 seed 的身份归档存在潜在错标风险。**这四臂 eval seed 与 suite seed 都是 123，且地形独立重建相符，不构成本次阻塞，也不能把本次成功外推到别的 seed。**
- 当前家族 `lizard2_no_dr` 将 reset 范围钉成常量；不能未经验证就用“rough 消耗随机数导致 reset 改变”解释本次 nominal 超差。
- success_rate 是有效帧加权，completion/fall_rate 是 env 均值，不能当同一估计量。stairs_20cm 两臂 fall 都为零，不能仅据 success 差就归因为 fallen env 的幸存者偏差。
- 关联事项的列重排会同时改变位置/列分配、spawn 和合并顺序；“重排不动就指向 RNG”不是排除其他机制的实验。它的后续结果须写明实际控制变量，不能把候选二分法当因果证明。

### 处置（2026-10-10，用户拍板）：按“降级判据”收束，不重审

- 本审核的退回结论保留。用户随后对“缺口只有用户能解”的那一半直接裁决：走降级判据路线 ——
  ① 的 `±0.02` 判据作废、改为“跨协议读数只作测量差异诊断”，本项以**变更后的范围**关闭为
  `work/closed/2026/runtime-acceptance-v3.md`（`status: done`，`outcome` 记这次范围变更）。
- 故上节末条“须再次 `pending_review`”由本次拍板取代：① 不再作为容限验收重审，而是记为一次**关闭范围变更**。
  本审核 P1（把失败当通过）的判定依然成立 —— 任何时候引用本项作跨协议可比时，先读它。
- 执行记录同日新增“勘误”一节（判据作废、completion 口径、几何差异不全、首跑双 rev）。按规则，证据在审核之后
  变动通常使该事项**重新变为未审**；本次例外由上述拍板承担，且改动方向是**收窄**原判据的适用范围，
  不新增任何“已验证”的声明。

## 证据引用

- 四个完整 run 路径及启动命令：`acceptance/records/2026-10-10-cross-protocol-suite-readings.md:11-15,71-79`。本审核保留它作为执行证据，不覆盖其旧结论；后续修订须引用本审核勘误。
- 本次实际运行的复读方法如下（cwd 为仓根；本机解释器由 `ablation_harness/host_paths.py` 解析，不需要启动仿真）。

```bat
:: 核对同 ckpt、两臂重跑与全部未改列超差；另打印 revision 冲突
python -c "import pathlib,json;from ablation_harness import record;p=sorted(pathlib.Path('ablation_harness/results').glob('locomotion_eval_v*/runtime-acceptance/*/record.json'));r=[json.loads(x.read_text()) for x in p];e=[json.loads(x.with_name('eval.json').read_text()) for x in p];g=[json.loads((x.parent/'terrain/geometry.json').read_text()) for x in p];assert len(p)==4;assert all(record.read_state(x)['state']=='complete' for x in r);assert len({x['checkpoint']['sha256'] for x in r})==1;assert record.file_sha256(r[0]['checkpoint']['path'])==r[0]['checkpoint']['sha256'];assert all({k:v for k,v in e[i].items() if k!='timestamp'}=={k:v for k,v in e[j].items() if k!='timestamp'} and g[i]==g[j] for i,j in [(0,1),(2,3)]);same=[a['sub_terrain'] for a,b in zip(g[0]['cells'],g[2]['cells']) if a==b];assert len(same)==7;print('delta failures',[(n,k,e[2]['terrains'][n][k]-e[0]['terrains'][n][k]) for n in same for k in e[0]['terrains'][n] if abs(e[2]['terrains'][n][k]-e[0]['terrains'][n][k])>0.02]);print('revision conflicts',[(x.parent.name,a['runtime']['git_rev_lizard'],b['git_rev_lizard']) for x,a,b in zip(p,r,e) if a['runtime']['git_rev_lizard']!=b['git_rev_lizard']])"

:: 重建全部归档；用 evidence 投影，不能直接拿内部 probe 结构与归档比
E:\IsaacLab\env_isaaclab\Scripts\python.exe -c "import pathlib,json;from ablation_harness import suites;from rl_exp.tasks.terrain_geometry import seed_rngs,evidence;from rl_exp.tools.verify import terrain_split_probe;p=sorted(pathlib.Path('ablation_harness/results').glob('locomotion_eval_v*/runtime-acceptance/*/terrain/geometry.json'));assert len(p)==4;exec('for x in p:\n a=json.loads(x.read_text());i=a[\"identity\"];seed_rngs(i[\"seed\"]);b=evidence(terrain_split_probe.generate_record(getattr(suites,i[\"suite\"])().terrain_generator),identity=i);assert a==b,str(x);print(\"REGENERATED_EVIDENCE_EQUAL\",str(x))')"

git diff 0f4b2bf5317a e4d1ac7d0a04 -- ablation_harness/eval.py ablation_harness/metrics.py ablation_harness/suites.py rl_exp/tasks/terrain_geometry.py rl_exp/tasks/lizard2_recipe.py
git show --stat e4d1ac7d0a04
```

地形核对第一次把内部 probe 的 cells 直接与归档 cells 比较，因归档投影丢弃内部字段而断言失败；诊断后改为调用现有 `evidence` 投影，四份全部相等。不是地形漂移，也未修改数据或生成器。

提交前验证：`rl_exp/tools/verify/run_offline_checks.bat` 返回 `ALL_OFFLINE_CHECKS_PASSED (37/37)`；`python rl_exp/tools/verify/check_work_docs.py` 返回 `WORK_DOCS_OK`（历史散文指针为 HINT，不是本次缺口）；`git diff --check` 与本记录五节顺序、事项状态和证据路径的断言通过。离线绿仅证明这些机器检查成立，不推翻本次人工审核退回判定。

## 未覆盖边界

- 没有新跑 policy eval；重建的是地形，不是动力学与指标。原 run 没有帧载荷，无法离线追到每 env 的 reset、first_done、末位置或 completion 样本。
- 本审核没有坐实跨列耦合机制，也没有指定 v2 或 v3 哪个数“正确”；该缺口正是①不得宣称通过的原因。
- 不评策略好坏、收敛、鲁棒性、其他 seed/ckpt；不推定非默认 seed 的风险已经发生在本次四臂。
- 活跃事项仅保留本记录指针与待办。修订证据后须再次 `pending_review`，由新上下文复审；本记录存在本身不是完成审核动作的机器证明。
