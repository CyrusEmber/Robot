# lizard2 main/v7 固定圆足接入记录

## 适用范围

2026-11-03，用户要求“新建v7”，并选择正式接入：当前圆足资产与26维动作、同步退休旧机体 v4–v6，完成配置检查，不启动训练、不提交。母本是 `rl_exp/versions/lizard2/main/v6/` 当前 v6.1 配方。记录为最初接入阶段执行者交付，不是独立审核通过记录；其“未测/None”描述按当时阶段解释，后续接口测量与限定批准唯一归 [接口实测记录](2026-11-03-lizard2-v7-interface.md)，不改写本记录原失败事实。

## 验收条件

- 正式 USD/URDF/网格与 export04 有效制品逐字节一致，完整引用可解析；原始未修正 USD 与历史现场保留。
- TRAIN/PLAY 的活动轴、动作、初始状态与驱动一致；固定足无活动动作，双肘目标限位与新机体一致，其余母本参数不漂移。
- 注册、配方声明、差异、golden、资产锁与旧机体退休路由一致；不通过手改 golden 或猜测实测关节序绕过闸门。
- 区分离线配置与运行时验证；缺实际关节序、观测宽度或动作/reset 证据时不宣称可开训。

## 结果

### 资产与配置

正式目录 `rl_exp/lizard2_round_feet/` 包含 USD、URDF 与28个实际引用网格，合计30个文件；复制自 export04 并逐文件比较原字节，未重转、未修改几何、惯量或旧正式掌足。USD静态依赖检查仅自身使用层与匿名 session，无外部资产引用；URDF相对网格完整。

| 项 | 本轮核对 |
|---|---|
| 正式 URDF SHA256 | `dbc00660b5c8feac84099fee65b44fe7a867f12a67f7ab437347ca7d82460a13` |
| 正式 USD SHA256 | `134bf043d42c3600dcb4369ef2c5642c49f1f68b650991702f833c6bca8eb6e4` |
| URDF / USD 静态结构 | 31 links / bodies；26活动轴、4固定足连接 |
| 动作 | 腿16 + 躯干10；从母本移除4个腕踝活动轴及 feet actuator |
| 双肘 | 物理限位及动作 clip ±1.0 rad；动作 scale 保留母本 `0.39999999999999997`，未重标定 |
| 球足 | 半径0.08 m，每足1.0861 kg，COM球心、实心球惯量；仍为诊断设计假设，不是实物材料批准 |
| 默认根高度 | 0.6038 m；export04 零位最低球底相对根为 -0.6037631034851074 m，对应理论间隙0.0000368965148926 m；非受载测量 |
| 其他参数 | v6.1 PD、奖励、终止、命令、无课程/无DR与PPO不变，经完整对象差异白名单核对 |
| 身份 | `Lizard2-Flat-v7` / `Lizard2-Flat-Play-v7`，runner `Lizard2V7PPORunnerCfg`，日志 `lizard2_v7`，母本句柄 `v6` |

四个足端 body 仍为 `lf_wrist/rf_wrist/rl_ankle/rr_ankle`，连接改为 `_fixed`，不进入动作或初始活动关节状态。`palm_spatial`角色读取器新增固定末端分支，要求具名连接、上游链与最终 cfg 状态一致，保留移动末端旧版本读取。v4–v6 已在 `lines.json` 退休并删除各自资产锁，旧参数、任务、训练记录与标签不改写；当前开发态参数与 assets 声明指向圆足。

### 实际离线检查

解释器统一为 `E:\IsaacLab\env_isaaclab\Scripts\python.exe -B`，以下命令相对仓根。前缀用该解释器替换 `python`。

- `python rl_exp/tools/verify/test_lizard2_v7.py`：修前实际失败 `gymnasium.error.VersionNotFound: Environment version `v7` for environment `Lizard2-Flat` doesn't exist.`；固定末端负例曾实际失败 `accepted mismatched fixed terminal: active_terminal`，修共享读取后通过。
- `python -m pytest -q rl_exp/tools/verify/test_lizard2_v7.py rl_exp/tools/verify/test_lizard2_v4.py rl_exp/tools/verify/test_lizard2_v5.py -p no:cacheprovider`：22 passed；覆盖母本差异、固定末端四类负例及旧版本隔离。
- `python rl_exp/tools/verify/check_cfg_lock.py --line lizard2/main --diff`：`CFG_LOCK_OK`，14 tasks。golden仅通过 `--update --line lizard2/main --reason ...` 工具生成，未读取或手改锁正文。
- `python rl_exp/tools/verify/check_recipe_registry.py`：生命周期一致。
- `python rl_exp/tools/verify/check_recipe_build.py`：`RECIPE_BUILD_OK`，14 tasks，累计197条差异。v4接触反证改读冻结v4，避免当前开发配方合法关闭该reward后破坏历史断言；原破坏测试保留。
- `python rl_exp/tools/verify/check_dr_parity.py --strict`：`PARITY_OK`。
- `python rl_exp/tools/verify/check_obs_protocol.py --live --only Lizard2-Flat-v7 Lizard2-Flat-Play-v7`：配置/golden比较完成，但缺新资产批准宽度而失败。这里 `--live` 只构造配置，不起实际环境。
- `python rl_exp/tools/verify/test_obs_protocol_gate.py`：未通过；缺新资产宽度锚点，现有“已批准多资产”反证夹具触发 `KeyError`。未放宽闸门或覆盖其他会话已修改测试。
- `git diff --check`：无空白错误。
- 第一轮 `python rl_exp/tools/verify/offline_suite.py --jobs 4`：失败1项、跳过28项；失败为本记录尚未落盘导致两项work证据指针缺失，落盘后该项通过。
- 第二轮全套揭出既有速度字段检查只识别v4–v6，v7被当成旧的无效标量限制；沿原分支加入v7并补 missing/changed/extra 反证。修前 `CONFIGCLASS_FIELDS_DRIFT (9)` / `CONFIGCLASS_FIELDS_GATE_SILENT`，修后 `CONFIGCLASS_FIELDS_OK` / `CONFIGCLASS_FIELDS_GATE_FALSIFIABLE`，未改数值或放宽断言。
- 第三轮全套揭出 manifest/rebuild 测试硬读已退休v4的生产资产锁。仅将两测试的资产输入隔离到temp合成树，仍走真实读取与哈希、锁归属检查；不恢复旧锁，不改生产验证逻辑。修前 `RUN_MANIFEST_TEST_DRIFT` 与 `assets: no lock recorded for this run`，修后单测和全套中分别 `RUN_MANIFEST_TEST_OK` / `REBUILD_GATE_TEST_OK`；资产篡改负例刷新T1后仍明确要求资产项失败。
- 最后一轮全套：37项中24项通过、1项失败、12项因fail-fast跳过，耗时32.6s。唯一已执行失败为 `check_golden_frozen.py` 的 `GOLDEN_FROZEN_DRIFT`：工具生成的线golden摘要前缀 `f82affdc627aa82b` 与已审基线 `b1396611378c26e9` 不同。新任务加入是有意变化，但仍需按该闸门要求复核逐字段差异、理由及B0基线指针；本轮没有自动更改审核锚点制造全绿。
- 主代理独立复跑上述3份pytest：22 passed；`check_version_docs.py` 为 `VERSION_DOCS_OK`，`check_work_docs.py` 为 `WORK_DOCS_OK`。v7无冻结tag警告如实保留。
- 主代理独立复跑观测检查：2个golden、2个cfg比较完成，只有新正式资产缺批准宽度这一项失败。未写观测锚点。


新增 v7 `diff.json`、cfg golden、资产锁和 obs 声明均复用既有工具生成。观测布局协议仍为 `a25a8c39001b`，没有伪造新的宽度批准或 runtime order。

## 证据引用

- 当前实现：`rl_exp/tasks/lizard2_recipe.py`、`rl_exp/tasks/agents/rsl_rl_ppo_cfg.py`、`rl_exp/tasks/__init__.py`、`rl_exp/tasks/obs_protocol.py`。
- 参数、差异与身份：`rl_exp/versions/lizard2/main/v7/`、`rl_exp/versions/lizard2/main/main_params.yaml`、`rl_exp/versions/lizard2/assets.json`、`rl_exp/versions/recipes.json`、`rl_exp/versions/lines.json`、`rl_exp/versions/obs_protocols.json`。
- 可运行回归：`rl_exp/tools/verify/test_lizard2_v7.py`、`rl_exp/tools/verify/test_lizard2_v4.py`、`rl_exp/tools/verify/test_lizard2_v5.py`及上述闸门命令。
- 本机来源：`rl_exp/out/lizard2_round_feet/export04/candidate.json`、`lizard2_round_feet.urdf`、`lizard2_round_feet/lizard2_round_feet_principal_axes_repaired.usda`、`usd_repaired_audit.json`。制品本身已晋升入正式目录；本机来源报告不承诺入库。
- 原隔离资产和接口历史：`acceptance/records/2026-10-30-lizard2-round-feet-plan-review.md`。其中 interface05 绑定 export03，不能当作 export04 或本轮正式资产运行时证据。

## 未覆盖边界

- `runtime_joint_order('Lizard2-Flat-v7')` 与 `recorded_dims(...)` 仍为 `None`。未起原生环境、未实测新资产关节序、非零观测、后端动作与reset/首物理步；不能宣称可开训。
- 观测宽度锚点须依据实际加载结果独立审核，不以静态计算替代。配置声明、资产哈希、离线通过均不证明受载、材料、滚动/滑移或学习性能。
- 原 `env.reset()` 后旧驱动目标残留边界仍在；本轮未修改框架，也未证明首步已覆盖全部状态。
- 两足导向承重、接触材料与子步载荷、prepare03来源哈希/视频更新等原动作留对应活跃事项，不随v7接入取消或冒称通过。
- 没有训练 run/checkpoint，没有提交、推送或冻结 tag；继承 runner 的迭代上限不是本轮训练预算批准。共享树另有其他会话未提交改动，不绕过脏树开训限制。
