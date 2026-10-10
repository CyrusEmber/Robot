# 记录格式真跑段：rsl_rl 身份与 num_envs 格子（2026-10-10，离线读数 + 真实记录）

## 适用范围

承载 `work/active/record-format-live-checks.md` 的 ①②。本轮**未起仿真**：读的是今日活解释器上的身份
读数、今日训练 manifest、以及仓内既有评测记录/结果目录。真跑段仍挂在该事项上（见未覆盖边界）。

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

- 记录本体：评测记录 9 份在 `ablation_harness/results/**/record.json`（进仓）；训练 manifest 在
  `E:\IsaacLab\logs\rsl_rl\lizard2_v3\<时间戳>\run_manifest.json`（机器本地，不进仓）。
- 相关的旧读数：`rl_exp/versions/lizard/ACCEPTANCE.md` §3.2、`acceptance/records/2026-09-17-lizard-eval-record-and-terrain-map.md`。

## 未覆盖边界

- **真跑段整段未做**：① 的写侧调用点（`main()` 是否把 protocol/group/base_run_id 传对、真跑落
  `substitutions` 与 `runtime.rsl_rl_id`）、② 的真跑观测，全部未做。原因（2026-10-10 用户定）：当时有训练
  在跑（`lizard2_v3/2026-10-10_10-14-50`，5.7 GB / 8 GB 显存，每 ~2 分钟落一个 ckpt），再起一个 Isaac app
  有挤 OOM 的现实风险 ⇒ 本轮先不跑，真跑挂账。**不得**据本记录称"记录格式已全部真跑"或"①② 已闭"。
- ② 的"不等格不可达"是**读代码 + 读既有记录得到的结论**，不是真跑观测；真跑也证否不了它（不可达的东西
  跑不出来）。若日后要让这一格有牙，作法是改"声明"的读取位置（`eval.py:394` 之前）或去掉这对同源字段
  ——两条都改记录语义，本项不动。
- ① 的"两侧一致"跨了两次会话：活解释器与训练 manifest 是今日（同树），评测侧的 3 份是 2026-09-20/22。
  同串只说明拼写规则没漂，不构成"今日一次真跑同时落了训练侧与评测侧"。
- 9 份记录 `complete` 是**当下仓内记录体**上的读数，不是对未来新增字段的承诺。
- 资产 fail 路径（③）不在本记录内。
