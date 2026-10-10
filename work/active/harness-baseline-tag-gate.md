---
id: harness-baseline-tag-gate
title: 代码基线与 tag 的配对现在有闸：`check_version_docs.py` 读 HARNESS.md 的基线号
scope: ablation_harness
status: pending_review
landing: rl_exp/tools/verify/check_version_docs.py
next: 由新上下文审（不带本次执笔会话的历史）：读 `check_version_docs.py` 的 `baseline_tag_problem` 与其 `--self-test` 的 `baseline_cases` 五例，然后**自己动手做破坏测试**——① 把 `ablation_harness/HARNESS.md` 的基线号临时改成没有 tag 的 `v9.9.9`，闸必须报 DRIFT 且非零退出；② 把 `**代码基线**：` 改成不带全角冒号的写法，闸必须报 `matched 0 time(s)`；两条都必须红，改回后必须绿。再对着 `close_when` 判它是否真覆盖了本项。通过则移进 `work/closed/2026/` 并把读数落一份 `acceptance/records/` 记录；破坏测试只有一条红 ⇒ 退回 in_progress。
close_when: 审核者独立跑出两件事：① `python rl_exp/tools/verify/check_version_docs.py --self-test` 末行为自测判词、`python rl_exp/tools/verify/check_version_docs.py` 末行 `VERSION_DOCS_OK`；② 上面两条破坏测试都变红、改回后转绿。全部成立 ⇒ done（闸真咬得住，且咬的是"号没有 tag"与"基线行读不到"两个分支）；只绿不红、或改错后仍绿 ⇒ 退回 in_progress。
---

## 情况

闸已建，落在 `rl_exp/tools/verify/check_version_docs.py`（§4 的默认动作：断言进已有闸，**0 新进程、0 秒预算**）。

- `baseline_tag_problem(text, tags)` 读 `ablation_harness/HARNESS.md` 的 `**代码基线**：vN.M.K`，与本地
  `harness-vN.M.K` 比对。**返回消息而不是布尔**，所以 `--self-test` 的五例夹具咬的是整条链（解析、条数、
  tag 比对），不是只咬正则。
- **两个分支都是失败**：号没有 tag；以及基线行匹配到 0 或 2 次 —— 这是散文解析的真空洞，行被改写后
  断言会变成 no-op，而 no-op 读起来和"仓库没问题"一模一样。五例里有两例专门咬这个（改写、重复）。
- **报 red，与家族版本 tag 只 WARN 并存**：家族历史前缀未统一、且有提案态；harness 的计数器一种写法、
  无提案态，号是在版本落地时写进去的。理由写在闸的模块 docstring 与 `_BASELINE_LINE` 旁边。
- 顺带修了共享探针 `_git_tags()`：原先 git 读不到时返回空集，与"所有 tag 都没打"不可分，会让这条红闸
  报出误导性原因；现在返回 `None`，由调用方单独点名"git 读不到"。家族侧的 WARN 在该情形下不再刷屏。
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
