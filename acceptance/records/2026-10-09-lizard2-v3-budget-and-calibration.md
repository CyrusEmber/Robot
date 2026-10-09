# lizard2 v3 预算声明 6000、配方锁重锚与旧机体标定修正（2026-10-09）

## 适用范围

本轮落两项用户拍板的修正，均不碰资产内容：

1. **v3 的预算声明**：由"沿用 v2 的 14000"改为本版自己的 **6000**（§B 内容修订 v3.3）。
2. **`pose_slider.py` 的旧机体标定**：默认体高 `0.912 m` 来自上一代机体，改为采用机体的读数。

不改 URDF/USD/网格/限位/动作接口，不刷新资产锁，不训练，不冻结/tag。

## 验收条件

- 预算落在**声明**（cfg 类属性）而不是 CLI 覆盖；改动面可复读，且不是"整份重写"。
- 配方锁的更新只经过 `check_cfg_lock.py --update --line <线> --reason`，理由写明什么动了。
- 黄金锚点的重锚走**两处编辑 + 一条理由**（`check_golden_frozen.py` 的表 + 本记录），不是静默刷新；
  该文件 `FROZEN_REVS` 的提交回填按既有两步形状（先摘要、后修订名）。
- `pose_slider` 的默认体高来自**采用机体**的实测且可复读，不再引用旧机体记录。
- `diff.json` 与本版方案一致：`agent` 组叶子集合变了，逐叶子理由重写（不许留 `TODO` / `[REVIEW]`）。
- 离线全套与 pre-commit 全绿；`git diff --check` 无空白错误。

## 结果

### ① 预算声明 6000

`rl_exp/tasks/agents/rsl_rl_ppo_cfg.py` 的 `Lizard2V3PPORunnerCfg` 增加自己的 `max_iterations = 6000`
（v2 类仍 14000，v2 的声明不动），并写明这是"读新机体的短窗、不是训练候选"。

配方锁更新输出（`--update --line lizard2/main`，只读闸门输出，未读锁正文）：

```
Lizard2-Flat-Play-v3: 1 path(s) differ
  agent.max_iterations: 14000 -> 6000
Lizard2-Flat-v3: 1 path(s) differ
  agent.max_iterations: 14000 -> 6000
change: 2 task(s) changed: ['Lizard2-Flat-Play-v3', 'Lizard2-Flat-v3']
entries written: rl_exp/versions/lizard2/main/cfg_lock.json (259 KiB, 6 entries)
```

即**两个字段路径**，其余四条条目原样写回（同一 `--update` 的既有行为）。理由字段记的是
"v3 declares its own 6000-iteration budget (user call 2026-10-09): agent.max_iterations 14000 -> 6000
on the v3 train/play pair only, nothing else moved"。

`diff.json`（`emit_diff_declaration.py --line lizard2/main --version v3`）重生后：env 路径仍 2 条，
`agent` 组叶子 1 → 2。工具发现值已变，把旧理由标 `[REVIEW]` 保留——两条理由都重写：

- `experiment_name`：删掉已不真的"budget unchanged"分句（v2 预算确实不再沿用）。
- `max_iterations`：新写 6000 的理由（未训练机体 + 限位/踝向/碰撞面仍挂账 ⇒ 短窗读数）。

顺带暴露的**硬 A pin**：`check_recipe_build.py` 的 `EXPECTED_DIFFS` 里 v3 钉的是 3 条差异路径，
差异集合变 4 后该闸红（`RECIPE_BUILD_FAILED`：declared 4, expected 3）。按该 pin 的既有用途（差异集合的
唯一机器读数）重钉为 4，并在注释里写明是 v3.3 的第二个 agent 叶子带来的。这一条是本轮唯一需要"重钉"的
闸门——它恰好证明差异集合的变化没有静默。

### ② 黄金锚点重锚（第六次，本线第二次）

`check_golden_frozen.py` 的 `FROZEN["rl_exp/versions/lizard2/main/cfg_lock.json"]`：

| | 摘要 |
|---|---|
| 旧（v3.2 采用时） | `6369e4bedc730079933fe16d7afb66d84ef34474ff8113d72f76d4ee31e609ef` |
| 新（本轮） | `90c8f5a22fd52dc6e86c8b2bd8fbedbf2ae5fab56dd6748a592eb0b97d7af80d` |

`FROZEN_REVS` 本轮先记 `working-tree:v3.3 (commit pending)`，落入提交后回填该提交作为黄金来源
（既有两步形状；回填与本次 `--update` 的字段面一致，不重打 tag）。

### ③ `pose_slider` 默认体高改到采用机体

`rl_exp/tools/diagnose/pose_slider.py`：

| | 值 | 来源 |
|---|---|---|
| 旧 | `DEFAULT_BASE_Z = 0.912` | 上一代机体的落定体高（`2026-09-22-lizard2-stride-at-load`，该表列的就是旧机体） |
| 新 | `DEFAULT_BASE_Z = 0.9253` | 采用机体的 PLAY 零动作窗口均值（`2026-10-08-lizard2-v3-landing`：60 步 / 2 envs，mean 0.9253、min 0.8842） |

这个常量决定摆姿器把机体摆多高，因此它错一代就会把**每一条离地间隙读数**都算过别的机体——这是本轮
要修的原因。注释里同时写明"0.8842 是该行里的落定暂态"，避免下次把它当第二个读数。

### ④ 闸门与复读

```bat
"E:\IsaacLab\env_isaaclab\Scripts\python.exe" rl_exp\tools\verify\check_cfg_lock.py --line lizard2/main --diff
"E:\IsaacLab\env_isaaclab\Scripts\python.exe" rl_exp\tools\verify\check_golden_frozen.py
"E:\IsaacLab\env_isaaclab\Scripts\python.exe" rl_exp\tools\verify\check_recipe_build.py
rl_exp\tools\verify\run_offline_checks.bat --jobs 4
git diff --check
```

结果：

- `check_cfg_lock --line lizard2/main --diff`：`CFG_LOCK_OK (6 tasks, 1 line(s), isaaclab=28a37cecdd43|rsl_rl=source:28a37cecdd43|python=3.12.13)`。
- `check_golden_frozen`：`GOLDEN_FROZEN_OK (5 baseline file(s) unchanged, frozen at: 020e6fb x2, 27ca424 x1, 817d64e x1, working-tree:v3.3 (commit pending) x1)`。
- 离线全套红绿：**先红**——`[41/48] hard A … FAILED → RECIPE_BUILD_FAILED`，判词
  `FAIL lizard2/main/v3: declared 4 difference path(s), expected 3`（差异集合变了、pin 未动）；重钉 pin 后
  `check_recipe_build` 单跑 `RECIPE_BUILD_OK (42 task(s) field-identical to the frozen golden; 475
  declared difference(s) against their own base)`，全套重跑 **`ALL_OFFLINE_CHECKS_PASSED (48/48 in 67.0s,
  wave 245s/informational, jobs=4)`**。
- pre-commit：pin / DR parity / version docs / work docs / obs layout 全绿；`git diff --check` 无空白错误。
## 证据引用

- 用户拍板：2026-10-09，"都修复，按照 6000 走"。
- 预算与状态的前序记录：`acceptance/records/2026-10-09-lizard2-limit-requirement-and-status-sync.md`（该记录明说预算不在其本轮改动，故本轮单独落）。
- 采用机体与体高读数：`acceptance/records/2026-10-08-lizard2-v3-landing.md`。
- 旧机体体高出处：`acceptance/records/2026-09-22-lizard2-stride-at-load.md`。
- 落点：`rl_exp/tasks/agents/rsl_rl_ppo_cfg.py`（`Lizard2V3PPORunnerCfg`）、
  `rl_exp/versions/lizard2/main/cfg_lock.json`（闸门产物）、`rl_exp/versions/lizard2/main/v3/{PLAN.md, diff.json}`、
  `rl_exp/tools/diagnose/pose_slider.py`、`rl_exp/tools/verify/check_golden_frozen.py`。
- 规则：`.codemaker/rules/versioning.mdc` §B（方案修订与 commit 绑定）与 §A（锁与资产采用）。

## 未覆盖边界

- **没有训练，也没有启动训练**：6000 只是声明；任何将来的 run 只能报告"截至 6000 步"的表现。
  启动时**不要**再传 `--max_iterations`，让声明值生效（v2 的教训就是覆盖没进 argv）。
- 采用机体仍是未训练机体：限位余量是否够（R4）、踝/掌反曲方向、完整动作周期、真实网格碰撞与
  旧机体开自碰撞控制组仍未做，归 `work/active/joint-limit-shape-and-range-pass.md`。
- `0.9253` 是 60 步短窗均值，不是专门的落定 run；换一次专门的静站 run 后应重读这个常量。
- 换默认体高会让摆姿器的读数与**旧机体高度下**的既有记录不可直接比：`acceptance/records/2026-09-29-leg-pose-slider-and-pad-clearance.md`
  的零位四腿读数是在 `base_z = 0.912 m`（旧机体）下取的，保持其历史身份不清零；要对比必须同高重取。
- 本轮改的是**声明级**预算：PPO 超参、DR、课程、命令与奖励一字未动；跨 v2/v3 比较仍受"不同机体"限制。
- 黄金锚点摘要与 `FROZEN_REVS` 的回填分两笔提交，回填笔只动物证行，不改任何被锁内容。
