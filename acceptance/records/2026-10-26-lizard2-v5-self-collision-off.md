# lizard2 v5.2：关闭全部物理自碰撞

## 适用范围

用户于 2026-10-26 最终决定“先把自碰撞全关了”，覆盖此前讨论的同腿内部过滤方案。修改对象为已解冻且未训练的 v5；关闭开关时保持提案态，后续用户明确要求的重新冻结见结果节。本轮不启动训练。v4 配方、共享开发态参数及 USD/URDF/网格不变。

## 验收条件

- v5 TRAIN/PLAY 解析到 `enabled_self_collisions=False`；v4 继续为 True，其余机器人字段一致。
- 正式 PhysX 环境中的 articulation 开关读回与 YAML 一致；地面接触和头部持续触地终止仍能运行。
- 本轮相对 v5.1 只改变自碰撞开关；保留已关闭的腿部接触惩罚、其余奖励及终止语义。

## 结果

`robot.self_collisions` 从 True 改为 False，复用既有 `lizard2_palm_interface` 写入正式 spawn 配置。未新增碰撞对过滤器，也未关闭地面碰撞。参数仅在 v5 变动；原版本 YAML、资产文件及摘要均不变，v5 资产锁只重新绑定本轮 YAML 摘要。

回归 `test_v5_disables_self_collisions_without_changing_v4` 修改前实际失败，报 `Lizard2-Flat-v5` 仍启用自碰撞；修改后 TRAIN/PLAY 均通过，且与 v4 的机器人字段差异严格只有该开关。本次完整 v5 九项测试通过。

配方更新工具逐字段只报告两个 v5 任务的 `env.scene.robot.spawn.articulation_props.enabled_self_collisions: true -> false`，逐条比较锁条目也仅这两个任务变化。相对母本 v4 的差异声明新增 spawn 路径并补写用户决策理由。

### 原生运行

`rl_exp/out/lizard2_v5_self_collision_off01/report.json` 的 completed、closed 均为 True。正式四环境完成 100 控制步、400 物理步；常规零动作段 reset 为零，有限值、驱动读回、零速度参考及自由根检查通过。

实际场景中 `/World/envs/env_0..3/Robot/Geometry` 四个 articulation 的 `physxArticulation:enabledSelfCollisions` 均读回 False。预检工具新增该读取与配置核对，不将 YAML 声明单独当作运行时证据。

原头地验证夹具在本配置下通过：真实头部→地面滤波力能够进入传感器，连续接触满足既有时间边界后触发终止；短接触、物理子步间断与 reset 检查继续成立。强制触地夹具只验证通道与终止，不能解释为策略载荷或步态能力。

### 后续冻结决定

用户随后明确要求由执行者冻结当前修订。本地工作树无未提交配置改动，`self_collisions=False`、`undesired_contacts=0.0`。同步当前状态文档后创建本地 `lizard2-main-v5` 标签，绑定包含当前配置的整树提交。先前撤销的旧标签曾指向 `8f9ce3a`；本次是未训练版本在解冻修改后的重新冻结，不改写提交历史。遵照用户此前“不用检验”的指示，不再追加检验或启动训练；远端同步仍待之前的推送授权。

## 证据引用

- 配置：`rl_exp/versions/lizard2/main/v5/main_params.yaml`；构建：`rl_exp/tasks/lizard2_recipe.py`；回归：`rl_exp/tools/verify/test_lizard2_v5.py`。
- 原生入口：`rl_exp/tools/diagnose/palm_preflight.py`；本机输出目录 `rl_exp/out/lizard2_v5_self_collision_off01/`，日志 `rl_exp/out/lizard2_v5_self_collision_off01.log`，目录保存预检源文件及相关源码快照。
- `report.json` SHA256：`1b2fc0ab282c728aaee38aa666eefc9efdebb1cc7ba1d479e32f0d7d7c46a187`。
- 前序修订与假设：`2026-10-26-lizard2-v5-leg-contact-penalty.md`、`2026-10-26-lizard2-v4-self-collision-hypothesis.md`，均按各自当时配置解释。

从仓根复读；原生输出须选择新目录：

```powershell
E:\IsaacLab\env_isaaclab\Scripts\python.exe rl_exp/tools/verify/test_lizard2_v5.py
E:\IsaacLab\env_isaaclab\Scripts\python.exe rl_exp/tools/diagnose/palm_preflight.py --task Lizard2-Flat-v5 --out rl_exp/out/<新目录> --num_envs 4 --steps 100 --head_ground_check --viz none
E:\IsaacLab\env_isaaclab\Scripts\python.exe rl_exp/tools/verify/offline_suite.py
```

## 未覆盖边界

未训练或评测新策略，不据本轮开关、有限时长预检或头地测量宣称低头/不稳已解决，亦不据此确认 v4 失败的自碰撞归因。未逐对构造全机自撞场景或测试全部姿态；全局关闭允许机体部件互相穿插，后续策略评测需要观察实际影响。训练与策略评测仍归原活跃事项，本记录不代表独立审核或关闭。
