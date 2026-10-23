# lizard2 main/v4 正式配置独立审核

## 适用范围

本上下文未参与本轮配置执笔。按用户“落实正式训练配置”的授权，审核正式掌部资产、main/v4 配方及任务接入、命名/索引、旧版本退休和证据复用；不是训练启动或策略验收。先读 work-ledger、版本纪律和相关 FILEMAP/FAMILY，再核实际 diff、配置对象、资产、原日志及已审草案；不以主记录转述替代这些核对。

审核主记录为 [配置交付](2026-10-23-lizard2-v4-configuration.md)，初审 SHA256 `0b2fbbe1a01bdccd453045f752e3f017f47eb3a417a45d18c40415d244f11047`。本轮只写本记录，不改实现、锁、work 或其它文档，不提交、推送、起物理或训练。

## 验收条件

- 稳定资产与具名已审输入同字节，引用闭合，正式构造器没有隐藏的增益、目标、采样或物理差异。
- 明确区分 URDF 树序、runtime 观测序和动作序；完整位置动作、逐轴 scale/clip、命名及正式注册对应实际关节。
- 新增元素不改已发布元素语义；退休不改旧配置/历史结果，不把新身份用于续训旧策略。
- 真实缺陷有修前失败/修后通过，声明与有限运行证据各按其能力解释；不把有限草案运行或正式建场等同训练通过。

## 结果

**接受此有限正式配置输入，未发现阻塞配置交付的缺陷。** 完整仓库检查及最终 LF 定向复核已通过，本地冻结身份已核；远端发布和训练前必要预检仍按实际结果收尾。本结论不代替这些动作，也不关闭任何 work。

1. **采用身份与旧版边界。** 新训练配置按版本纪律落入 v4；v3 仅新增退休状态并删除其资产锁，旧任务身份与 tag 不改写。逐文件核 v1–v3 的冻结 YAML、PLAN、NOTES 与 HEAD 相同；AST 核旧 `lizard2_recipe.py` 的 15 个函数/类及旧 runner 的 3 个类无变化。新元素只被 v4 追加消费，runner 只新增实验目录身份，6000 预算和 PPO 沿母本。FAMILY、路线、README 和 work 指向新配置，原实际训练、必要预检、策略评测动作仍留在活跃项。
2. **资产与配置等价。** 新树 38 文件（USD、URDF、36 OBJ）逐字节等于具名 standing 来源，所有 URDF 网格引用存在；USD 无外部 asset 引用。新资产锁的 39 项（含参数）逐项重算摘要均一致，原工具日志只首次写 v4。固定草案的 71 个 `config` 字段逐项与实际构造出的 Train、Play 对象归一化 list/tuple 比较，唯一值差为环境数 1→4096 / 50。PD、caps、默认状态、自碰撞、TGS/false、逐子步接触与六轴 reset 均相同。胸 pitch 280 N·m 对 URDF 80 N·m 的原覆盖保留，未冒称一致。草案显式全部 body union 与正式 `Robot/.*` 是选择表达差异；正式场景日志实际覆盖 31 bodies。
3. **索引及运行证据。** 动作是明确 preserve_order 的 20 腿 +10 胸颈尾，逐名覆盖 30 个非固定关节，scale 与 URDF 对称可用范围/3、clip 与逐轴硬限位一致，默认偏置为零。七项观测保持：q/dq 依 articulation runtime 顺序，last_action 依动作序，二者不误称同序。结构化比较协议登记：旧条目、旧宽度、旧运行顺序均不变，只加 v4 和新资产的 102 维批准宽度。正式 live 原日志无 target_config，确有建场/reset、30 joints、31 bodies、102 policy 和新资产 pin；日志中的 `unapproved` 是批准宽度写入前的读数，不是随后批准已被再次实跑的证据。未据此声称 commanded rollout。
4. **负例不是声明自证。** 在内存取 HEAD 原 `load_diagnostic_target` 实际函数重现 v4 因 shared 命名被拒；当前函数及错误 naming 负例通过。取 HEAD 原 `covers` 实际函数重现 `[]` / `[0]` 均不覆盖，当前数组正例、兄弟键和反向负例通过。独立运行当前六项离线配置测试全部通过；没有启动 Kit。新 optional `robot.naming` 保留旧 YAML 默认 shared，旧 v3 实际绑定仍为 shared。
5. **证据复用没有扩大结论。** 复用的是相同资产/参数/处理链下草案的有限 affine、clip、backend 零速度、非零观测、接触 history 与 reset 证据；正式建场补新身份/路径和实际管理器布局。单环境/双环境证据不外推 4096 环境性能或所有并发状态。原 processed/backend position target 在 reset 即时可能残留、下一步先写新动作再推进物理的边界仍明确；TGS/false 的速度偏差和未知自然终止/timeout 范围也保留。
6. **新增 golden 锚点复核。** 只读 diff 确认 `check_golden_frozen.py` 只改 lizard2 的期望摘要、说明和 banner provenance，校验函数未变；B0 表只加本次记录指针。旧摘要的实际日志拒绝新 golden，当前实际执行输出 `GOLDEN_FROZEN_OK`，与原更新工具“仅新增两 task”相符。`FROZEN_REVS` 中 `lizard2-main-v4` 是本轮冻结锚的名称；该次初审时 tag 尚不存在，banner 不能证明其已创建或发布，最终本地身份另按实际 refs 补核。另核 launcher 原 argv 无 `--launch`，计划身份为 active/v4、操作 new_train allowed，只有 seed 覆盖；该允许判定不是训练已经运行。
7. **检查兼容修正重审。** 初审后完整检查暴露旧夹具绑定及 emitter 的真实缺陷，本上下文重新核实际 diff 与失败/最终日志。旧速度闸门只对 `lizard2/main/v4` 增加逐关节 implicit sim caps 的严格分支（原组 10/6/4），旧 inert scalar 规则不删；在内存独立复现 HEAD 原函数对 v4 的 12 条拒绝，当前 clean baseline、原 11 类负例和新增缺失/改值/外来键均通过。manifest 仅改绑 v4/102 的有效资产锁，原漂移、dirty、resume 等负例未删。sole/FK/反曲算术控制明确使用 v3 资产和冻结参数，原数字/负例保留，套件标签不再称它证明当前掌部几何；正常 reader 默认仍取当前掌部及其 naming，新增逐关节 gain 读取保留 scalar 兼容。dev 接触 owner 从 URDF 碰撞和非固定链父链接求得，排除 terminal；独立执行空选、错名、全选三负例均拒。emitter 原 last-writer 归属由本上下文在 HEAD 原函数上复现五条失败；当前按父块的实际完整 writer 集合署名，原 hard B 规则未改，仍为 65 env +1 agent，两个组合作者组准确覆盖五个父块。当前新增几何绑定与 emitter 回归也由本上下文执行通过，最终持久配置回归为 8 项。
8. **换行与首次锁重建。** 参数 CRLF→LF 的确会改变文件摘要；独立将最终 LF 字节还原 CRLF，恰好得到初审 `fa454c…`，确认没有参数内容变化。比较留存早期锁与最终锁，仅 v4 YAML 摘要一项改变，其余 38 资产及 note 相同；最终 39 项摘要全匹配。再次逐字节核工作副本、实际 index 和原来源的 38 资产全部相同，最终文本源码/index 也相同。`.gitattributes` 的 `-text` 只限新资产树，URDF 只豁免该文件的 blank-at-eol、USD 只豁免该文件的 blank-at-eof，并识别源 CRLF；没有源码空白检查豁免。v4 当时未 tag/未发布，原工具针对不存在的新锁重新生成，不是刷新已发布锁。

初次完整套件因本记录尚不存在导致 WORK_DOCS_DRIFT，随后还有上述真实兼容失败，失败日志均保留。最终实际 `offline_suite_release.log` 为 `ALL_OFFLINE_CHECKS_PASSED (37/37 in 63.2s)`；LF 规范化后配置 8 项、严格 parity+self-test、precommit 静态检查再通过。单独 parity 的未设 UTF-8 输出失败未冒称通过，也没有为输出问题改源。记录落盘后本上下文执行 work 格式检查为 `WORK_DOCS_OK (91 item file(s))`；全套与定向检查不证明训练表现。

最后复核活跃训练事项的当前态清理：已完成的配置/采用动作转为 v4 与证据指针，实际预检、运行条件、训练、策略评测及真实缺证修复仍在原项；未删评测目标、未解除安全条件，也未关闭事项。本记录五节、LF、表内实际文件哈希及暂存 diff 空白检查均再核通过。

**冻结身份补核。** 实际 HEAD 与本地 `lizard2-main-v4` 均精确指向 `9465f9f60dee2eed9b0ab310e40d0ba853fedb09`；逐项读取该提交中的已审对象，均与下表摘要相同，未读取 cfg_lock 正文。原 commit 日志含正常 `[pre-commit] static gates passed` 和该提交成功行。主记录仅把末尾待发布元数据替换为实际 commit/tag/钩子及未训练边界：反向还原该段，得到上一已审 SHA256 `363260fa0aec1c47465b50b03bc43f33a870d96ff286476dca6d4611cd51017c`，证实无配置、数值或其它正文漂移。本次没有重复已通过功能检查，不声称已经推送远端。

## 证据引用

- [固定草案与接口运行审核](2026-10-23-lizard2-interface-runtime-review.md)、[B/C 输入审核](2026-10-23-lizard2-bc-independent-review.md)、[原生接触审核](2026-10-23-lizard2-contact-native-review.md)，其原有限范围不改判。
- 固定草案 `rl_exp/out/lizard2_bc_handoff_20261023/training_interface_draft.json` SHA256 `a120b8907601852e5ca7bf1190f675d75ea7a8ae0fa79e970d887628ed7e8b19`；正式 USD `721e8a4053c2a6114b5c4607e57ed34f287fe317f8f9abb47a5e857b845e9c0e`，URDF `e8896feb8b0dbdbeaa35e74a01c2ffcb4ab38d89b52f221831b3f287943edd00`。
- 持久复读入口 [test_lizard2_v4.py](../../rl_exp/tools/verify/test_lizard2_v4.py)、[正式参数](../../rl_exp/versions/lizard2/main/v4/main_params.yaml)、[逐项差异](../../rl_exp/versions/lizard2/main/v4/diff.json)。从仓根以项目 Python `-B` 运行配置测试，不启动环境。

| 实际审核对象 | SHA256 |
|---|---|
| `rl_exp/tasks/lizard2_recipe.py` | `a7516eebdb2fd341c3ac005088b278c6207e9feeb51376a4e3e1c5f5fbceceed` |
| `rl_exp/tasks/obs_protocol.py` | `d6e66af6aff105f1a82394c00d2d4ffdc509075cea926e2a3c704b06d87c95c6` |
| `rl_exp/tasks/agents/rsl_rl_ppo_cfg.py` | `9d961be35015a0b6da5ba2f4c893e7056a638889f4bead19eda59c2ae83d33f9` |
| `rl_exp/tools/verify/test_lizard2_v4.py` | `3a17d5af05bf20d0388d3f2d2617968ade9b680ab5f781e320db67e304c8f262` |
| `rl_exp/tools/verify/check_recipe_build.py` | `1247af913a4895e0082923aa35a2d48b76a8f5d6dbe3f9251f54247bc7e1fb59` |
| `rl_exp/versions/lizard2/main/v4/main_params.yaml` | `db3291e93688426d3251db837f352982c5764865486112d279b52a1475036abc` |
| `rl_exp/versions/lizard2/main/v4/asset_lock.json` | `274bbc2268dad07b39692a836837f8830ae4708035b3d34ed22590dabff79b6b` |
| `rl_exp/versions/lizard2/main/v4/diff.json` | `1e2323aa58b12eea91d3d18513ecea2768da68701add8034ba01d225fe2911e2` |
| `rl_exp/out/lizard2_v4_obs_live.log` | `8237fc1d03edb8e0cce31c47877f1f5dc48f783723521244f5ce3555a3147d9c` |
| `rl_exp/tools/verify/check_configclass_fields.py` | `0f27923432014b20a398043d62ad3966e201cacc8c227edeb6967ee723f91f6c` |
| `rl_exp/tools/verify/test_configclass_fields_gate.py` | `a235ab325b446882da8d8456632ba2be160ad1bd645a93e47802eef4403f2555` |
| `rl_exp/tools/verify/test_run_manifest.py` | `4d2ae7207b81429cbecc0f0daa0083af4c34eeb1da8a78de9ea369d89735bd5d` |
| `rl_exp/tools/diagnose/gait_probe.py` | `869934db91823166561c8ca7433df51da95d64141ed9d6740360c26e9bc4f565` |
| `rl_exp/tools/verify/check_leg_reachability.py` | `97eb7fe49c10e7f03f165722ba62e571e9b08a08f0f40abe52b4b905c11bdff3` |
| `rl_exp/tools/verify/test_baseline_contract.py` | `9b63778898a74ec784be8a7724f35ef1eb34650e5e156ac7b925fd71cf8c963f` |
| `rl_exp/tools/pipeline/emit_diff_declaration.py` | `a2063af4e64742ef3367010bc5c6fdbfaa4f1fb77e88a72a47147c40c894083a` |
| `rl_exp/tools/verify/offline_suite.py` | `17f7c6dd1e51f372aafe4785bdfe0bac105ee503b716390f3ee94de4b9c2557a` |
| `.gitattributes` | `9faf840c91c602d56b41295d285276c5abcd8fcaca0dabc9d9da5231a91564ab` |

`rl_exp/out/lizard2_v4_golden.log`（SHA256 `8870abbcabd45488630ead1e509e412f96e6b74bb91de6f8babe42b523d3898c`）记录仅新增两个 v4 task；没有读取 cfg_lock 正文。`asset_lock.log`（`dfb4f75137c7479f84470048e6d9dd20d94c5f12155168cd4a32215616eecf8c`）记录只写 v4。修前/最终配置测试日志在相同前缀下保留；失败的 draft_comparison_final.log 不作通过依据，字段比较由本上下文直接完成。

最终主记录 SHA256 `32bbd02d74b6582bebd64a19a6cacf8a103d0bb3dc78ce52f956f9e6c2d985a9` 已复核，取代初审/中间元数据哈希；正式实现与 38 资产不变，新增兼容代码和最终 LF 参数/锁/差异哈希见表。冻结日志 `rl_exp/out/lizard2_v4_commit_freeze.log` SHA256 `ff055a77f0e87f8940a2544d53bb7433c1226437f5c1abb430538fb4a3063196`。`check_golden_frozen.py` SHA256 `f9ca7833f2a9eadf4497cc0570921e74b7ebcdfe11f3bc98fdc85903e68f4a1f`；旧锚拒绝日志 `rl_exp/out/lizard2_v4_golden_pin_before.log` 为 `46bc8ddee6610f7e9b8a11b75b25faa0764112ebe817d8f237c159a57ee9f6e6`；计划日志 `rl_exp/out/lizard2_v4_launch_plan.log` 为 `14e12870c392fafddbb5c5dc75e56beda892cc7320ef6004d1bab15f5c4735ee`。

最终原日志 SHA256：`rl_exp/out/lizard2_v4_offline_suite_release.log` 为 `a2d56dad9b8f84695be848a7f257ca8d3ba1cff5702da923d51fea41303ac9a1`；`lizard2_v4_lf_config_tests.log` 为 `c4b03805663b644cd99b047f3267c5d52c6fbb4931fe7678213cc649d75b6eb6`；`lizard2_v4_lf_parity_utf8.log` 为 `820b35a97e2ea93e7acdb18b3706b3a0fcac46f28dff58162f3050d0c5a61c5f`；`lizard2_v4_precommit.log` 为 `61ff20535c3260c6e4759e5afa5778170b3af5757e17ef2806a145b81ea9957f`。

## 未覆盖边界

本轮未新增物理采集、训练、checkpoint 或策略评测；未验证正式默认并行规模下运行性能、全部地形/终止组合、普通自然终止/timeout 到期、动态滑移/滚动分类或硬件包线。不恢复已取消的限速/限矩、对称复测、手工步态或独立 S5/S6 门槛。本地冻结已核，远端推送及训练前集成/预检按原路由执行；配置接受不是训练已放行、work 已关闭或全域驱动验收。
