# 膝肘对称 PD 候选统一取值

## 适用范围

2026-10-21 用户要求两侧膝和肘按相似对称结构统一 Kp=220，随后明确本轮没有必要复测。执行者据此只调整隔离诊断候选参数，不启动原拟八例物理复测、不创建子 agent。此决定接续[左后膝校准记录](2026-10-21-lizard2-left-knee-absolute-pd.md)，不改写历史测量。

## 验收条件

四个膝肘候选 Kp 均为 220 N·m/rad；Kd 按各自原值乘 sqrt(220/原 Kp)，保留名义阻尼比。左后膝已是 220，因此只实际提高右后膝和两个前肘。其余 26 轴增益、全部力矩上限、资产、armature、求解器及正式训练配方保持不变。仅核对参数、源文件和提交所需离线闸门，不以声明一致证明新增三轴精度或动力学通过。

## 结果

| 关节 | Kp N·m/rad | Kd N·m·s/rad |
|---|---:|---:|
| `rl_knee_joint` | 220 | 14.9500767900415 |
| `rr_knee_joint` | 220 | 14.9500934553255 |
| `lf_elbow_joint` | 220 | 14.9500680188319 |
| `rf_elbow_joint` | 220 | 14.9500706501953 |

候选已落在 `_self_weight_symmetric_knee_elbow_design` 并接入 `--symmetric_knee_elbow_pd`。该开关作为原 `--left_knee_absolute_trial` 的参数覆盖层，保留原输入校验链、两个左膝工况及误差口径；本轮没有增加或执行四肢测试机制。未来若用原入口采样，它只检查原有左膝工况，不能当作四个膝肘全部验证。新输出另用 `symmetric_pd_left_knee_trial_*` 状态，记录实际参数变更及 `prior_left_knee_verification_transferred=false`，不冒充原左膝历史报告。

本机完整参数快照状态 `candidate_selected_not_physically_retested`，`physical_runs_started=0`。源码参数核对确认四个 Kp、配套 Kd、原设计无原地修改、其余设置相同及重复应用不继续放大；原跟踪离线自检通过。仓库离线套件 `ALL_OFFLINE_CHECKS_PASSED (37/37 in 47.3s)`；先前本地核对脚本使用自行散列文件被一致性闸门拒绝，改为复用公共 binding 后全套通过。未新增回归测试或闸门。

判定：按用户决定选定四膝肘统一刚度候选；新增三轴未物理复测，尚无其精度、稳定性或真实驱动力矩余量结论。原左膝测量继续只属于其原参数组合，不自动迁移至本轮四轴同时提高后的设置。下一步核真实力矩读数与有效边界，仍由既有 B/C/D 事项承接。

## 证据引用

- 源码提交 `6e685b1e99434797a78fc7c61a226e549cb7aeed`，候选源码 SHA256 `724bc0a6d7c43979e48fa70b186e703ea7db69f8f94d64e1f08598cd1c75520e`。使用独立索引只提交本轮增量，未夹带共享文件其它在办内容。
- 前序左膝 report SHA256 `361fb3816cc0c3ef28995c3343926fea934d25447ee3c0b3cfc5d4b2ec11668b`；历史物理数据和 source.py 未覆盖。
- `rl_exp/out/lizard2_symmetric_knee_elbow_pd_20261021.json` SHA256 `0c83f23b57fa021ca118ae132b3f004a6f3433cbe68d180ddffc5318e0195e8b`。
- `rl_exp/out/lizard2_symmetric_pd_parameters_20261021.log` SHA256 `551d65e4abbd445a8ca586e25f50090201aab20a0c7e7c08c5c25fd749b8d9fb`。
- `rl_exp/out/lizard2_symmetric_pd_offline_20261021.log` SHA256 `c1366439493205bdfcae333207834bf478138eb387131c8a5b31f7c9d8c872ef`。
- 本机参数复读入口 `rl_exp/out/check_symmetric_pd_20261021.py`；快照含完整 design 和实际变更三轴清单。本机工件引用不承诺入仓。
- 参数使用入口为左膝记录的原命令追加 `--symmetric_knee_elbow_pd`；默认不加该开关仍可复现原左膝候选。本轮未执行该物理命令，也不以离线自检代替它。

## 未覆盖边界

未复测右膝或两肘，未复测调整其它三轴后对左膝的耦合影响；不新增全程 0.002 rad、其它姿态、自由根/承地、额外载荷或硬件保证。实际力矩、饱和与速度读数偏置仍待核验；不提高力矩上限，不修改正式训练默认值，不关闭既有事项，不声称完成新上下文独立审核。
