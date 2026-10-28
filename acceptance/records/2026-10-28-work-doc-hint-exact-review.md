# 指针精确豁免及导航修复独立审核（2026-10-28）

## 适用范围

- 不带执笔历史的新上下文审核 `work-doc-hint-scan-scope` 的扫描实现、逐条豁免及两处家族活文档导航修复。
- 用户选择逐条核对并精确豁免；原条件的“冻结证据类整体不扫描”未实现，本审核不声称自动识别历史。

## 验收条件

- 已核准历史引用仅在文件、行号、整行和引用目标均匹配时豁免；其他引用与活文档仍报告，范围及破坏测试可复读。
- 核对家族活导航修复与其闭项依据，保留冻结记录和未完成动作。

## 结果

**通过用户选定的精确豁免口径。** 两条豁免属于开训前历史上下文；探针未做、训练记录不完整仍是事实，豁免不代表通过。两处家族导航分别指向已归档的 `baseline-v2-recipe` 和已取代的 `phase2-obs-fidelity`，未更改冻结版本文件，亦不声称被取代事项已完成。

- 按 `acceptance/records/2026-10-28-work-doc-hint-exact-exemptions.md` 的五条命令复跑，退出码依次为 0、1、1、1、1：自测通过；撤销精确豁免、还原旧扫描范围、撤销记录目录豁免、撤销去重分别触发预期断言。
- 单独默认检查 `WORK_DOCS_OK (94 item file(s))`，当次保留 4 条 HINT；计数是当次工作树读数，不是固定基线。
- `rl_exp/versions/lizard/baseline/v1/NOTES.md:182`、`baseline/v2/NOTES.md:45` 是历史复验和记录缺口入口，旧线退休后复验触发条件不可达，缺失复现锚仍是事实；`rl_exp/versions/lizard/main/v14/NOTES.md:3` 的历史 run 核认经用户裁决取消，未核认 run 仍为 unknown；`rl_exp/versions/lizard2/main/v2/PLAN.md:91` 是预注册风险处置入口，原事项已关闭。四条均保留提示，不授权改写冻结文档，也不把历史缺口当作已验证。
- 家族事项退休处置依据 `acceptance/records/2026-10-09-retired-family-prune-manifest.md`；本次未发现须从本事项迁出的未完实现动作。

## 证据引用

- 逐条判断和可复读命令：`acceptance/records/2026-10-28-work-doc-hint-exact-exemptions.md`；前次复审：`acceptance/records/2026-10-28-work-doc-hint-scope-repair-review.md`。
- 实现：`rl_exp/tools/verify/check_work_docs.py` 的 `_HISTORICAL_REFS`、`_inbound_hints`、`self_test`。
- 历史依据：`rl_exp/versions/lizard/baseline/v2/PLAN.md`、`rl_exp/versions/lizard/baseline/v2/NOTES.md`、`work/closed/2026/baseline-eval-protocol-gap.md`。
- 导航修复与依据：`rl_exp/versions/lizard/ACCEPTANCE.md`、`rl_exp/versions/lizard/OBS.md`、`work/closed/2026/baseline-v2-recipe.md`、`work/closed/2026/phase2-obs-fidelity.md`。

## 未覆盖边界

- 仅扫描可读取、未超大小上限的 Markdown；代码、配置及验收记录目录不扫描。未审计全部文档语义或物理、训练表现。
- 精确豁免不覆盖未来历史痕迹；行号或整行变化时 HINT 恢复。剩余 HINT 留待人工判断，不修改冻结记录。
- 前次执行记录中的六条保留是导航修复前快照；本次审核时为四条。
