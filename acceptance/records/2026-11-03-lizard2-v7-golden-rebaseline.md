# lizard2 v7 golden 冻结基线复核与重锚

## 适用范围

2026-11-03，用户要求继续golden基线复核，并选择“复核并重锚”：对旧冻结基线与当前golden逐字段比较，独立审核后仅更新基线锚点与证据路由，运行仓库检查；不训练、不提交。配置、资产与原生接口的能力证据分别取圆足接入记录和接口记录，本记录只裁定本次golden变更可否合法重锚。

新上下文只读复核旧tag与当前golden；不读或展示配方锁正文，解析、字段比较复用 `check_cfg_lock.py` 的读取和差异输出。原锁和其他线未在本轮重新生成。

## 验收条件

- 旧tag解析到真实提交，旧完整文件摘要匹配原冻结锚点。
- 共同条目的完整对象、字段顺序与摘要不变；只新增授权的v7 TRAIN/PLAY，历史条目不因退休而删除。
- 两条v7相对v6.1母本的逐字段差异仅对应圆足资产、四足轴移除、双肘clip收窄及新版本/日志身份；其余参数、奖励、终止、命令、观测和PPO不变。
- 其他线golden与框架组合基线不变；原因元数据明确，不将脏树来源伪装成新提交。
- 冻结闸门摘要、来源标注与B0记录路由同步，保留字节篡改/缺失/新锁漏覆盖反证；重锚不替代构建器和真实接口检查。

## 结果

### 旧基线与当前文件

| 项 | 复核 |
|---|---|
| 旧tag | `lizard2-main-v6.1` |
| 旧提交 | `ca955e163b9f86fc5eba0a4eead9abca11d0edd1` |
| 旧锁SHA256 | `b1396611378c26e9f723fde301e38404db801692c74093fe6cac1fca2cc9172d` |
| 当前锁SHA256 | `f82affdc627aa82b1be599669a83b45837367c0121bd6d48dbd360cbbd7d6084` |
| 当前框架条目 | 12 → 14；共同12个完整对象与保留键序的序列化一致 |
| 旧框架历史条目 | 6 → 6；共同6个完整对象与保留键序的序列化一致 |
| 全文件entries | 18 → 20；新增2、修改0、删除0 |

两框架组合分别为 `isaaclab=28a37cecdd43|rsl_rl=installed:5.4.2|python=3.12.13` 与历史 `isaaclab=28a37cecdd43|rsl_rl=source:28a37cecdd43|python=3.12.13`。v4–v6虽退休，历史golden仍保留。`cfg_baselines.json` 及其他三线golden与旧tag全文件字节一致，没有框架或跨线漂移。

本轮锁外层仅原因元数据3字段变化，`lock_format` 和 `note` 不变：

- `reason` 从v6.1转向修订原因变为 `Adopt main/v7 export04 fixed round feet: 26 actions and PD axes, elbow clips +/-1, retain v6.1 elsewhere; retire palm-body v4-v6.`。
- `reason_at` 从 `2026-10-28T14:31:00+08:00` 到 `2026-11-03T10:49:05+08:00`。
- `reason_rev` 从 `35d9ca11173f` 到 `d4a06a74aec1`，是当时工具生成来源，不代表v7已提交。

### 新条目逐字段复核

只新增 `Lizard2-Flat-v7` 与 `Lizard2-Flat-Play-v7`。每条相对同模式冻结v6.1各25条snapshot差异，两条集合相同：

| 字段组 | 差异与理由 |
|---|---|
| `env.scene.robot.spawn.usd_path` | 掌足 → 当前正式圆足USD，对应已授权资产采用 |
| `init_state.joint_pos` / `joint_vel` | 各移除4个固定足端活动轴，共8字段 |
| `env.scene.robot.actuators.feet` | 移除固定足PD组，其他PD完整不变 |
| `joint_pos_legs.clip` | 移除4足轴；两前肘4端点±1.2 → ±1.0 |
| `joint_pos_legs.joint_names` | 20 → 16；额外按实际名称核只删4轴，剩余顺序不变 |
| `joint_pos_legs.scale` | 只移除4足轴scale；保留轴全量一致，双肘仍 `0.39999999999999997` |
| `env.params_version` | `v6` → `v7`，新版本身份 |
| `agent.experiment_name` | `lizard2_v6` → `lizard2_v7`，独立日志身份 |

外层版本、TRAIN/PLAY cfg类、runner类与digest按新身份变化。额外核验legs16＋spine10、躯干动作/剩余actuator/根初始位置不变、PPO除experiment名外完整不变。无其它reward、termination、commands、observation、课程或DR漂移。列表长度差异输出本身不能证明删除了正确名称，本轮已另核名称和保留顺序。

只读新上下文 `d6302633-7fca-4a90-b2dc-11dfff047ccc` 实际比较后支持限定重锚：共同18条未改、2条新增符合授权、跨线/框架字节不变。不是“重新生成能过”自证。

### 锚点与验证

本轮只更新 `check_golden_frozen.py` 中lizard2/main摘要，并在 `versions/lizard/ACCEPTANCE.md` 的B0主题加本记录路由。`FROZEN_REVS` 明确标为未提交v7候选及其短摘要，不冒充旧v6.1提交已包含新字节；将来正式提交时再绑定实际提交，不修改历史tag。

重锚前实际命令，解释器 `E:\IsaacLab\env_isaaclab\Scripts\python.exe -B`：

- `rl_exp/tools/verify/check_cfg_lock.py --line lizard2/main --diff`：exit0，`CFG_LOCK_OK`，14个当前任务。
- `rl_exp/tools/verify/check_recipe_build.py`：exit0，`RECIPE_BUILD_OK`，14任务、197声明差异。
- 原 `rl_exp/tools/verify/check_golden_frozen.py`：exit1，`GOLDEN_FROZEN_DRIFT`，只lizard2/main摘要不匹配。

重锚后同解释器实际执行：

- `rl_exp/tools/verify/check_golden_frozen.py --self-test`：exit0，`GOLDEN_FROZEN_SELFTEST_OK`，篡改、缺失与漏覆盖反证保持。
- `rl_exp/tools/verify/check_golden_frozen.py`：exit0，`GOLDEN_FROZEN_OK`，5个受控文件，lizard2来源横幅明确为未提交v7候选。
- `rl_exp/tools/verify/check_cfg_lock.py --line lizard2/main --diff`：exit0，`CFG_LOCK_OK`，14任务。
- `rl_exp/tools/verify/check_recipe_build.py`：exit0，`RECIPE_BUILD_OK`，14任务、197声明差异。

第二独立新上下文 `4ba89667-271a-4e32-8139-19b041679b22` 只读对照实际锚点、B0指针、旧tag与当前摘要，重新实跑冻结反证/闸门；确认未提交来源标注诚实、完整SHA和覆盖检查未削弱，接受限定重锚。其指出最终执行结果待回填，已在此落盘，不靠该审核自动判绿。

最终完整检查 `python -B rl_exp/tools/verify/offline_suite.py --jobs 4`：退出0，`ALL_OFFLINE_CHECKS_PASSED`，37/37通过，无失败或跳过，墙钟73.3s；wave269s只为并发成本提示，不作为静态成本判定。构建、冻结摘要、obs协议、生命周期、manifest/rebuild、suite shape及其它既有闸门均实际执行通过。

另外独立核 `check_work_docs.py` 为 `WORK_DOCS_OK`；本轮v7两task obs声明/golden/cfg比较通过，`git diff --check` 通过。收尾重新用共享哈希原语核golden仍为上表当前sha，确认本轮没有重新生成或改写配方锁字节。

## 证据引用

- 核验及摘要控制：`rl_exp/tools/verify/check_cfg_lock.py`、`rl_exp/tools/verify/check_golden_frozen.py`、`rl_exp/tools/verify/check_recipe_build.py`。
- 本次机器落点：`rl_exp/tools/verify/check_golden_frozen.py`；B0证据指针：`rl_exp/versions/lizard/ACCEPTANCE.md`；在办路由：`work/active/lizard2-family-landing.md`。
- 旧证据：`acceptance/records/2026-10-28-lizard2-v6-yaw-command.md`；旧tag及完整sha见上表。
- 授权配置差异：`rl_exp/versions/lizard2/main/v7/diff.json`、`base.json`；来源与配置：`acceptance/records/2026-11-03-lizard2-v7-round-feet.md`；运行时限定批准：`acceptance/records/2026-11-03-lizard2-v7-interface.md`。
- 复读旧锁只从 `git show lizard2-main-v6.1:rl_exp/versions/lizard2/main/cfg_lock.json` 交系统临时文件，工具 `load_entries()` 读取，与当前工具读取条目逐对象比较，字段输出复用 `_baseline_changes()` / `_print_diff()`；不输出锁正文、不在仓根留一次性脚本，TemporaryDirectory结束自动清。

## 未覆盖边界

- 重锚批准只覆盖上述golden增量，不证明站稳、承重、长期稳定或训练效果；观测/reset范围仍以接口记录为准。
- 新golden字节尚未提交，当前共享树有其它会话改动；不伪造可从某提交重建的新基线，也不绕脏树开训门。
- 不启动训练、不提交/推送、不打标签；整体验收及训练评测事项仍在办。证据或golden再次变化须重新复核。
