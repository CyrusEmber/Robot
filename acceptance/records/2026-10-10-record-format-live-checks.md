# 记录格式真跑段：rsl_rl 身份与 num_envs 格子（2026-10-10，离线读数 + 真实记录）

## 适用范围

承载 `work/active/record-format-live-checks.md` 的 ①②。分两段：**离线段**（当日中午，未起仿真）读的是
活解释器上的身份读数、训练 manifest、以及仓内既有评测记录/结果目录；**真跑段**（当日 15:24–15:27，
GPU 空出后真起仿真跑 base + variant 两条）。两段各自带适用范围，后段不追溯改写前段的读数。

不含：③ 资产 fail 路径（2026-10-10 用户定：拆为 `work/active/asset-fail-path-live-check.md`）；
协议版本切换的对照（归 `runtime-acceptance-v3`）。

## 验收条件

事项 `close_when` 的 ①②：

- ① 同一 run 身份按训练记录的 `mode` 重建后，两处取值一致 ⇒ 记"已核到行为"；不一致 ⇒ 记差异并指出
  是哪一侧的字段口径；
- ①（顺带）变体 run 的 `substitutions` 取值，以及 `unknown` + pre-format reason；
- ② 声明与实际分列且不相等时两列都出现 ⇒ 成立；某侧缺失 ⇒ 报记录不完整。

## 结果

### ① rsl_rl 身份：两侧按 `mode` 重建后同一字符串

| 侧 | 来源 | 原始形态 | 重建后 |
|---|---|---|---|
| 活解释器（写侧同一函数） | `provenance.rsl_rl_id()`，在 `env_isaaclab` 解释器上现读 | `mode=editable/source`、`rev=28a37cecdd43` | `source:28a37cecdd43` |
| 训练侧 | `logs/rsl_rl/lizard2_v3/2026-10-10_10-09-15`、`..._10-14-50` 的 `code.rsl_rl` | `mode=editable/source`、`rev=28a37cecdd43`（**裸 rev**） | `source:28a37cecdd43` |
| 评测侧（既有记录） | 3 份带 `runtime.rsl_rl_id` 的记录（2026-09-20 ×2、2026-09-22） | `source:28a37cecdd43` | — |

- 三处同串 ⇒ 两侧的差别只是"裸 rev + mode"与"拼好的身份"，**是拼写差，不是值差**；按
  `editable/source ⇒ source:<rev>`、`installed ⇒ installed:<version>` 重建后无差。
- 反向读：2026-09-17 那批 6 份记录**没有** `runtime.rsl_rl_id` 这个键（有意不进 `record.ALWAYS`），
  仓内 9 份记录**全部** `read_state=complete` ⇒ 新增字段没有追溯把历史读成 incomplete。

### ①（顺带）`substitutions`：同一函数在真实记录/真实目录上的取值

不是 fixture，取的是仓内真文件：

- **真替换**：base = `results/locomotion_eval_v2/v14/Lizard-Rough-v14_850rec_nominal_seed123`，
  candidate = `..._850rec_nominal_seed123_ckpt1150` ⇒ `comparison=compared`、
  `substitutions=['checkpoint']`、`unproven=[]`（P04 的换 ckpt 情形，类目去重后只报一次）。
- **pre-format reason**：base = `..._850_nominal_seed123`（**只有 `eval.json`、无 `record.json`**）
  ⇒ `comparison=unknown`，reason = "a pre-format run sits at … (results, no record): its bindings cannot
  be read"；`baseline` 记下被找的 run_id 与 `record.json` 路径；6 条绑定全为
  `candidate=<值> / baseline=null` ⇒ 缺席的基线记成"没有证据"，没有被读成"这是第一次 run"。
- 仓内这类"有结果、无记录"的目录共 **43 个**（51 个带 `eval.json` 的目录里）。

**边界**：这是读侧函数在真实数据上的取值，**不是** `eval.py` 的写侧调用点（`main()` 传
protocol/group/base_run_id 那一层）——那一层未观测。

### ② `num_envs` 的"不等格"在现行写侧不可达

- 写：`ablation_harness/eval.py:394` 把 `env_cfg.scene.num_envs` 覆盖成
  `envs_per_terrain * num_cols`（覆盖掉的正是**任务配方声明过的**那个值）。
- 读：`ablation_harness/eval.py:345-346` 分别读 `mbenv.num_envs` 与 `env_cfg.scene.num_envs`；
  `mbenv` 就是 `gym.make(args_cli.task, cfg=env_cfg)` 的 env（`eval.py:803-804`），它的 `num_envs`
  取自**同一个** cfg 对象。
- ⇒ 两列是同一对象的两次读；唯一能叉开的是"env 构造后再改 `cfg.scene.num_envs`"，现行路径没有这回事。
  仓内 9 份记录实测 72 / 72，无一例外。
- 同一段代码里另一对声明/实际（`runtime.device` / `runtime.device_declared`）在 9 份记录里也只读到
  相等 ⇒ **截至本轮，没有任何一次记录观测过"声明≠实际"这一格**。
- 结论：② 的验收句"声明与实际分列且不相等时两列都出现"在现行写侧**无法被满足**；且字段名
  `num_envs_declared` 承诺的是"声明值"，实际读到的是 harness 自己刚覆盖上去的值。

## 真跑段（2026-10-10 15:24–15:27，GPU 空出后）

两条真 run，同协议 `locomotion_eval_v3`、新 campaign 组 `livecheck`、`Lizard2-Flat-v3` / nominal /
seed 123（`--viz none`，cwd `E:\IsaacLab`）：

| # | 命令要点 | run 目录（进仓） | 落盘时刻 |
|---|---|---|---|
| 1 base | `--checkpoint …\lizard2_v3\2026-10-10_10-14-50\model_1150.pt --tag live` | `results/locomotion_eval_v3/livecheck/Lizard2-Flat-v3_live_nominal_seed123/` | `2026-10-10T15:24:01` |
| 2 variant | 同上换 `model_3000.pt` + `--variant ckpt3000` | `…/Lizard2-Flat-v3_live_nominal_seed123_ckpt3000/` | 同上批 |

### ① 写侧调用点：`main()` 把 base 找对、把 `substitutions` 与 `runtime.rsl_rl_id` 落对

- **base 找对了**：run 2 记录里 `substitutions.baseline` = `{run_id: Lizard2-Flat-v3_live_nominal_seed123,
  path: …\Lizard2-Flat-v3_live_nominal_seed123\record.json}` —— 正是 run 1 的目录，即"身份去掉 variant
  后缀"那个 run（`eval.py:867` 的 `base_run_id` 语义在真跑上成立，没被拼回最终串去猜）。
- **已证类目**：`comparison=compared`、`substitutions=['checkpoint']`、`unproven=[]`、`reason=""`。
  6 条绑定逐条读出：`checkpoint.sha256` 两侧不同（`f55014d2…` vs `f4c54b9b…`），另 5 条（`suite.digest`
  / `assets.declared_digest` / `eval_protocol.digest` / `obs_protocol.identity` / `obs_protocol.digest`）
  两侧逐字相同 ⇒ 换 ckpt 只报一次 `checkpoint`，没有把未动的绑定也读成替换。
- **两侧取值在写时冻结**：`bindings` 里同时存了 candidate 与 baseline 的**值**，不是事后重算 ——
  这正是"基线日后被 `--overwrite` 改写而旧 `substitutions` 仍指同一路径"要防的那一格。
- **无比较 = 无键**：run 1（base 自己）记录里**没有** `substitutions` 这个键；run 2 有。缺席与空集
  没被混成一回事。
- **`runtime.rsl_rl_id` 写侧落值**：两条真 run 都是 `source:28a37cecdd43`，与
  `provenance.rsl_rl_id()` 当场读数、以及训练 manifest `code.rsl_rl{mode=editable/source,
  rev=28a37cecdd43}` 按 `mode` 重建的 `source:28a37cecdd43` **四处同串**。⇒ ① 的"重建后两处取值一致"
  在**同一次真跑**上成立，不再是跨会话拼出来的（离线段那条边界到此收敛）。
- 两条真 run 的 `record.read_state` 都是 `complete`（`[EVAL] record=eval-record-1 state=complete`）。

### ② `num_envs` 两列在真跑上的读数

两条 run 都是 `num_envs=72` / `num_envs_declared=72`。**"不相等"这一格仍未观测到**，且真跑也证不了它：
两条列都追溯到 `gym.make(cfg=env_cfg)` 那**同一个** cfg 对象（离线段已给代码路径，此处真跑只是又一次
同值）。⇒ ② 的验收句只有"分列"这半在半真跑上落地，"不等时两列都出现"这半保持"结构性不可达"的结论。

### 未做与边界（真跑段）

- **pre-format 分支不构造**：`eval.json` 与 `record.json` 同进同出（`_persist` 一处落两个文件），
  真 run 产不出"有 `eval.json` 无 `record.json`"这个状态；旧目录的 task 前缀又都是退役 id（`Lizard-Rough-v14`
  等），当不上新 run 的基线。2026-10-10 用户定："既然不会出现就不用处理" ⇒ 该分支只保留离线段的
  读侧取值，**不写"已真跑"**。
- **`git_rev_lizard` 侧有位移**：两条真 run 记 `0f4b2bf5317a`，而训练 manifest 的
  `code.repository.rev` 是 `bd1ae8dd54a5`（训练时 clean）⇒ 蜥蜴仓在训练与评测之间前进了。① 的"同串"
  说的是 **rsl_rl 依赖身份**（`source:28a37cecdd43`），不是配方仓 rev；这条不构成跨 rev 结果可比。
- **这两条 run 的分数不作数**：`--variant` 真跑的目的是观测记录字段的落点，且 run 2 换了 ckpt
  （`success=0.537 fall=0.681`，`resets_in_rollout=72 early_terminations=22` 由 stdout 带出）——
  livecheck 组的数不进任何对账表。顺带：这两条是 v3 下**带 ckpt 的真 run**，`runtime-acceptance-v3`
  ③ 要的"一条有 ckpt 的 run"由此有了候选，但那件事的判据归它自己。

### 独立审核（2026-10-10，离线复核）

**判定：不通过，不关闭。** 审核实读两条真跑记录、训练 manifest、写侧采集点与身份实现，
并用 `env_isaaclab` 解释器执行离线断言；未重跑仿真。以下结论限定并勘误上文执笔结论。
用户在审核后选择退回 `in_progress`；未决定验收②的新口径。

- **已通过的复核**：两条记录 `read_state=complete`；base 没有 `substitutions` 键；variant 的存储证据
  与从这对记录重新计算的证据逐项相同，`baseline` 指向 base，仅确认 `checkpoint`，`unproven=[]`。
  训练 manifest 按已记录 `mode` 重建的字符串与两条 `runtime.rsl_rl_id` 相同。
- **[P1] 同串不等于依赖身份成立**：活解释器的 `rsl_rl` 来自
  `E:\IsaacLab\env_isaaclab\Lib\site-packages\rsl_rl\__init__.py`；distribution 是
  `rsl-rl-lib 5.4.2`，无 `direct_url.json`、未声明 editable。`provenance.rsl_rl_state()` 却返回
  `mode=editable/source`、`root=<ISAAC_ROOT>`。`rl_exp/tools/runrecord/provenance.py:194-199`
  只问包目录是否位于 Git 树内，因 venv 位于 IsaacLab 仓内而把普通安装包绑到了外围仓 rev。
  `rsl_rl_id()` 再于同文件 215 行拼出 `source:28a37cecdd43`；该 rev 不锚住包本体。
  因此撤回上文将“同串”称为已核到依赖身份行为的判定：目前仅证明两侧用了同一拼写规则。
  此外，训练 manifest 的 `code.rsl_rl.dirty=true` 与外围树差异摘要也不证明包本体逐字节相同。
- **[P2] 同次 variant 的 rev 互相冲突**：variant `record.json` 的
  `runtime.git_rev_lizard=0f4b2bf5317a`，但同目录 `eval.json` 与组 `summary.csv` 为 `ee1fc367cba8`。
  两个采集点是 `ablation_harness/eval.py:831` 与 `ablation_harness/eval.py:624`；前者在 rollout 前，
  后者在分析结果时重新读 HEAD。运行期间提交即可产生分叉，不能把后读 HEAD 当作已加载代码的身份。
  上文“两条真 run 记同一 rev”仅对 `record.json` 成立，遗漏了同次 run 的产物冲突；
  需明确这层边界，不能据记录完整或替换列表干净推导运行代码一致。
- **[P2] 验收②仍未兑现**：现行 `mbenv.num_envs` 经 `ManagerBasedEnv.num_envs` →
  `InteractiveScene.num_envs` 返回同一 scene cfg 值（宿主源码分别为
  `source/isaaclab/isaaclab/envs/manager_based_env.py:274-276`、
  `source/isaaclab/isaaclab/scene/interactive_scene.py:499-501`）。
  真跑仍只有 `72 / 72`。离线复制 variant，改 `num_envs_declared=73` 后读作 complete，
  删除该列后读作 incomplete：证明读侧保留不等列、识别缺列，**不证明写侧真跑不等格**。
  未经用户决定，不以“结构性不可达”替代既有验收条件，也不自动改 `close_when`。
- **勘误与保留边界**：variant 的落盘时间是 `2026-10-10T15:30:07`，上文真跑段的
  `15:24–15:27` 时间范围不包含它。用户此前决定不构造 pre-format 分支，本次不推翻；
  但 `_persist` 顺序写两个文件，不是跨文件事务，不能把“不做该分支”写成永远产不出缺一侧文件。

## 证据引用

- 事项：`work/active/record-format-live-checks.md`；拆出项：`work/active/asset-fail-path-live-check.md`。
- 代码：`ablation_harness/eval.py`（345-346 读两列 / 394 覆盖 / 803-804 `mbenv` 来处 /
  831-832 组装 `runtime`）、`ablation_harness/record.py`（`ALWAYS`、`read_state`、`baseline_evidence`）、
  `rl_exp/tools/runrecord/provenance.py`（`rsl_rl_state` / `rsl_rl_id`）。
- 复读命令（本机、无需仿真，按顺序）：

```
E:\IsaacLab\env_isaaclab\Scripts\python.exe -c "import sys;sys.path.insert(0,r'E:\Robot');from rl_exp.tools.runrecord import provenance;print(provenance.rsl_rl_id(), provenance.rsl_rl_state().get('mode'))"
python -c "import json,glob,os;ms=glob.glob('E:/IsaacLab/logs/rsl_rl/lizard2_v3/*/run_manifest.json');[print(os.path.basename(os.path.dirname(m)),json.load(open(m,encoding='utf-8'))['code']['rsl_rl'].get('mode'),json.load(open(m,encoding='utf-8'))['code']['rsl_rl'].get('rev')) for m in ms]"
python -c "import json,glob,sys;sys.path.insert(0,'ablation_harness');import record;ps=glob.glob('ablation_harness/results/*/*/record.json')+glob.glob('ablation_harness/results/*/*/*/record.json');[print(p,record.read_state(json.load(open(p,encoding='utf-8')))['state'],json.load(open(p,encoding='utf-8'))['runtime'].get('rsl_rl_id'),json.load(open(p,encoding='utf-8'))['runtime'].get('num_envs'),json.load(open(p,encoding='utf-8'))['runtime'].get('num_envs_declared')) for p in ps]"
python -c "import json,sys;sys.path.insert(0,'ablation_harness');import record;R='ablation_harness/results';L=lambda p: json.load(open(p,encoding='utf-8'));c=L(R+'/locomotion_eval_v2/v14/Lizard-Rough-v14_1150_nominal_seed123_ckpt1150/record.json');a=record.baseline_evidence(c,R,protocol='locomotion_eval_v2',group='v14',base_run_id='Lizard-Rough-v14_850rec_nominal_seed123');print(a['comparison'],a['substitutions']);b=record.baseline_evidence(c,R,protocol='locomotion_eval_v2',group='v14',base_run_id='Lizard-Rough-v14_850_nominal_seed123');print(b['comparison'],b['reason'])"
```

- 真跑段的复读（**起仿真**，每次一条约两分钟内；本机 GPU 需空出，cwd `E:\IsaacLab`）：

```
E:\IsaacLab\env_isaaclab\Scripts\python.exe E:\Robot\ablation_harness\eval.py --task Lizard2-Flat-v3 --checkpoint E:\IsaacLab\logs\rsl_rl\lizard2_v3\2026-10-10_10-14-50\model_1150.pt --protocol locomotion_eval_v3 --mode nominal --seed 123 --group livecheck --tag live --viz none
E:\IsaacLab\env_isaaclab\Scripts\python.exe E:\Robot\ablation_harness\eval.py --task Lizard2-Flat-v3 --checkpoint E:\IsaacLab\logs\rsl_rl\lizard2_v3\2026-10-10_10-14-50\model_3000.pt --protocol locomotion_eval_v3 --mode nominal --seed 123 --group livecheck --tag live --variant ckpt3000 --viz none
```

- 真跑段读回（无需仿真）：`python -c "import json;L=lambda p: json.load(open(p,encoding='utf-8'));R='ablation_harness/results/locomotion_eval_v3/livecheck/Lizard2-Flat-v3_live_nominal_seed123';print(sorted(L(R+'/record.json')));print(L(R+'_ckpt3000/record.json')['substitutions'])"`

- 记录本体：评测记录 11 份（含真跑段新增的 `livecheck` 2 份）在 `ablation_harness/results/**/record.json`
  （进仓）；训练 manifest 在 `E:\IsaacLab\logs\rsl_rl\lizard2_v3\<时间戳>\run_manifest.json`
  （机器本地，不进仓）。
- 独立审核的复读（无需仿真；cwd `E:\Robot`，不改记录本体）：

```bat
E:\IsaacLab\env_isaaclab\Scripts\python.exe -B -c "import pathlib,copy;from ablation_harness import record;R=pathlib.Path('ablation_harness/results/locomotion_eval_v3/livecheck');bid='Lizard2-Flat-v3_live_nominal_seed123';b=record.load(R/bid/'record.json');c=record.load(R/(bid+'_ckpt3000')/'record.json');m=record.load(r'E:\IsaacLab\logs\rsl_rl\lizard2_v3\2026-10-10_10-14-50\run_manifest.json');s=m['code']['rsl_rl'];identity=('source:'+s['rev']) if s['mode']=='editable/source' else ('installed:'+s['distribution_version']);assert record.read_state(b)['state']==record.read_state(c)['state']=='complete';assert 'substitutions' not in b;assert c['substitutions']==record.baseline_evidence(c,R.parent.parent,protocol='locomotion_eval_v3',group='livecheck',base_run_id=bid);assert b['runtime']['rsl_rl_id']==c['runtime']['rsl_rl_id']==identity;x=copy.deepcopy(c);x['runtime']['num_envs_declared']=73;assert record.read_state(x)['state']=='complete';x['runtime'].pop('num_envs_declared');assert record.read_state(x)['state']=='incomplete';print('PASS record fields, stored bindings, identity spelling, reader columns')"
E:\IsaacLab\env_isaaclab\Scripts\python.exe -B -c "import json,importlib.util,importlib.metadata;from rl_exp.tools.runrecord import provenance;d=importlib.metadata.distribution('rsl-rl-lib');u=json.loads(d.read_text('direct_url.json') or '{}');s=provenance.rsl_rl_state();print(importlib.util.find_spec('rsl_rl').origin);print(d.metadata['Name'],d.version,'editable:',u.get('dir_info',{}).get('editable',False),'direct_url_present:',bool(u));print(s.get('mode'),s.get('root'),s.get('package_dir'))"
E:\IsaacLab\env_isaaclab\Scripts\python.exe -B -c "from ablation_harness import record;R='ablation_harness/results/locomotion_eval_v3/livecheck/Lizard2-Flat-v3_live_nominal_seed123_ckpt3000/';c=record.load(R+'record.json');e=record.load(R+'eval.json');print('record/eval rev:',c['runtime']['git_rev_lizard'],e['git_rev_lizard']);print('timestamp:',c['run']['timestamp'])"
```

- 独立审核落点：`rl_exp/tools/runrecord/provenance.py:185-215`；
  `ablation_harness/eval.py:336-346`、`:394`、`:624`、`:831`、`:743-744`；variant 的
  `ablation_harness/results/locomotion_eval_v3/livecheck/Lizard2-Flat-v3_live_nominal_seed123_ckpt3000/record.json:1558-1589`
  与同目录 `eval.json:8-10`；训练 manifest `code.rsl_rl`（机器本地，上述复读命令给出路径）。
- 相关的旧读数：`rl_exp/versions/lizard/ACCEPTANCE.md` §3.2、`acceptance/records/2026-09-17-lizard-eval-record-and-terrain-map.md`。

## 未覆盖边界

- **已收**：真跑段的 ①（写侧调用点、`substitutions` 落值、`runtime.rsl_rl_id` 写侧）与 ②（两列真跑读数）
  已按上节观测，① 那条"跨两次会话"的边界随之收敛。**未见** ② 的"声明≠实际"格与 pre-format 分支
  （前者结构性不可达，后者写侧产不出 —— 2026-10-10 用户定不处理）。
- ② 的"不等格不可达"在真跑后仍是**读代码得到的结论**：真跑只能再证一次两列同值，证否不了不可达。
  若日后要让这一格有牙，作法是改"声明"的读取位置（`eval.py:394` 之前）或去掉这对同源字段
  ——两条都改记录语义，本项不动。
- ① 的"同串"只覆盖 **rsl_rl 依赖身份**。真跑段两条 run 的 `git_rev_lizard=0f4b2bf5317a` 与训练 manifest 的
  `bd1ae8dd54a5` 不同 ⇒ 配方仓 rev 在训练与评测之间前进了，本记录的任何读数都**不得**当作跨 rev 可比。
- 11 份记录 `complete` 是**当下仓内记录体**上的读数，不是对未来新增字段的承诺。
- 资产 fail 路径（③）不在本记录内（`work/active/asset-fail-path-live-check.md`）。