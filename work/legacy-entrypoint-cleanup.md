---
id: legacy-entrypoint-cleanup
title: 清理旧配方退网后残留的入口与引用
scope: README.md, .codemaker, ablation_harness, rl_exp/tools, rl_exp/tasks, work
status: done
close_when: 正式探针能读取当前实验绑定的机体，默认测试与相关专项通过。删除项均无现役调用方且可从历史标签取回，操作指南明确现役命令和历史复跑入口。
---

## 现役入口与历史复跑

现役以仓库 README 为入口。实验通过 `rl_exp/lizard2_v7.py` 的 `ROBOT` 绑定机体，训评继续使用 `train.cmd`、`eval.cmd` 和现有评测协议。资产候选、接口探针、训评冒烟分别证明不同判据。历史记录的原始命令、注册任务名、协议字节和产物身份保留，复读进入对应历史源码。

## 改动清单

| 对象 | 操作与依据 |
|---|---|
| 圆足正式探针 | 从 `exp.ROBOT` 取 URDF，并把实际执行的机体模块纳入诊断绑定。先保存未修改探针的失败报告，再用同一种工况验证修复。保留既有 `--task` 参数，它在此脚本里选择 Train 或 Play 配置。 |
| 资产验证 skill 和 Blender 参考 | 用现役候选资产检查、圆足正式探针和训评冒烟替换作为当前指南的旧任务命令。旧版的站姿对称与受力流程只给历史复跑入口。 |
| 旧掌足预检与 head dwell 助手 | 仅服务 v4–v6 注册任务，当前只有预检脚本调用助手。两者从当前树移除，原实现与配方同存于 `archive/pre-refactor`。 |
| 旧 UE 导出和一次性更名 | 只消费旧 Lizard 的参数、URDF 和 pin 数据。移除生成器与一次性迁移脚本，保留 UE 构建器和其已生成的 JSON。新 v7 对 UE 的导出契约归独立事项。 |
| 旧 URDF 转换器 | 使用退役版本参数并写入旧资产路径，从当前工具移除。文档改指隔离候选转换，后者继续复用 `flatten_usd.py`。 |
| 旧配方扫描和 A0 迁移 | 旧发现器只有独立自测，A0 脚本重写已退网的布局。移除这三个工具，历史标签保留原脚本。 |
| 当前注释与未结工单 | 扁平工单改指现有路径；已删除工单改指可复读证据，或直接说明代码契约。删除旧门禁引用，保留仍有消费者的历史分析原语及测试。 |
| 新生成的地形档案 | `definition.module` 记录实际生成模块名。新增断言从生成的档案导入生成器。旧档案继续按其 suite、seed 和几何摘要检验。 |
| Windows 地形专项 | 显式按 UTF-8 读取冻结协议来构造测试夹具，避免默认 GBK 在收尾检查时阻断动态传感器断言。 |

删除清单如下。需要复跑任一旧工具时，使用 `archive/pre-refactor` 的独立检出，让脚本和依赖参数一起恢复。

- 掌足预检 `rl_exp/tools/diagnose/palm_preflight.py`、`head_ground_dwell_probe.py`
- 旧资产管线 `rl_exp/tools/pipeline/convert_urdf.py`、`export_ue.py`、`migrate_joint_names_v8.py`
- 旧配方工具 `rl_exp/tools/verify/_a0_paths.py`、`recipe_lines.py`、`test_recipe_lines.py`

## 验收

1. 从现役树核对删除项没有导入或运行方，使用 `git cat-file -e archive/pre-refactor:<path>` 验证每个历史入口仍可取回。历史工单、固化记录和归档脚本允许保留原名。
2. 用 `paths.yaml` 解释器运行默认 pytest、圆足专项、评测记录与地形专项。用 `--collect-only` 复核三个测试目录独立显式收集。地形档案生产路径变更后，实跑 `-m sim` 并核对评测产物。
3. 用正式圆足探针生成独立诊断报告，核对 URDF 与机体模块身份、关节和观测检查、首步及 reset。失败时先保留原输出。
4. 核对活动指南列出的当前工具和参数、评测协议字节与工作区归属。运行 `git diff --check`，按文件边界提交。

## 执行结果

- `rl_exp/out/legacy-entrypoint-cleanup/` 下的 `before-20261124-105050-880` 报告复现旧属性 `AttributeError`。`after-20261124-105225-820`（Train）与 `play-20261124-105640-435`（Play）均退出 0，测得 26 维动作、90 维观测、3 个 control step，并通过显式与自动 reset。两份成功报告都绑定了当前 `ROBOT` 模块。
- 默认 pytest 9 通过、1 排除。显式专项 45 通过，另有 13 项子检查。地形专项复现了默认 GBK 解码错误和档案的旧模块导入错误，两处修复后地形专项 9 条及源码扫描通过。
- 三目录收集 272 条、排除 1 条，无收集错误。`pytest -m sim` 通过 1 条、排除 9 条，耗时 151 秒。完整训评日志与产物位于 `rl_exp/out/legacy-entrypoint-cleanup/sim-20261124-110225-168*`。历史权重在最终提交上的基线评测仍由 [v7 工作流收尾](v7-workflow-hardening.md)验收。
- 8 个旧工具的历史版本均可从 `archive/pre-refactor` 取回。保留当前仍有专项用例或归档分析调用的历史辅助代码，包括 `test_joint_sir.py` 覆盖的 SIR 机制。冻结协议与资产字节没有改动。
