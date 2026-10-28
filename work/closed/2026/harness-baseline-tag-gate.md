---
id: harness-baseline-tag-gate
title: 代码基线与 tag 的配对现在有闸：`check_version_docs.py` 读 HARNESS.md 的基线号
scope: ablation_harness
status: done
landing: rl_exp/tools/verify/check_version_docs.py
outcome: 独立审核通过本地标签名与声明检查，远端锚点和外部调用方不在本项验证范围。
evidence: acceptance/records/2026-10-28-harness-baseline-tag-gate-final-review.md, acceptance/records/2026-10-28-harness-baseline-tag-gate-fourth-review.md, acceptance/records/2026-10-28-harness-baseline-tag-gate-third-review.md, acceptance/records/2026-10-28-harness-baseline-tag-gate-second-review.md, acceptance/records/2026-10-28-harness-baseline-tag-gate-execution.md, acceptance/records/2026-10-28-harness-baseline-tag-gate-repair-review.md, acceptance/records/2026-10-28-harness-baseline-tag-gate-review.md
---

## 当前状态

Tab 缩进修复经独立审核通过；证据和范围边界见 `evidence`。

## 情况

闸已建，落在 `rl_exp/tools/verify/check_version_docs.py`（§4 的默认动作：断言进已有闸，**0 新进程、0 秒预算**）。

- `baseline_tag_problem(text, tags)` 读 `ablation_harness/HARNESS.md` 的 `**代码基线**：vN.M.K`，与本地
  `harness-vN.M.K` 比对。**返回消息而不是布尔**，所以 `--self-test` 的夹具咬的是整条链（解析、条数、
  tag 比对），不是只咬正则。
- **两个分支都是失败**：号没有 tag；以及基线行匹配到 0 或 2 次 —— 这是散文解析的真空洞，行被改写后
  断言会变成 no-op，而 no-op 读起来和"仓库没问题"一模一样。夹具包含改写和重复声明。
- **报 red，与家族版本 tag 只 WARN 并存**：家族历史前缀未统一、且有提案态；harness 的计数器一种写法、
  无提案态，号是在版本落地时写进去的。理由写在闸的模块 docstring 与 `_BASELINE_LINE` 旁边。
- 共享探针 `_git_tags()` 返回 `None` 表示 git 读不到；声明仍校验，标签存在性不作推断。
- `OFFLINE_CHECKS.md` §4 的暂缓条款加了范围说明（2026-10-10 用户拍板）：暂缓针对**被当作能力证据**的
  条目，纯记账的声明一致检查不在此列。

## 天花板

只读本地 ref。**"打了 tag 没推"抓不到** —— 而那一半才是别人能否 checkout 的依据，所以
`work/active/harness-version-anchor-missing.md` 的远端判据（`git ls-remote`）仍需 review，本闸不是它的
等价物。

## 未覆盖边界

- 不动 `harness-v1.8.0` / `v1.9.0` / `v1.10.0` 三个已推的 tag。
- 不新建独立进程：§4 要求新进程买秒，本闸不需要。
- 不重新评价 `video_matrix.py`（归 `work/closed/2026/video-matrix-gears.md`）。
