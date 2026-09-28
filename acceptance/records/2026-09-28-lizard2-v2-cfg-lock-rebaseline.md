# lizard2/main 配方锁重基线（第五次，该线第一次）

## 适用范围

`rl_exp/versions/lizard2/main/cfg_lock.json` —— 被 `check_golden_frozen.py` 按摘要冻结的"stage B 验收基线"
之一。v2 给同一条线加了两个任务 id（`Lizard2-Flat-v2` / `Lizard2-Flat-Play-v2`），锁的字节因此移动；
本记录就是那一次**有意重基线**的账（该闸门自己的要求：改摘要表 + 一条 acceptance record）。

不覆盖：`asset_lock.json` 那套（v2 的资产锁刷新是另一件事，按 `--update-locks` 走、与本记录无关）；
不覆盖 v2 的运行时行为（归启动契约探针与训练）。

## 验收条件

1. 新字节相对旧字节必须只是**追加**：新增两条任务条目 + 锁自身的 `reason`/`reason_at`/`reason_rev` 三行，
   不得有任何已有条目被改写或消失。
2. `cfg_lock --update` 必须只报新增（它是"只重写真正变了的"）。
3. **两步形状**：新字节先落在一个提交里，摘要表随后引用**那一笔**的 rev，而不是引用一个还没写的提交。
4. 摘要表与 `FROZEN_REVS` 同时改，改完 `check_golden_frozen` 必须绿。

## 结果

- 摘要：`0d67afd05d66061b…` → **`62b51d8930146db2…`**；新字节落在 **`e59e240`**（"Register lizard2 v2"），
  `FROZEN_REVS` 引的就是这一笔。
- `cfg_lock --update --line lizard2/main --reason "v2 adds the two blade-authority task ids (26-dim action);
  v1 unchanged"` 的输出只有 `change: 2 task(s) added: ['Lizard2-Flat-Play-v2', 'Lizard2-Flat-v2']`。
- **复核（条件 1 的证据）**：那一笔里锁的 diff
  （`git show e59e240 -- rl_exp/versions/lizard2/main/cfg_lock.json`）的 `-` 行只有锁自身的
  `reason` / `reason_at` / `reason_rev` 三行，`+` 行是两条新任务条目（各带自己的 `snapshot` 摘要与
  `env_cfg_class` / `agent_cfg_class`）⇒ **v1 的条目一条未动**，这不是一次重写而是一次追加。
- `check_golden_frozen.py` 报 `GOLDEN_FROZEN_OK (5 baseline file(s) unchanged, frozen at: 020e6fb x2,
  27ca424 x1, 817d64e x1, e59e240 x1)`。

## 证据引用

- 那一笔的锁 diff：`git show e59e240 -- rl_exp/versions/lizard2/main/cfg_lock.json`。
- 摘要表与来源 rev：`rl_exp/tools/verify/check_golden_frozen.py` 的 `FROZEN` / `FROZEN_REVS`
  （该文件在 `FROZEN` 表里同时写了这次重基线的理由，指回本记录）。
- 写入命令与输出：`rl_exp/tools/verify/check_cfg_lock.py --update --line lizard2/main --reason "…"`。
- 复读：`"E:/IsaacLab/env_isaaclab/Scripts/python.exe" rl_exp\tools\verify\check_golden_frozen.py`。

## 未覆盖边界

- 本记录只钉"锁的字节是什么、为什么换、以及换的是不是只有追加"；它**不证明** v2 的配方在运行时正确
  ——那是启动契约探针（随机激励下脚板目标恒等默认位、逐点实读增益与限幅）与训练的事。
- `check_golden_frozen` 的覆盖集是读树上来的：本次动的是其中 1 个文件，另外 4 个逐字节未变（输出里逐个列了
  rev），但"有没有第 6 个基线文件该在表里而没在"属 `uncovered` 的判据，不在本记录范围。
- 重基线**不改任何版本目录的内容**：v1 的冻结副本、`versions/lizard/main/*` 的 19 个锁都不在本次改动里
  （`--update-locks` 那一步的输出明确写了"lizard2 only -- 19 other version(s) not read, not written"）。
