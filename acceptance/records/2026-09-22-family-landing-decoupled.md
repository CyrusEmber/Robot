# 2026-09-22 家族落成与任何历史家族解耦

## 适用范围

- 工具/契约：`rl_exp/tools/pipeline/declare_family.py`、`rl_exp/tools/verify/check_dr_parity.py`、
  `rl_exp/tools/verify/recipe_lines.py`、新增 `rl_exp/versions/freeze_parity.json`、
  新增反证 `rl_exp/tools/verify/test_declare_family.py`（挂进 `offline_suite.py`）、
  `versions/lizard2/main/{main_params.yaml,v1/main_params.yaml}`（删掉没人读的块）。
- 覆盖：新家族落成工具对"另一个家族"的三种实质耦合（参照家族前置依赖、保护对象写死、通用闸门夹带旧配方假设）
  及其验收；`limb_body_names` 那条强制义务随之取消。
- 不覆盖：训练、旧家族的资产/锁内容、`EXPECTED_DIFFS` 与 obs 声明两级红（既定待办，见 `lizard2-family-landing`）。

## 验收条件

1. 无需提供旧家族参照即可创建新家族。
2. 工具中没有历史家族特判。
3. 只写目标家族及明确的公共注册入口。
4. 其他家族内容不变。
5. 任一步失败都返回失败。

## 结果

| 耦合（评审所指） | 处理 | 反证断言 |
|---|---|---|
| 参照家族是前置依赖（`--reference-family/--reference-line`、读旧 `diff.json`、要求参照是血统根） | 整条删除（参数、`Target.ref_*`、`reference_diff()`、两处参照检查）；wiring 类由**类自己声明的 `params_line`**定位，stock 父类由**该模块自己的 `isaaclab_tasks` import**解析 | `one-family-tree/declares`、`/no-reference-flag`、`/stock-parent` |
| 零漂移保护写死 `lizard` | 保护集 = **目标家族之外的全部家族**，逐字节比对写前/写后；资产锁更新加 `--family`（结构上够不到别家）；按 stdout 解析 `versions/lizard/` 的旧实现（恒 `0 checked`）删除 | `guard/scope-is-every-other-family`、`apply/wrote-only-target-family`、空集判红 |
| 通用闸门夹带旧家族配方假设（被迫填没人读的 `limb_body_names`） | 资产契约只查 yaml **自己声明**的键（`_declared_block_lists`）；覆盖范围由"线名是 `main`"改为**声明状态 `active`**；对拍对象搬进 `versions/freeze_parity.json`（含每条已审差异的理由）；`is_main_line` 由此成死接口并删除 | `subjects/empty-declaration-refuses`、`/missing-files-refuse`、`/repo-declares-one`、`contract/no-limb-key-required` |

- 反证脚本 **18 项全过**，末尾 `DECLARE_FAMILY_SELF_TEST_OK`。
- 契约闸门：`PARITY_OK`；对拍 `lizard/main`（family 20 行 / teacher 20 行 / 已审 21 条）；
  资产契约 `yamls checked: 22`（22 声明资产，0 不声明；`lizard/parkour` 因 retired 不计）。
- 锁隔离：`check_dr_parity.py --update-locks --family lizard2` 打印
  `scope: lizard2 only -- 19 other version(s) not read, not written`，同一命令内 `lizard` 19 个锁 sha256 前后一致（`CHANGED: []`）。
- 删块的影响：`check_cfg_lock --update --line lizard2/main` 报 **`change: no content change`** ⇒ 对建出的 cfg 行为零影响；
  随后 `--update-locks --family lizard2` 重钉该版本锁。
- 离线套件 **47 → 48 项**，实测 `48 check(s): 2 failed, 4 skipped`（**46 绿**）；两级红为 `EXPECTED_DIFFS` 未钉与 obs 声明缺两个 task id，与本轮无关。

## 证据引用

- 复读命令：`test_declare_family.py`；`check_dr_parity.py --strict`；`run_offline_checks.bat`。
- 落点：`work/active/lizard2-family-landing.md`（本项 `next` ①②③④）；
  `rl_exp/versions/freeze_parity.json`；`FILEMAP.md` 的"机器件"一条。

## 未覆盖边界

- `--root`（拷贝树）下三个生成器仍跳过（它们按自身文件位置解析真仓注册表）；emit 原先不检查 rc，本轮改为**也跳过**而非静默失败。
- `emit_diff_declaration.wiring_class` 仍按 `<family>_env_cfg.py` 命名约定定位模块：是约定不是历史家族特判，但家族模块改名会拒。
- `freeze_parity.json` 的已审差异是**搬运**（与旧 `ALLOWLIST` 逐条一致），未逐条复核理由是否仍成立；两侧都不再出现的豁免不作声。
- `experiment_name` / `max_iterations` 的检查是"派生声明里有没有该叶子"，不是"与 runner cfg 取值一致"（声明本就由 runner cfg 推导，无法自证）。
- `declare_agent_leaves` 会改写这两个叶子的 `why`（值 + TODO），`diff.json` 其余 64+41 条 why 仍是 TODO。
