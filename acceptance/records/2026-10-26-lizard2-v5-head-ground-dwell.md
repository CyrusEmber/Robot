# lizard2 main/v5 头部持续触地终止

## 适用范围

用户于 2026-10-26 要求放宽原终止条件：只计头部接触地面，连续满 0.5 s 才终止，不计胸部或颈关节本身。原 v4 已训练，按版本规则新增 v5，不改 v4 的配方、资产、tag 或共享开发态参数。本轮不启动 v5 训练，也不热改原 run。

头部实际碰撞网格 `meshes/collision/neck_pitch_collision.obj` 挂在刚体 `neck_pitch` 下；`neck_yaw` 是无碰撞网格的枢轴，资产没有独立名为 `head` 的刚体。这里按实际头部碰撞 owner 选择，不把关节名解释为颈部触地。保留 1 N 力阈值；根部 `base_contact` 仍按旧规则即时终止。旧 `head_contact` 的胸颈瞬时净力语义原样保留在 v4。

## 验收条件

- 独立单刚体传感器只接收头部 owner→地面 collider 的滤波法向力；胸部和其它碰撞对象不参与该项，不从净力猜地面接触。
- 以每个物理子步的滤波力判断连续接触；任何一个无接触子步清零，连续达到 0.5 s 才终止。reset 只清对应环境，不能跨回合/环境累计。
- 对旧函数提供新要求下的真实失败对照；覆盖阈值、精确时间、子步间断、错绑定、子集/全部 reset 及 rollout inference_mode 后显式 reset。
- 正式原生任务能创建新传感器，真实头部触地进入滤波通道，连续真实接触在时长边界触发。其它配方字段与母本保持一致，现有闸门继续约束历史版本。

## 结果

### 实现与身份

新增 `HeadGroundContactDwell` 与 v5 元素 `lizard2_head_ground_dwell`，移除 v5 的旧 `head_contact` 实例，新增 `head_ground_contact`。传感器精确路径为 `{ENV_REGEX_NS}/Robot/Geometry/neck_pitch`，地面为 `/World/ground/terrain/GroundPlane/CollisionPlane`。读取 `force_matrix_w_history`，不读取全对象净力作为触地依据。PhysX 多环境视图按传感器返回分组路径，每组必须恰好同一地面、filter_count=1；错对象、空分组与错 body 均拒绝。

传感器每 0.005 s 更新，history=4；term 每控制步按从旧到新的顺序消费全部四个子步。连续计数达到 100 个物理样本才触发；有间断即清零，不把零散接触累加。计数缓冲保持原分配，避免 inference_mode 内重绑为 inference tensor 后，外部显式 reset 无法清理。

新任务为 `Lizard2-Flat-v5` / `Lizard2-Flat-Play-v5`，日志 `lizard2_v5`。位置动作、102 维观测、恒零速度参考、全部逐轴驱动/上限、奖励、命令、PPO、物理和根部终止继承 v4。原 `check_cfg_lock.py --diff` 仅报两个新任务缺快照；原 `--update --line lizard2/main --reason ...` 仅增加这两个任务，历史条目无漂移。`diff.json` 只有新传感器、新终止、移除旧终止与日志身份四个路径。

### 行为对照与回归

旧函数实际运行的新要求失败对照：短暂头部触地就立即终止；滤波地面力为零但净力非零时仍终止。`test_lizard2_v5.py --legacy` 预期返回 1，不把此负例当新实现失败。

新实现七项回归通过：短接触不终止、自碰撞净力排除、0.48/0.50 s 边界、一个物理子步间断清零及历史顺序、环境隔离、部分/完整 reset、阈值边界与错绑定拒绝、v5 路由及 v4 语义不变。原生接入发现 inference/reset 错误后，新增回归先在修复前实际失败，再修复并全部通过；失败日志保留。

### 原生测量

最终输出 `rl_exp/out/lizard2_v5_head_ground_native07/`，completed=true、closed=true。四环境正式 v5 完成 100 控制/400 物理步的原配置零动作预检，共 2 s，无 reset；所有常规有限值及驱动读回检查通过，实际后端 TGS、外力时序 false、自由根保持。

真实传感器缓冲注入验证中，前 24 次控制窗均不终止，第 25 次四环境同时触发；子集 reset 和中间一个离地物理样本分别清掉对应计数。零动作末窗实际头部→地面力为零。

随后独立测量夹具将根前倾并逐物理步恢复指定姿态，使实际头部碰撞网格触地。共 100 物理步/0.5 s，四环境每个样本的真实滤波力均大于接触阈值；真实 term 前 24 控制窗不终止，第 25 窗四环境全部触发。夹具中的大接触力来自主动重置接触姿态，只证明测量通道和时间边界，不是策略载荷、关节驱动力矩或力矩余量证据。

失败尝试保留：native01 缺观测路由，在 Kit 前拒绝；native02/03 暴露多环境路径分组处理错误，未执行控制步；native04 完成常规预检后暴露诊断缓冲/inference reset 问题；native05 的平移夹具没有形成可读头部触地，不作通道通过；native06 前倾夹具形成真实触地并完成短通道检查；native07 扩到完整实际持续时间后才作为最终行为证据。退出码不代替报告完成标志。

既有完整离线套件 `37/37` 通过，57.3 s；日志为 `rl_exp/out/lizard2_v5_offline_suite.log`。没有为此新增离线套件进程或放宽历史闸门；配方比较集合只增加新任务，v5 同样受逐轴实际上限检查。

代码及版本提交 `651adbc`，正常提交钩子全部通过，日志 `rl_exp/out/lizard2_v5_commit_code.log`。事项/记录格式检查通过，日志 `lizard2_v5_work_docs.log`；记录和事项指针同次文档提交，不据此宣称整体事项已经独立审核或关闭。

## 证据引用

源码：`rl_exp/tasks/lizard2_mdp.py`、`lizard2_recipe.py`；行为复读：`rl_exp/tools/verify/test_lizard2_v5.py`；原生入口：`rl_exp/tools/diagnose/palm_preflight.py --task Lizard2-Flat-v5 --out rl_exp/out/<新目录> --num_envs 4 --steps 100 --head_ground_check --viz none`。调用 `head_ground_dwell_probe.py`，不训练；报告同时保存主入口及新 term、元素、原生核验源码快照。

从仓根用项目 Python 复读：

```powershell
& E:/IsaacLab/env_isaaclab/Scripts/python.exe -B rl_exp/tools/verify/test_lizard2_v5.py
& E:/IsaacLab/env_isaaclab/Scripts/python.exe -B rl_exp/tools/verify/test_lizard2_v5.py --legacy
& E:/IsaacLab/env_isaaclab/Scripts/python.exe -B rl_exp/tools/verify/check_cfg_lock.py --diff --line lizard2/main
```

`rl_exp/out/lizard2_v5_inference_reset_before.log` 是真实修复前失败；`lizard2_v5_tests.log` 为修复后通过。`lizard2_v5_cfg_diff.log` 为更新前原工具对照。原生输出和训练目录均本机工件，不承诺随仓分发。

| 工件 | SHA256 |
|---|---|
| native07/report.json | `15fc3bfcd4617c87c29145732738eca0219885f96e05d685872b96dbd852c932` |
| v5/main_params.yaml | `357865a0e6e3ae2fc51d7b616b1d9505cef92b6866b0787807ea46b081057e9d` |
| v5/asset_lock.json | `e7236d9eeb1673c9e7a5d041f6c1f98dc7fc9296acdb1c3e5f155ebcb146b94d` |
| lizard2_mdp.py | `782f5b8fc6efb17e027892f8cbfe7d5f72d4d2c9cb7cabc2df57c0e6592f2a44` |
| head_ground_dwell_probe.py | `4ba69bbc86d356bba109edb41568fcb45bcc5d15bc6237131f770ce04ac137cc` |
| main/cfg_lock.json（只核文件摘要，正文未读取） | `b03879832e6fe950f6c44d4f52c627099e0c46221944727c8a0c8c67c5a54c5e` |

原 v4 run `E:/IsaacLab/logs/rsl_rl/lizard2_v4/2026-10-26_11-16-58/` 的外部检查点索引已登记 `model_5999.pt`，本轮未重启或更换该 run。它的训练曲线只能按 v4 原规则解释。

## 未覆盖边界

本轮未训练 v5、未评测新策略、未决定 v4 权重迁移后的训练预算；不把旧曲线当作新规则效果。原生物理仅四环境，未另做新增传感器的 4096 环境容量测试。净力排除、胸部不参与和间断/reset 分别由实际路径绑定与具名缓冲/回归验证，未声称采集了所有可能自碰撞姿态。

该规则按采样分辨率定义连续时间，不能识别两个 0.005 s 样本之间未观测到的瞬间离地；1 N 保留旧接触阈值，不宣称已做全工况抗噪标定。允许头部在持续时间内擦地是用户指定的新口径，不等于策略已经避免头部承重。整体训练和策略评测仍在原事项，不关闭或取消未完动作。
