# lizard2 v1 的机体归属缺口：锁已被换代改写，原 run 无资产锚（2026-09-30）

## 适用范围

`lizard2/main/v1` 的**资产锁与机体归属**，以及"能否据现有记录复原它训练时那具身体"这一问题。只记录已核实的事实与该事实的后果。

**不覆盖**：v1 的读数是否仍然可用（属评测协议侧）；v2（其 run 记录完整）；重训、重评或任何形式的恢复动作；旧资产的清理（另一次决策）。

## 验收条件

1. 每条事实可由 Git 或仓内文件复核，推断与实测分开标注。
2. 缺口不得被写成一致：不把锁刷新当修复、不把"有 tag"当可复现证明。
3. 本记录**不改动任何冻结产物**（不改锁、不改 yaml、不重锁）。

## 结果

**一、v1 的锁已被换代改写（Git 可查）**

`88f6bd9`（2026-09-28，"lizard2: fix rl foot hull in the family's own tree"）改写了 `versions/lizard2/main/v1/asset_lock.json`，42 插入 / 82 删除。两处内容变化：

| 键 | 换代前 | 换代后 |
|---|---|---|
| `assets/lizard2/lizard2.usda` | `0ae235fb…` | `ce96df09…` |
| `meshes/collision/rl_foot_collision.obj`（现 `versions/lizard2/meshes/…`） | `6712765b…` | `f3d07584…` |

（同一次提交也把锁的路径口径从"共享树"改成"家族树"，见 `2026-09-28-lizard2-foot-hull-and-asset-isolation.md`。）

**二、v1 的 run 早于该次换代**

`logs/rsl_rl/lizard2_v1/2026-09-22_19-26-50`（14000 iters / 4096 envs / seed 42），比换代早 6 天。⇒ **v1 今天的锁与当前加载的资产描述的是它从未训练过的那具身体。**

**三、该 run 本身没有资产锚**

`run_manifest.json` 的 `checks_failed`：`pre_make` 记录失败（`AttributeError: 'NoneType' object has no attribute 'strip'`），声明段整块未写，**manifest 里没有任何资产或锁字段**；`ready_to_learn` 同样失败 ⇒ manifest 未冻结，`checkpoints.json` 全部 `status: "incomplete"`。仅存的锚是 `env_constructed.env_cfg_digest` 与 `params_version: "v1"` / `seed 42`，而 cfg 里只有 usd 的**路径**、不含内容。

⇒ "该 run 用的是换代前的摘要"是**推断**（v1 锁的 usda 摘要在冻结到 `88f6bd9` 之间只被 `dfdc2ae` 动过一行、且动的是锁自身的 yaml 摘要），**不是 run 自证**。按 `versioning.mdc`：记录不完整要写明缺什么、结果凭什么锚住。

**四、同路径冲突，回滚 v1 会破坏 v2**

v1 与 v2 的锁当前钉**同一路径同一摘要**（`assets/lizard2/lizard2.usda` = `ce96df09…`）。把公共 usda 恢复成旧字节以回滚 v1，会立刻使 v2 的锁不符 ⇒ 同一路径无法同时满足两个摘要。要让两者在当前树都通过，必须给 v1 一具独立路径的机体资产（= 机体资产分层），本记录不主张这件事。

**五、处置（本次不执行）**

不重锁、不回滚、不做恢复演练；v1 保持其现有状态与读数记录，缺口即本文件。本轮的机制（资产锁只写一次、换代检查要求旧机体版本全部退休、退休即删锁并从验收中退出）自本轮起防止同类漂移再次发生；已经发生过的这一次不再修复。若将来要重跑 v1，先评估恢复成本——旧字节在 Git（`88f6bd9^`）可得，但那是一次独立决策。

**六、本记录写入时的读数**

`check_dr_parity.py --strict` 全绿（v1/v2 的活跃锁与**今天的**资产一致）、`git status rl_exp/versions` 零改动。注意这条绿的含义：它说明今天的树自洽，**不说明 v1 当时加载过什么**。

## 证据引用

- 锁的换代：`git log --numstat --format="%h %ad %s" --date=short 88f6bd9 -- rl_exp/versions/lizard2/main/v1/asset_lock.json`（42/82）；`git log -p -1 88f6bd9 -- <该锁>` 中的两行摘要对照。
- 换代的事实与后果：`acceptance/records/2026-09-28-lizard2-foot-hull-and-asset-isolation.md`（含"本轮未重训、未重评；v1 的既有 run 属平板 hull 下的读数"）。
- run 记录（机器本地、不进仓）：`E:\IsaacLab\logs\rsl_rl\lizard2_v1\2026-09-22_19-26-50\run_manifest.json`、同目录 `checkpoints.json`。
- 复读命令：
  ```
  E:\IsaacLab\env_isaaclab\Scripts\python.exe rl_exp\tools\verify\check_dr_parity.py --strict --self-test
  E:\IsaacLab\env_isaaclab\Scripts\python.exe -m rl_exp.tools.runrecord.manifest --verify E:\IsaacLab\logs\rsl_rl\lizard2_v1\2026-09-22_19-26-50
  ```

## 未覆盖边界

1. 不判定 v1 的评价读数是否仍可比（属评测协议与家族文档）。
2. 不覆盖 v2 及以后版本的 run 记录完整性。
3. 不做历史树复现，也不宣称现行 `--strict` 绿等价于"v1 可复现"。
4. 旧资产保留或清理是另一次决策；本记录不因此主张删除任何文件。
