# 删掉 FILEMAP 的线级行（第 4 步第二个候选，2026-09-23）

## 适用范围

- 落点：`FILEMAP.md`（删 3 行线级行；该节重命名为"版本目录内的文件"并重写说明）、
  `rl_exp/tools/pipeline/declare_family.py`（删 `filemap_rows()` 与它的打印块；模块 docstring、`Target.rel` 与 FAMILY 模板注记同步）。
- 属 `work/active/freeze-maintenance-simplification` 第 4 步的**第二个**候选，同上一候选一族：手工索引行。
- **不覆盖**：`lines.json` 自身的内容；`FAMILY.md` 的版本史行（那是身份，有闸门）；FILEMAP 里描述布局的散文。

## 验收条件

1. 删前先取观测（它被谁看守、删了会不会红），不许推断。
2. 删后：原来抓住的事要么有接替反例，要么明确写成"不再被发现"。
3. 同一变更内建新删旧（文档 + 打印器 + 文案），不留中间态。
4. 套件入口数与 `MAX_CHECKS` 不变。

## 结果

**一、观测 A（有没有人看守）**：把那 3 行删掉后跑三个可能有关系的闸门 ——

```
check_version_docs.py:   rc=0
check_recipe_registry.py: rc=0
check_recipe_map.py:     rc=0
```

⇒ **从来没人看守它们**。这与上一个候选正好相反（那条删行会红）：这些行不但在重复事实，而且是**无人维持**的重复。

**二、观测 B（那件事的家在哪）**：从 `rl_exp/versions/lines.json` 撤掉活跃线 `lizard2/main` ——

```
check_version_docs.py:   rc=0
check_recipe_registry.py: rc=1      ← 接替在这里
check_recipe_map.py:     rc=0
```

⇒ "哪个家族、哪条线存在、活跃还是退役"的家是 `lines.json`，闸门是 `check_recipe_registry`。

**三、它已经过期了（促成删除的硬证据）**：那三行指向的 `lizard/parkour` 与 `lizard/baseline`
早在 **2026-09-22** 随整族退役（`lines.json:5` 起逐条 `status: retired` + `retired_at`），
而表里一个字都没写、也没有任何东西提醒它 ⇒ 手工索引**已在骗读者**。

**四、删除规模与同变更对齐**

- `FILEMAP.md`：−3 行；该节改为"版本目录内的文件"，并把三层归属写清：家族/线 → `versions\lines.json`（registry 闸门看守）；
  版本身份 → 各 `FAMILY.md` 版本史；目录存在与齐件 → `check_version_docs` 读目录判定。
- `declare_family.py`：−1 函数（`filemap_rows()`）−1 打印块；docstring 里"要粘贴 FAMILY + FILEMAP 两行"改为只粘贴 FAMILY 一行，
  并注明新线的家是 `lines.json`；`Target.rel` 的说明与 FAMILY 模板注记同步。

**五、验证**：`check_version_docs` → `VERSION_DOCS_OK`；`declare_family.py` 语法解析通过；
pre-commit 六闸全绿（含 `check_dr_parity --self-test`，它一并跑 `test_declare_family` 的夹具）。

**关于全量套件**：那一轮 `[14]`（本改动相关）**ok**，但**整轮 FAIL，原因不属本改动** ——
`[22]` 挂在 `ablation_harness/baseline_metrics.py:726` 的 `NameError: name 'JUDGE_REPORTS' is not defined`，
而该文件当时正是**另一会话**在改（工作树 `M`，同一批还有 `baseline_frames.py`/`test_baseline_contract.py`）。
**本记录不声称那一轮 47/47**；本改动不碰那些文件。

## 证据引用

- 观测 A / B 的输出见"结果"节（受控变更：`try/finally` 还原并校验 byte-exact；探针脚本在 `%TEMP%`，跑完即删）。
- 过期证据：`rl_exp/versions/lines.json`（`lizard/main`、`lizard/parkour`、`lizard/baseline` 均为 `retired` + `retired_at 2026-09-22`）。
- 提交面：`git status --short` 只见 `FILEMAP.md`、`declare_family.py`（提交 `25bb445`，2 文件 +17/−30；pre-commit 六闸绿）。

## 未覆盖边界

- 现在"一眼看有哪些家族/线"要靠 `lines.json` 或列目录；FILEMAP 不再提供。这是**决定**（与上一候选同理），不是遗漏。
- FILEMAP 的散文仍以 `versions\lizard\...` 举例讲布局（`:92` 一带），本次未改：那讲的是**层级形状**，不是索引。
- `rl_exp/tools/verify/_a0_layout_migration.py:76` 的历史说明仍写 "FAMILY/FILEMAP rows"（一次性迁移脚本，未动）。
- 旧记录里的历史引用按仓规留存，故 grep 仍会命中已废的措辞。
- 全量套件那一轮因他人半成品而红；本改动的完整端到端验证待套件恢复后再补一次（未做）。
