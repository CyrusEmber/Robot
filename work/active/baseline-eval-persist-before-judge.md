---
id: baseline-eval-persist-before-judge
title: eval 先保存完整采集，再判分
scope: ablation_harness, rl_exp/tools/verify
status: open
landing: ablation_harness/baseline_eval.py, ablation_harness/baseline_frames.py, rl_exp/tools/verify/test_baseline_contract.py
next: 调整 baseline_eval.run 的保存顺序；帧文件原子完成且拒绝覆盖，判分失败可从已保存记录离线重试，并做失败注入回归。
close_when: 执行者注入判分异常后可加载完整帧并离线复判；写盘异常无伪完整产物；重试不覆盖原记录；工具错误对调用方可见。修复前反例失败、修复后通过，相关回归及离线闸门通过，证据归档后关闭。
---

## 来源与范围

由 `work/active/baseline-eval-pipeline-restructure.md` 的 P0 拆出，可独立实施，无家族阈值前置。
`baseline_eval.run` 当前在保存帧前调用 `judge`；本项只修已完成采集被判分异常连带丢失的执行耦合。

## 实施与验收

1. 采集结束后先封装、检查并保存完整记录，再调用判分；临时写入后原子完成，已有目标拒绝覆盖。
   帧与 meta 可独立在 CPU 读取，携带本次采集条件与来源；不在本项扩展步态字段或改格式语义。
2. 判分异常保留记录路径与错误，沿现有离线入口重试；采集无效、策略失败、执行错误分别可读。
   核验 Kit 关停不吞工具错误状态；未完整的采集不能标成完成。
3. 在既有测试入口注入判分异常和写盘失败，确认记录恢复与非覆盖行为；撤掉修复证明反例失败后恢复。
   验证同一记录修复后可复判、摘要不变。真跑取证写入 `acceptance/records/` 并回填指针。

仅采集 CLI 的扩展由总项编排时处理。本项不承诺任意进程中断后的续采，不接协议发布与产品门槛。
