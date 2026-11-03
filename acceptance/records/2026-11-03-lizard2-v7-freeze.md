# lizard2 v7 冻结与共享工作树归属

## 适用范围

2026-11-03，用户明确批准“冻结并同步远端”：解除此前不提交边界，只提交v7、圆足与必要接口文件，保留其他会话工作，打 `lizard2-main-v7` 并推送；不启动训练。本记录追踪真实提交/标签/远端结果，不以计划或检查通过冒充操作成功。

## 验收条件

- 提交集合具名，必要代码、正式资产、配方、接口锚点及证据引用闭合；不提交评测耦合、两足支撑、UI等未授权工作。
- 不清索引、不stash/还原共享改动，不使用全树add；按本轮路径提交，hooks不跳过。
- 候选快照独立验证，不能只凭含别人未提交改动的工作树全绿；正式资产/参数/接口脚本与已审核证据字节一致。
- 当前黄金来自真实提交时才回填 `FROZEN_REVS`，旧tag不改写；新tag真实指向本次冻结快照。
- 远端只正常递增推送；失败报告，不强推。剩余共享脏树按原归属保留，不伪称已经可在脏树上训练。

## 结果

用户授权后，实际发现HEAD已由其他会话从 `d4a06a7` 前进至 `24e8eb1`，其提交完成观测入口退出码修复。重新按实际diff核：`obs_protocol_live.py`剩余差异仅本轮原生preset解析两行；`obs_protocol.py`剩余差异全部固定末端/最终状态一致性及对应反证，因此两文件可归本轮整文件提交，不需要裁剪或还原别人的代码。

### 提交归属

本轮范围：

- 资产/来源与可复读入口：正式 `rl_exp/lizard2_round_feet/`；圆足candidate/export、结构生成、USD审计、正式probe及focused测试。
- 训练接入：v7注册/recipe/runner、线dev/v7参数、base/diff/asset lock、旧v4–v6资产锁删除、生命周期/身份/资产声明、runtime order与obs宽度锚点。
- 必要共享检查：固定末端读取、原生preset解析、v7限速字段适配、v4历史断言读取、退休后的manifest/rebuild隔离夹具、golden冻结摘要。
- 文档：v7 PLAN/NOTES、家族事实/入口、B0路由、三份v7实测/重锚记录及本冻结记录、圆足work、旧脚板两项归档及独立关闭审核、必要性事项交接。

留在原工作树且不暂存：`ablation_harness/`评测耦合改动及其records/work；`column_coupling_probe.py`；`palm_contact_sample.py` / `palm_training_interface.py`；`check_suite_shape.py` 与 `test_eval_record.py`相关其他会话改动；两足支撑geometry/video、lift guide及测试、查看器、landing probe、学习步态work等。由具名暂存集合与独立候选检查再核，不靠这份分类文字证明归属。

### 实际执行

操作前暂存区为空、分支main、新v7标签不存在，远端为 `origin`（用户仓 `CyrusEmber/Robot`）。

暂存字节核对发现仓级LF归一化会改变29个已审制品（URDF与28网格），而USD字节不变。沿既有掌足资产原字节政策，为圆足目录新增定点 `-text` 及仅源URDF/USD历史格式例外；只对该目录索引重录，不改源文件。30个正式制品暂存字节随后全部匹配实测源哈希，最大单文件6,307,658字节，总12,172,188字节。

首轮独立候选快照通过 `git write-tree` + archive放到系统temp，未借用原工作树未暂存内容；资产契约检查发现v7冻结参数CRLF也被索引归一化，锁期望 `cec36187`、候选实际 `93fd1fe4`。不刷新资产锁或历史证据，而为唯一已测 `v7/main_params.yaml` 添加定点原字节属性，索引重新录入后SHA保持 `cec36187638859eb8109e760551cde1203b9a7bfdeb3b0462c72f71eb37b49dc`。第一次失败现场保留在 `%TEMP%/lizard2-v7-freeze-3hznmbja/offline.log`，候选后续检查用新日志，不覆盖失败。

第二轮候选恢复参数原字节后资产契约通过，但work检查发现既有 `diagnostic-artifact-lifecycle` 的scope指向机器本地 `rl_exp/out`，干净archive不含该目录。仅在临时候选创建空输出目录，不复制原工作树诊断数据或其他会话代码；保留第二轮失败日志 `offline02.log`，第三轮用 `offline03.log`。候选专项 `test_lizard2_v7.py` 与 `test_lizard2_round_feet.py` 实际14项通过、15个subtest通过，正式30资产、v7 yaml及probe32个受审文件的索引字节与工作树原字节全部一致。

第三轮独立候选完整套件实际退出0，37/37通过，56.9s，无失败或跳过。验证的是暂存快照与HEAD已有内容，不是借用仍未提交的评测/lift/UI工作；只补机器路径和空输出目录。冻结归属的另一新上下文只读核82个diff路径、原字节属性、必要共享修改和归档交接，未发现归属混入硬阻塞。版本/事项文档检查及索引空白检查随后通过。

提交、标签和远端结果按实际回填；尚未执行的动作不记成功。

## 证据引用

- 参数及源资产：`acceptance/records/2026-11-03-lizard2-v7-round-feet.md`。
- 原生接口/批准范围：`acceptance/records/2026-11-03-lizard2-v7-interface.md`。
- 黄金逐字段审核：`acceptance/records/2026-11-03-lizard2-v7-golden-rebaseline.md`。
- 新冻结方案：`rl_exp/versions/lizard2/main/v7/PLAN.md`；实际状态路由 `rl_exp/versions/lizard2/FAMILY.md`、`rl_exp/versions/lizard2/PLAN.md`、`work/active/lizard2-family-landing.md`。
- 共享diff复核只读上下文 `a12f8c34-ffa9-48df-8017-68edcc68d41e` 与文档依赖闭合复核 `dc79e814-425e-4671-a85d-bf70abef4a38`；前者无终端的推断已由主上下文真实git diff纠正，以真实HEAD及diff为准。

## 未覆盖边界

- 本轮只冻结已审训练候选；无新训练run/checkpoint、无承重或步态性能结论。
- Blender来源报告、失败日志与接口原始JSON在本机输出树，未因冻结承诺上传全部DCC来源或诊断制品；正式USD/URDF/网格、参数与可复读代码入库。
- 其它会话的未提交改动不因本轮冻结消失；当前树仍脏时训练默认拒绝，不设置脏树豁免。
- 原接入/接口/重锚记录中的“未提交”是各阶段事实，后续提交身份以本冻结记录为准；不改写历史失败或旧tag。
