# lizard2 main/v3 工程落地与最小运行验证

日期：2026-10-08。决策：用户明确批准现在采用本轮候选，基于 v2 去掉四个 kfe action，foot 已去掉；保留所有可动关节、PD 与默认零目标。本轮不开训练、不冻结/tag；提交同步按仓库迭代纪律执行。

## 适用范围

本记录只验收 v3 配方接入、候选资产采用与最小运行契约；不覆盖完整步态与碰撞安全。

## 验收条件

正式 train/play 使用采用的新资产；kfe/foot 不在策略接口而保留 PD 与默认目标；其余配方沿用 v2。构建、观测、复位与离线契约检查可复读。

## 结果

### 实现与资产

- 正式任务 `Lizard2-Flat-v3` / `Lizard2-Flat-Play-v3`；配方表沿用 v2 元素，runner 继承 v2，仅改 experiment_name 为 `lizard2_v3`，预算 14000。
- action = 四腿 hip/haa/hfe 12 + spine 10 = 22；30 个可动关节、31 bodies。policy = 94（3+3+3+3+30+30+22）；obs 仍保留所有关节状态，只有历史动作项变窄。
- default_joint_pos 所有匹配模式仍为 0.0 rad；init_state/reset 写零默认姿态，动作 use_default_offset=True；8 个 kfe/foot 不在策略接口，仍由 implicit PD 保持默认零目标，非机械锁定。
- kfe PD Kp/Kd=800/40，effort_limit=180；foot=200/12、70；spine=400/20、80，均继承 v2。自碰撞继续关闭，重力开启。
- 正式 USD：`rl_exp/lizard2_candidate/lizard2_candidate.usda`，从原隔离产物 `rl_exp/assets/lizard2_candidate/lizard2_candidate.usda` 逐字节复制；同目录 source URDF 与 meshes 原样采用，无手算骨架、无本轮重导出。DCC 来源 `rl_exp/blender/lizard2_stance_candidate.blend`。移除该正式树的 gitignore，保证 USD/URDF/mesh 随仓交付；原隔离转换输出继续忽略。
- family assets.json 改为 `lizard2_candidate/meshes`。dev yaml 与 v3 yaml 一致；旧 v1/v2 同次生命周期退休并删除 asset_lock，yaml、代码语义与身份保留，不刷新旧资产锁。
- 设计正文从 family PLAN 迁入 main/v3/PLAN（v3.2 用户拍板），family PLAN 收回入口；NOTES 只保留结果指针。

## 精确复读命令与结果

解释器统一 `E:\IsaacLab\env_isaaclab\Scripts\python.exe`（来自本机 paths.yaml）；以下从 `E:\Robot` 执行，无训练与策略 checkpoint。

```bat
"E:\IsaacLab\env_isaaclab\Scripts\python.exe" rl_exp\tools\pipeline\emit_diff_declaration.py --line lizard2/main --version v3 --out rl_exp\versions\lizard2\main\v3\diff.json
"E:\IsaacLab\env_isaaclab\Scripts\python.exe" rl_exp\tools\verify\check_cfg_lock.py --update --line lizard2/main --reason "v3.2 owner-approved candidate body adoption, 22 actions, unchanged PD/defaults and v2 recipe; old-body versions retired"
"E:\IsaacLab\env_isaaclab\Scripts\python.exe" rl_exp\tools\verify\check_dr_parity.py --update-locks --version lizard2/main/v3
```

生成器结果：diff 相对唯一母本 v2 仅 2 env paths（spawn、legs action）+ 1 agent leaf（experiment_name）；人工填写理由。cfg 更新输出只有 v3 train/play 两个任务新增，旧四条无字段变化；资产锁首次写 v3 一份，其它版本不写。注意 update-locks 仅首次建立可运行契约，本轮不打冻结 tag；不要重复刷新。

```bat
"E:\IsaacLab\env_isaaclab\Scripts\python.exe" rl_exp\tools\verify\obs_protocol_live.py --viz none --tasks Lizard2-Flat-v3 Lizard2-Flat-Play-v3 --pin --reason "v3 owner-approved candidate body adoption; measure actual articulation order"
"E:\IsaacLab\env_isaaclab\Scripts\python.exe" rl_exp\tools\verify\check_obs_protocol.py --live --only Lizard2-Flat-v3 Lizard2-Flat-Play-v3 --self-test
"E:\IsaacLab\env_isaaclab\Scripts\python.exe" rl_exp\tools\verify\baseline_probe.py --viz none --task Lizard2-Flat-v3 --num_envs 2 --steps 60 --random-actions
"E:\IsaacLab\env_isaaclab\Scripts\python.exe" rl_exp\tools\verify\baseline_probe.py --viz none --task Lizard2-Flat-Play-v3 --num_envs 2 --steps 60
"E:\IsaacLab\env_isaaclab\Scripts\python.exe" rl_exp\tools\verify\reset_check.py --viz none --task Lizard2-Flat-Play-v3 --num_envs 2 --subset 1
rl_exp\tools\verify\run_offline_checks.bat --jobs 4
git diff --check
```

结果：

- obs_protocol_live 正式两任务构建/reset，实际新资产 30 joints/31 bodies、22 actions、policy=94；实测序 pin 到新资产键。首次宽度显示 unapproved，随后人工登记实测批准与 dims_digest，check_obs_protocol live/self-test 全绿；URDF tree 序与 PhysX 实测序不同属正常，两者分别保留。
- train 随机动作 60 步：`BASELINE_PROBE_OK`，22/22 通道被激励；8 个未命令关节 max |target-default|=0.000e+00 rad，有限 obs，无 fall。实际 PD 参数表覆盖全部 30 关节。
- PLAY 零动作 60 步：`BASELINE_PROBE_OK`，8 个默认目标漂移仍为 0，无 fall；base z mean/min 0.9253/0.8842 m，tilt mean/max 0.41/1.08 deg。四脚平均承重 lf/rf/rl/rr=184.8/184.2/165.4/163.7 N，feet/(m*g)=0.9855；无非足承重、抽查非足网格不穿地。仅短窗静站读数，不作长期稳定/步态证明。
- PLAY reset：`RESET_CHECK_OK`；随机激励两环境后全量复位为默认位置/速度，子集复位只改变指定环境，另一环境逐位不变。
- 离线最终 `ALL_OFFLINE_CHECKS_PASSED (47/47 in 66.0s, jobs=4)`；包括版本、生命周期、资产契约/隔离/body swap、cfg golden、recipe identity/build、obs、pxr-clean。git diff --check 无空白错误。
- 独立 yaml 比对断言：仅替换 v2 robot.usd_path 与 action.joints.legs 后即与 v3 完全一致；正式 USD 与隔离候选 bytes 相等，输出 `V3_V2_RECIPE_AND_CANDIDATE_BYTES_OK`。

## 红绿与 B0 重锚

1. check_recipe_build 新版覆盖 pin 未更新时 `RECIPE_BUILD_FAILED`（6 对 expected 4、v3 未钉差异）；更新为 6 对与 v3=3 路径后 `RECIPE_BUILD_OK`。
2. 发现 obs 门硬编码 assets/ 前缀，不接受已有 resolver 支持的独立机体目录。最小修复为 repo 内真实相对 .usda 路径，并拒绝绝对路径与越界。新增 `dims/own-directory-body` / `dims/outside-tree-refused`，暂回退修复后 `OBS_PROTOCOL_GATE_FAILED (3)`、own-directory-body 红；恢复修复后全部 self-test 与 live 绿。一次初稿测试引用 `_REPO` 未定义，已纠正为既有 g._REPO 后重新执行完整红绿。
3. 首轮离线在 `[35]` 报 `GOLDEN_FROZEN_DRIFT`，11 项 fail-fast 跳过。只新增 v3 两条的 reviewed rebaseline：旧摘要 `62b51d8930146db27e776ce9e7d02c4cb62425b6cf47a362bf3f4820b0f4be6e` → 新摘要 `6369e4bedc730079933fe16d7afb66d84ef34474ff8113d72f76d4ee31e609ef`。同步 check_golden_frozen 与 lizard/ACCEPTANCE B0 指针，不读/手改 cfg_lock 原文。FROZEN_REVS 初次验证时为 `working-tree:v3.2 (commit pending)`；配方与资产已落入 `4928ced`，随后回填该提交作为黄金来源，不改黄金正文。

## 证据引用

- 用户于 2026-10-08 确认采用新骨架并落实 v3、取消四个 kfe 动作通道。
- `acceptance/records/2026-10-08-lizard2-blender-body-candidate.md`：本轮机体来源与候选测量限制。
- `rl_exp/versions/lizard2/main/v3/PLAN.md` 与 `diff.json`：配方设计及唯一差异声明。

## 未覆盖边界

- 正式最小仿真已完成，不是 stance probe 的 --drop-joints 替代；未做 GUI、长期/多 seed 稳定、完整动作周期、mesh 自碰撞验证，旧机体+selfcollision 对照仍未运行。候选旧记录 local-space BVHTree 205 pairs 无效，不引用其为碰撞证据。
- 保留 v2 的 velocity_limit 字段；框架明确告警 implicit actuator 不采用该旧字段，运行表速度上限极大。这是继承语义，不在本轮改 velocity_limit_sim，否则增加物理调参。effort_limit 同样有未来弃用告警但当前 effort 上限生效。
- 最小 sim 未设环境 seed，仅一次短窗，不能声称跨 seed 确定性。运行 stdout 由本次执行返回，本记录保留命令/判词/摘要，未另保存 raw 日志。
- 本轮工程落地定义已满足；主代理处理在办入口指针与提交归属回填/收尾，不自动冻结或启动训练。
