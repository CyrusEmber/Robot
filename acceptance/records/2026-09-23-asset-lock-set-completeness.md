# asset lock 的集合比对补齐两个方向（第 2 步第二类，2026-09-23）

## 适用范围

- 落点：`rl_exp/tools/verify/check_dr_parity.py` —— 新增 `_left_the_tree()` 与 `_unread_locks()`、
  `check_asset_locks()` 改为双向比对 + 锁集合比对、"新增键"判词从 `? -> {sha}` 改为 `asset not in the lock`、
  新增 `_self_test_locks()` 并入 `--self-test`、docstring 第 6 条与 `--self-test` 帮助文本随之改写。
- 属 `work/active/freeze-maintenance-simplification` 第 2 步第二类：折进**已有**闸门（套件入口数不增、`MAX_CHECKS` 不动）。
- **不覆盖**：第 2 步第三类（开训前协议绑定，归 `eval-protocol-before-training`）与第四类（`binding.git_run` 编码）；
  也不覆盖"锁里的摘要值是否可信"——本类只保证**集合**不漏。

## 验收条件

1. **反证先行**：不改代码即可观测到两个静默方向 —— (a) 被锁定的资产被移出树 ⇒ 闸门仍绿；
   (b) 锁出现在没有被枚举的版本目录 ⇒ 无人过问。
2. 修后两者都必须红，且判词点名具体路径/版本。
3. 两条新比较各有一条自测用例（自测要能在实现写错时挂掉）。
4. 套件入口数与 `MAX_CHECKS` 不增。

## 结果

**先测现状**：盘上 20 份 `asset_lock.json` = 20 个被枚举的版本；三个开发目录
（`lizard/main/rough-v0`、`curriculum-flat-v0`、`curriculum-rough-v0`）**根本没有锁文件**；
逐份把锁内条目与盘上集合比对，stale 条目 **0**（20 个版本全空）。⇒ 缺口是**潜伏**的，
不能像 golden 那次靠"已有活体实例"取证，必须做受控变更。

**反证探针**（`%TEMP%` 下的临时脚本，`try/finally` 保证资产与临时锁一定还原；已删除）：

- 动作 1：`rl_exp/meshes/visual/tail3_pitch_visual.stl` 移出仓外。
- 动作 2：把 `lizard/main/v0/asset_lock.json` 复制进 `lizard/main/rough-v0/`。
- 旧实现判词：`rc = 0`、`PARITY_OK`，两个动作**都没有任何一句话**。
- 副产物：若只是把文件**改名**留在 `meshes/**` 内，闸门会红，但红的是"多了一个新键"
  （`meshes/visual/tail3_pitch_visual.stl.probe_tmp ? -> 41ab3ebd`），
  **原文件消失本身仍无人提** —— 这顺带暴露了旧判词 `recorded.get(rel, '?')[:8]` 在"新增"分支只会打印一个 `?`。

**修法（两个方向都补）**：

1. `_left_the_tree(recorded, current)` ⇒ 判词 `{vtag}: locked file left the tree: {rel} (the lock still lists it; retire the asset with a deliberate --update-locks, or put the file back)`。
2. `_unread_locks(_VERSIONS, checked)` ⇒ 判词 `{vtag}: has an asset_lock.json but no discovered version reads it -- nothing checks its contents; declare the version or drop the lock`。
3. "新增键"单独成句：`{vtag}: asset not in the lock: {rel} {sha[:8]} (refresh the lock deliberately with --update-locks)`。

**自测当场抓到实现 bug**：`_unread_locks` 的 glob 第一版写成 `*/*/asset_lock.json`（少一层，
真实布局是 `versions/<fam>/<line>/<vN>/asset_lock.json`），规则在真仓里会**静默失效**；
自测用例报 `SELFTEST: a lock no version reads was not reported: []`，修成 `*/*/*/asset_lock.json` 后转绿。
这条自测的存在理由就此被证明了一次。

**修后反证**：同一条探针 ⇒ `rc = 1`，21 条判词 —— 20 条
`locked file left the tree: meshes/visual/tail3_pitch_visual.stl`（逐版本点名）+ 1 条
`lizard\main\rough-v0: has an asset_lock.json but no discovered version reads it`；
探针收尾打印 `restored: True | stray removed: True`。

## 证据引用

```
$ python -c "... 逐份比对锁内条目 vs _asset_hashes() ..."        # 先测：stale 全为 0
lizard/baseline/v1 stale: []  ...  lizard2/main/v1 stale: []     （20 行，全空）

$ python "%TEMP%\probe_asset_lock.py"                            # 旧实现：两个动作都不报
rc = 0
  | [check] asset lock (frozen versions vs current assets)
  | PARITY_OK
restored: True | stray removed: True

$ python rl_exp\tools\verify\check_dr_parity.py --strict --self-test
DECLARE_FAMILY_SELF_TEST_OK
  SELFTEST: a lock no version reads was not reported: []         # 抓到 glob 少一层
（改成 */*/* 后）PARITY_OK

$ python "%TEMP%\probe_asset_lock.py"                            # 修后：21 条判词
  |   DRIFT: lizard\main\rough-v0: has an asset_lock.json but no discovered version reads it -- ...
  |   DRIFT: lizard\main\v14: locked file left the tree: meshes/visual/tail3_pitch_visual.stl (the lock still lists it; ...)
  | PARITY_DRIFT (21 problem(s); review whether each diff is intentional; allowlists in this script)
restored: True | stray removed: True

$ rl_exp\tools\verify\run_offline_checks.bat
[2/47] freeze contracts (...) ... ok (2.5s) -> PARITY_OK
ALL_OFFLINE_CHECKS_PASSED (47/47 in 54.3s, wave 279s/informational, jobs=6)
```

提交面：`git status --short` 只列 `M rl_exp/tools/verify/check_dr_parity.py`（探针与临时锁均已清除）。

## 未覆盖边界

- 第 2 步第三类（开训前协议绑定）与第四类（`binding.git_run` 编码）未做。
- 本类只保证**集合**不漏，不保证锁里摘要值的来源可信；`--update-locks` 仍是**写自己的答案**的那条路径
  （它的合法性依赖"同变更内人工审 + `--reason`/记录"，不在本次范围）。
- 三个开发目录「该不该有锁」仍未决：现行规则只是"**有**锁就必须被读"，不是"必须有锁"。
  该不该给它们立目录级规则，按第 4 步"能抓什么具体错误"判，不在本次预设。
- `_lock_files` 对 `meshes/**` **不做扩展名过滤**：往里落一个非资产文件（临时文件、编辑器备份）会被算成"新增键"并判红。
  本次未改 —— 它算出的确实是真事实（树变了），且放宽过滤会削弱"mesh-only 重建必须出声"这条原始意图。
- 未在其他 checkout（CRLF/LF 差异）上验证；探针只覆盖了一个资产文件与一个开发目录。
