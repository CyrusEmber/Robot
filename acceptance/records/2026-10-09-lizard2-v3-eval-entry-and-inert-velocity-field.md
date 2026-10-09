# lizard2 v3 评测入口、锚点与"框架丢弃字段"折闸（2026-10-09）

## 适用范围

本轮交付两件，均不改判据数值、不改配方与资产、不训练、不冻结：

1. **v3 的评测入口**：新建身份副本协议 + 锚点条目 + 把同尺用例从两臂扩到三臂；
2. **"框架接受后丢弃的字段"折进已有闸**：把 `velocity_limit` 这类"声明了但不生效"的字段钉成
   可判形态（规则归机制，见 `work/active/lizard2-family-landing.md`）。

在此之前 v3 没有任何判据可跑：`baseline_eval.py:105` 拒任何 `recipe_version` 与任务
`params_version` 不符的协议，而现有 lizard2 协议只判 v1/v2。

## 验收条件

- v3 任务通过评测入口的四项检查（配方版本、地形为 plane 且无生成器、`episode_length_s`）；
- "判据同 v4"不是散文：由离线套件里一条会红的用例看守，新协议进锚点表，覆盖由目录推出而非声明；
- 新断言**折进已有闸**，条数棘轮不动；每个新分支在对应闸的 `--self-test` 里各有一条会红的反例；
- 全量离线绿。

## 结果

### ① 身份副本协议

`ablation_harness/protocols/lizard2_flat_v5.json`：`name`/`version`/`supersedes` +
`recipe: lizard2-flat-v3@1` + `recipe_version: v3` + `why_v5`（身份、"第三臂"理由、跨臂不可当同一次测量）。
`criteria` 与 `report_only` 与 v4 逐字段相同，未新增指标实现。协议号与配方号是两个命名空间：
本文件是**协议** v5，判的是**配方** v3。

### ② 锚点

`ablation_harness/protocol_anchors.json` 增一条（该文件的 `sha256` + 理由）。未锚时闸门点名文件并 rc=1，
已实测；补锚后：

```bat
python rl_exp\tools\verify\test_eval_frame_v2.py
```
```
  ok 10 protocol(s) match the bytes their approval records
  ok 10 protocol(s) anchored, 3 declared legacy, none uncovered
ALL_EVAL_FRAME_V2_TESTS_PASSED
```

### ③ 同尺用例扩到三臂

`rl_exp/tools/verify/test_baseline_contract.py:572`：集合 `{v1: v2.json, v2: v3.json}` → 增
`v3: v5.json`，并显式豁免 `report_only`（v4 起它就是"只报告不判"的升级；除此之外任何键不同即红）。
函数名保留 `..._two_...`：冻结的 v3/v4 协议正文按该名引用它，名字已改会留下解析不到的引用。

```bat
python rl_exp\tools\verify\test_baseline_contract.py
```
```
BASELINE_MDP_OK
BASELINE_CONTRACT_OK
```

### ④ 入口验证（启动契约级，非真跑）

```bat
python -c "import sys; sys.path.insert(0,'.'); import rl_exp.tasks; from rl_exp.tools.verify.baseline_runtime import resolve_task_cfg; ..."
```
```
protocol judges v3 | task resolves v3 | episode 20.0 20.0 | terrain plane | terrain_generator None
```

即 `baseline_eval.py:105-111` 的四项检查全部通过。

### ⑤ 折闸：框架丢弃的字段

`check_configclass_fields.py` 新增 `INERT_VELOCITY_LIMITS`（腿 10 / 脚 6 / 脊 4 rad/s、无
`velocity_limit_sim`、执行器仍是 implicit）与 `_check_inert_velocity_limits`；四条出路各自一条判词：
未审分组、值移动、`velocity_limit_sim` 出现（该字段**会**进驱动）、执行器不再 implicit（该字段**会**生效）。
反例在 `test_configclass_fields_gate.py` 的 `--self-test` 里四条，全部 `FIRES`。**条数棘轮 48 未动**
（折进已有进程，未新增检查）。

### ⑥ 全量离线

```bat
E:\IsaacLab\env_isaaclab\Scripts\python.exe -B rl_exp\tools\verify\offline_suite.py --python E:\IsaacLab\env_isaaclab\Scripts\python.exe --jobs 4
```
```
ALL_OFFLINE_CHECKS_PASSED (48/48 in 64.0s, wave 238s/informational, jobs=4)
```

## 证据引用

- 上面各节的复读命令与判词；`existing` 读数不复述。
- `acceptance/records/2026-10-08-lizard2-v3-landing.md`：v3 采用与"保留旧 `velocity_limit` 字段、不改
  `velocity_limit_sim`"这条偏差的原始读数。
- `acceptance/records/2026-09-29-gait-shape-in-the-eval-flow.md`：协议 v4 的同类交付先例。
- 用户 2026-10-09 拍板：结论并入现有事项，不新开事项。

## 未覆盖边界

- **没有真跑 eval**：本记录证明的是入口的四项检查通过，不是任何策略读数；协议存在不产生判决。
- **平面路径不经套件锁**：`suite_lock` 只在 `eval.py`（locomotion 路径）使用，故本协议不声明
  `suite_expected`；若这条线将来换地形套件，`start_refusal` 的 geometry 支会拒。
- **折闸不改变物理**：`velocity_limit` 仍是死字段，是否启用有效限速仍归
  `work/active/lizard2-family-landing.md`；闸只保证"它是死的"这件事会一直被显式检查。
- **同尺用例只比判据面**：`report_only` 逐臂可异（v4 起的设计），且 v3 臂的机体与动作接口都变了 ⇒
  跨臂读数不是同一次测量，可比性由记录的条件面判，不由本记录判。
