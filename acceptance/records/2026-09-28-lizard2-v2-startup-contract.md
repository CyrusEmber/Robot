# lizard2 v2 启动契约取证（两个新任务 id）

## 适用范围

`Lizard2-Flat-v2` 与 `Lizard2-Flat-Play-v2` 在 v2 冻结参数（`versions/lizard2/main/v2/main_params.yaml`）上的
**启动契约**：观测宽度、动作接口、未被命令关节的行为、终止集合、以及建成环境里逐组生效的执行器参数。

不覆盖：训练与评测（v2 尚无 run/checkpoint）；部署端（UE 侧是否接受动作维度变化不在仓内）；任何步态结论。

## 验收条件

1. 随机激励其余动作时，四个脚板关节的**目标角恒等默认平放位**（不是"看起来没动"）。
2. 建成环境里逐组**实读**增益/阻尼/限幅，且不是从 yaml 抄来的。
3. 动作映射无遗漏、无重复，维度等于 yaml 声明集；reset 后关节参考正确。
4. 实测新观测宽度，且与批准锚一致。
5. v1 的旧断言必须仍然成立 —— 否则读到的是"改了断言"，不是"改了配方"。

## 结果

| 项 | v2 | v1（对照） |
|---|---|---|
| `policy` 观测宽度（实测） | **98** | 102 |
| 动作维度 / yaml 声明集 / 通道数 | 26 / 26 / 26，无重复 | 30 / 30 / 30 |
| 未被命令的关节 | 四个 `*_foot_joint` | 无 |
| 随机激励下 `max |target − default|`（未命令关节） | **0.000e+00 rad**（40 步） | 不适用（该检查不介入） |
| 终止集合 | `{base_contact, head_contact}` + `time_out` = 声明集合 | 同 |
| 探针结论 | `BASELINE_PROBE_OK`（训练 id 与 Play id 各一次） | `BASELINE_PROBE_OK` |

建成环境里读到（不是 yaml）：`legs` **16 关节** kp 800 / kd 40 / effort 180；`feet` **4 关节** kp 200 /
kd 12 / **effort 70**；`spine` 10 关节 kp 400 / kd 20 / effort 80 —— 脚板组与 v1 逐字相同（差异声明里
对母本只有一条 env 路径，见 `versions/lizard2/main/v2/diff.json`），"固定平放参考的 PD"因此是实测生效的
（`velocity_limit_sim=None`，与 v1 同：cfg 的 velocity_limit 被本 fork 丢弃）。

**宽度这条曾经会红**：v1/v2 共用同一协议与同一资产，而动作接口不同 ⇒ 批准锚按资产记宽度的老结构无法同时
容纳 102 与 98。现按 `dims_by_task` 任务层批准（`versions/obs_protocol_anchors.json` 的 `a25a8c39001b`），
落地改动见那次提交；`obs_protocol_live.py` 对两个 v2 任务报 `OBS_PROTOCOL_LIVE_OK`。

## 证据引用

- 启动契约：`rl_exp/tools/verify/baseline_probe.py --task <id> --random-actions --steps 40`
  （v2 训练 id、v2 Play id、v1 各一次；输出里 `actions/declared-joints-channelled`、
  `actions/no-undeclared-joint-channelled`、`actions/dim-matches-declared`、
  `actions/uncommanded-hold-default-target` 四条即为上表）。
- 生效执行器参数：`rl_exp/tools/verify/check_actuator_budget.py --task Lizard2-Flat-v2 --freqs 0.5
  --unloaded-s 0.2 --loaded-s 0.2`（只取建成环境的限幅表，不取响应曲线）。
- 宽度实测与批准：`rl_exp/tools/verify/obs_protocol_live.py --viz none --tasks Lizard2-Flat-v2
  Lizard2-Flat-Play-v2`（`OBS_PROTOCOL_LIVE_OK`）+ `versions/obs_protocol_anchors.json`。
- 差异声明（"其余逐字沿用 v1"的依据）：`versions/lizard2/main/v2/diff.json` 与
  `rl_exp/tools/verify/check_recipe_build.py`（`RECIPE_BUILD_OK`）。

## 未覆盖边界

1. **交付力矩读不到**：implicit 驱动的 `applied_torque` 结构性为零，所以第 2 条给的是"交给求解器的限幅"，
   交付力矩只能由重构 + `clamp` 给**上界**（口径见 `2026-09-23-lizard2-v1-gait-skate.md` 的 ⑫/⑭）。
2. 探针用的是随机激励、没有策略 ⇒ 它证接口与执行器的形状，**不证任何步态行为**；"脚板被钉住会让 v1 的
   策略 1–3 秒倒地"那条接口先验属 gait-skate 记录的 ⑭，不是本记录。
3. reset 参考检查在探针内（`reset/…` 那组）随同一次运行通过；但"参考正确"只覆盖 **reset 时刻**，
   不覆盖长期漂移。
4. v2 未训练、未冻结 tag ⇒ 本记录不锚任何 run；`asset_lock` 与配方锁的刷新各有其记录（重基线见
   `2026-09-28-lizard2-v2-cfg-lock-rebaseline.md`）。
