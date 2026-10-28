---
id: work-doc-hint-scan-scope
title: 指针扫描把冻结证据读成活指针（HINT 信道被恒噪占满）
scope: rl_exp/tools/verify
status: done
landing: rl_exp/tools/verify/check_work_docs.py
outcome: 用户选择逐条精确豁免；独立审核通过，未核准的历史提示保留，详见证据。
evidence: acceptance/records/2026-10-28-work-doc-hint-exact-review.md, acceptance/records/2026-10-28-work-doc-hint-exact-exemptions.md, acceptance/records/2026-10-28-work-doc-hint-noise-reduction.md, acceptance/records/2026-10-28-work-doc-hint-scope-repair-review.md, acceptance/records/2026-10-28-work-doc-hint-scope-repair.md, acceptance/records/2026-10-28-work-doc-hint-scope-review.md, acceptance/records/2026-10-10-work-doc-hint-scope.md
---

## 当前状态

用户选择逐条核对并精确豁免；独立审核及残余边界见 `evidence`。原条件要求冻结证据类不扫描；新策略不自动识别或整体排除所有冻结证据，保留未核准历史提示。

## 为什么按类豁免，而不是逐条修

记录的活句柄方向是**事项 → 记录**：事项带 `evidence` 指过去，记录里那句"被验的动作 = 某事项"是历史。所以
记录里回指事项的过时路径**不是路由**，按路径豁免它不丢信息；反过来在证据里改路径，等于把"当时对着哪件事"抹掉 ——
那条记录就不再是任何事的证据。这条判断不需要人逐句读，正是它归"类"的原因。

## 未覆盖边界

- 不改冻结证据里已写下的路径，也不把 HINT 升级成红闸：文本仍判不出"活指针 vs 痕迹"，这条边界不变。
- 不含 `work/closed/**` 散文的同类豁免（当前无命中）；要豁免是另一次判断。
- 不含"把扫描扩到代码/配置"：那里路径是数据或 fixture，`_REF_SUFFIXES` 已钉住该边界。
