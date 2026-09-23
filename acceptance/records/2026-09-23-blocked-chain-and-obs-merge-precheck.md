# 卡点链：依赖环、obs 合口核认、两个待拍板决定（2026-09-23）

## 适用范围

- 本轮只处理"卡在别人手上"那条链里**我能执行的部分**：
  ① 依赖环（修）；② `obs-three-tables-merge` 的**核认**（做）；③ 两个待拍板决定（只备证据，不代拍）。
- 落点：`work/active/baseline-eval-protocol-gap.md`（删一条陈旧 `depends_on`）、
  `work/active/obs-three-tables-merge.md`（核认结论回填）。
- **不覆盖**：第二步第三类（开训前协议绑定）的**实现**——它等 owner 拍板形态 + `baseline-eval-protocol-gap` 的 v2 首跑，
  而按 `eval-protocol-before-training` §排序决定（2026-09-21，用户）"**v2 先开训，本闸门后补**"，实现不该抢跑；
  也不覆盖 obs 合口的实施本身。

## 验收条件

1. 环消失，且 `check_work_docs` 保持绿（不靠放宽闸门）。
2. 核认三问各给**代码依据**（file:line），不采信事项正文里的表述——它可能过时。
3. 不代 owner 决定形态；只把"要想"变成"要选"。

## 结果

**一、依赖环：两个事项互指，陈旧的是 gap→gate 那条。**

`eval-protocol-before-training` 正文 §"排序决定（2026-09-21，用户）：v2 先开训，本闸门后补"已把顺序定死：
缺的只是**机制**，而机制排在 v2 之后。所以 gap 的工作不需要闸门存在 ⇒ `baseline-eval-protocol-gap` 的
`depends_on: eval-protocol-before-training` 是陈旧箭头，已删。现在只剩 **gate → gap** 单向（＝闸门等 v2 首跑），
与排序决定一致。`check_work_docs`：`WORK_DOCS_OK`。

**二、obs 合口核认（三问，逐条给依据）**

① **三张手抄表仍在**：`rl_exp/tasks/components.py:391`（`PROPRIO_TERMS`）、`:402`（`BASELINE_PRIV_TERMS`）、
`:412`（`SPEC_TERMS`），构造时使用于 `:550-557`。

② **互钉的准确形态**（事项原文"仍由 `[8]`+`[42]` 互钉"需要修正）：
- `[8]` `check_obs_layout.py` 才是那个对账：它读**构出的** `cls().observations` 的分组序列
  （`:165,177,216,254,437`），比它自己的期望顺序；而期望顺序来自**声明**——
  `_declared_orders()` → `obs_protocol.live_terms_for()`（`:96,104,107-114`）。
  ⇒ 这正是"实现侧（三张表）vs 声明侧（`obs_protocols.json`）"的互钉。
- `rl_exp/tools/verify/test_component_ownership.py:275-307` 另外**直接点名**三张表，断言分组序列等于它们。
- `[42]` `check_obs_protocol.py` **不点名**这三张表：它钉的是"声明 vs recipe golden"，
  `--live` 时再加"声明 vs 构出的 cfg"（`:468,501`）；而套件跑的是**不带 `--live`** 的那半。

③ **合口的代价经代码确认**（此前只是推断）：合口后组件改为读声明 ⇒ `[8]` 的比对退化为"声明 vs 声明"（自指），
届时独立来源只剩**冻结 golden** 与 `--live` 那半。这与事项里写的代价一致，现在有了机制级依据。

**动工前置判定：满足**。`components.py` 最后一次**实质**改动是 `bbedd96`（2026-09-18，"Delete the version subclasses"），
其后只有 `4a80e47`（2026-09-21，只改引用指向、不动行为）；2026-09-17 设的排期约束正是"builder 改动静下来后一次落"。

**三、两个待拍板决定——只备证据**

| 决定 | 卡住的活 | 我备到的证据 |
|---|---|---|
| 形态三选一（`teacher-literal-parity-gate`） | 第 4 步的 teacher／`freeze_parity.json` 去重 | 它的 `next` 首句即"先由用户拍板形态"；三选项与后果已在该项写清，本项不重复 |
| 开训前协议绑定的形态（`eval-protocol-before-training` ①） | 第二步第三类实现 | 该事项已写明"不新造机制，只把它们接起来"，且点名了可抄的先例（`manifest.begin` 的拒绝集合 + `obs_protocol` 的"声明协议 + 摘要"形态） |

两者都只等 owner 一句话，没有可代做的部分。

## 证据引用

```
$ git log --date=short --format="%h %ad %s" -3 -- rl_exp/tasks/components.py
4a80e47 2026-09-21 Point the code's references at the items, not at PLAN's drained rows
bbedd96 2026-09-18 Delete the version subclasses, and ask the gate the other question
f349495 2026-09-17 Make the curricula read the split the generator produced

$ python rl_exp\tools\verify\check_work_docs.py
WORK_DOCS_OK (53 item file(s))
```

依据行：`components.py:391,402,412,550-557`；`check_obs_layout.py:96,104,107-114,165,177,216,254,437`；
`test_component_ownership.py:275-307`；`check_obs_protocol.py:468,501`。

## 未覆盖边界

- 我没做 obs 合口的**实施**（不属本次）；`--live` 那半**没跑**（需要 isaaclab，属实施前置）。
- `[8]`／`[42]` 是**套件序号**，会随清单增删而漂；本次按标签核对（"obs layout gate"／"obs protocol declaration"），不按数字。
- "builder 静下来"是判断：我按"最后一次实质改动 2026-09-18、之后仅引用改动"判**满足**，最终确认权在该事项 owner。
- 两个待拍板决定我只备了证据，**没代拍**；第二步第三类因此仍 blocked。
