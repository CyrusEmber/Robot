---
id: legacy-frames-rejudged-invalid
title: 旧帧记录的冻结判决不可再复读（新 reader 的报告项声明把老记录判成 invalid）
scope: ablation_harness/baseline_metrics.py, ablation_harness/HARNESS.md, rl_exp/tools/verify/test_baseline_contract.py
status: open
landing: ablation_harness/baseline_metrics.py, rl_exp/tools/verify/test_baseline_contract.py, ablation_harness/HARNESS.md
next: 先定处置口径（修行为 vs 改声明，见下节，待用户拍板），再落对应改动 + 一条用**旧格式真实记录**（不是最新格式合成 fixture）钉住的行为断言。取证与读数见 `acceptance/records/2026-10-10-baseline-eval-pipeline-restructure-post-close-review.md`。
close_when: 下列两条之一成立，且 `rl_exp/tools/verify/test_baseline_contract.py` 有一条用已入仓 `baseline-frames-1` 真实记录做输入的行为断言（现缺口：钉这件事的测试只喂 `build(frozen, 20)` 的默认最新格式）——(a) 修行为：`python -m ablation_harness.baseline_metrics <已入仓 frames.pt>` 对这些记录回到原判决（`fail`/`pass`），"只对新 reader 强制"对报告项依赖列检查也成立；(b) 改声明：把"旧格式记录遇声明了足端项的协议即判 `invalid`"写进 `HARNESS.md` 的机制契约与 `baseline-eval-pipeline-restructure` 的 P2 出口，并给出旧记录判决的替代可复读路径（原 `eval.json` 与帧并存即为该路径）。两条都不允许只改文档不改测试。
---

## 情况

由 `work/closed/2026/baseline-eval-pipeline-restructure.md`（2026-09-23 关闭）的事后补审发现，非该项当年
已知的敞口。补审判定 PASS-WITH-GAPS，唯一被**行为反证**的出口是它的 P2 承诺"完整性检查不作废旧判决"。

实跑（复读命令见记录的证据引用节）：已入仓三份 `baseline-frames-1` 记录（`lizard2_flat_v1/v1/...`、
`lizard2_flat_v2/v1/...`、`..._settle0.5_superseded`）今天全部复判 `invalid`、gates 全 null；
同目录 `eval.json:1664` 记的是 `fail` / `pass` / `fail`。帧与内嵌协议字节未变 ⇒ **冻结判决不可再复读**。

根因：`baseline_metrics.py:1094-1101` 的报告项依赖列检查对任何 reader 都生效（"只对新 reader 强制"只覆盖
`_judge_reasons` 的未实现名那一半：`:1096-1097` 的 `declared is None → continue`），而 P2 往 `REPORT_ITEMS`
加了 `foot_*`，旧格式帧没有 `foot_lowest_point`/`foot_com_pos`/`foot_lin_vel`/`foot_ang_vel` 四列。
钉这件事的测试用默认最新格式的合成记录 ⇒ 看不到"旧格式真实记录 × 声明了足端项的协议"这个组合。

## 待定口径（用户拍板）

这不是产品阈值，是测量机制的取舍，两条都要付代价：

- **(a) 修行为**：让报告项依赖列检查沿记录所选 reader 走（旧 reader 只按旧路径）。代价 = 旧记录的判决能
  复读，但"协议声明了一个记录没测的项"这条保护对旧 reader 失效，历史上那三份 `report_only` 里的足端项
  将永远只报"缺号"而不报不可判。
- **(b) 改声明**：承认旧记录在新声明下不可判，把这条写进 `HARNESS.md` 与 P2 出口。代价 = 一个已发布的
  验收工具改变了已冻结产物的可复读性，须在契约里显式登记，而不是让它静默发生。

**不做**：不动已入仓帧与协议（它们是复现锚），不重判那三份记录的历史结论，不给 `REPORT_ITEMS` 加开关。

## 未覆盖边界

不管 `outcome` 复述读数那一处散文缺陷（`AGENTS.md` 无闸门、已记在补审记录的"附带形状缺陷"里），
也不管 `baseline_metrics.py:48` 的 `_BASE_COLUMNS` 残留与事项 `landing` 里 `_expected_shape` 的符号名不符
（补审的另两条残留，不驱动判决）。`frame_semantics.json` 新增格式不属本项。
