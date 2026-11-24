# 退网残留清理：只留 v7 现役最小集与可核验归档

- 日期：2026-11-24
- 范围：仓内代码、资产、`rl_exp/out/` 产物、`work/` 工单、`.gitignore`/`.gitattributes`/`AGENTS.md`/`README.md`
- 结论：仓内只剩 v7 现役入口、正式圆足资产与 4 份锚定 YAML 协议；被移除的 6648 个文件全部可核验恢复。

## 为什么做

旧配方退网后，`rl_exp/tasks`、`rl_exp/versions`、`rl_exp/ue`、`rl_exp/fork_patches`、旧诊断脚本与
`rl_exp/out/` 下约 5000 个分析产物仍在树上。它们既不被训练/评测链路使用，又持续制造"按旧路径复跑"
的错觉；同时若干留存入口还从这些模块里取函数（FK、主轴修复、support geometry、实测关节序），
所以"直接删"会打断现役工具。

## 恢复口径（唯一入口）

两份清单：`rl_exp/out/archive/pre-refactor/manifest.json` 与 `manifest-part2.json`，共 **6648** 条。
每条字段为 `rel`（仓库相对路径，正斜杠）、`size`、`sha256`、`recovery_source`，以及：

- `recovery_source = "git_tag"`（522 条）：附 `blob_oid`，字节可从 tag `archive/pre-refactor` 取回：
  `git cat-file blob <blob_oid>` 或 `git checkout archive/pre-refactor -- <rel>`。
- `recovery_source = "local_archive"`（6126 条）：附 `local_path`，即
  `rl_exp/out/archive/pre-refactor/<rel>`（该目录被 `.gitignore` 忽略，属本机归档）。

同一 `rel` 在 tag 与本地归档中字节可能不同时（如 `work/archive/2026/ARCH_PLAN.md`），本地归档是
tag 之后的权威版本；按条目的 `blob_oid` 或 `local_path` 恢复，不按路径推断来源。删除前两份清单
逐条反向核验（5958/5958、690/690），复查剩余候选 0。

## 保留集（此处不重复列表）

`work/legacy-entrypoint-cleanup.md` 记录过完整白名单，但它随本次收尾删除；现役集合以仓库实际树为准：
`rl_exp/{lizard2_v7.py,robots,lizard2_round_feet,lizard2_palm_spatial,locomotion,tools}`、
`ablation_harness`（探针/判定/协议 + v7 结果与视频）、`work/*.md`、`acceptance/records/`。

白名单在实施中被两处漏项打回，补删 690 个后补齐：

- `two_foot_trim` / `support_report` 真依赖 `lizard2_round_support_geometry.py`、`pose_target_solver.py`、
  `check_self_collision.py`（原 CLI 已退网，只留 `load_urdf`/`read_obj`/`chain_up`/`fk`）。
- 圆足导出的上游源件 `rl_exp/lizard2_palm_spatial/`（URDF + meshes，12.5 MB）被导出以
  `FORMAL_SHA` 定住，必须留在树上。

## 验证（全部本机实跑）

| 项 | 结果 |
|---|---|
| 默认 `pytest` | 9 passed |
| `pytest rl_exp/tools/verify rl_exp/tools/diagnose` | 46 passed（13 subtests） |
| `pytest -m sim rl_exp/locomotion/tests/test_v7_experiment.py` | 1 passed |
| `check_terrain_split_source.py` / `check_split_probe_wait.py` | 退出 0 |
| `lizard2_round_feet_usd.py --formal_dir` | `pass=true`，`unresolved=[]`，正式目录零改动，且与 `MEASURED_*_SHA256` 一致 |
| `--repair`（新导出→URDF→USD 后） | 修前恰好 5 处主轴失败（`lf_elbow`/`rf_elbow`/`tail1_pitch`/`rl_knee`/`rr_knee`），修后 `pass=true` |
| `lizard2_round_feet_export.py` | 上游 .blend 只在归档中、或 `--skeleton` 指向副本时均 `ROUND_FEET_EXPORT_OK` |
| `column_coupling_probe.py selftest` | 全 PASS |
| 归档 ZIP 复读 | 逐文件摘要 20/20；`compare` 复现 `stairs_20cm` 第 10 步与 `rough_b` 第 48 步分叉 |
| `lizard2_shank_use_probe --leg_drive_preflight` | `LEG_DRIVE_PREFLIGHT_OK`，PhysX 运行时 26 轴序与 `MEASURED_JOINT_ORDER` 逐位一致 |

## 实施中修正的缺陷（不是"按计划完成"）

1. `column_coupling_probe.capture()` 切到 `lizard2_v7.make_env_cfg()` 后漏绑头部触地传感器：
   换 generator 地形后 `GroundPlane/CollisionPlane` 过滤匹配为 0，构造环境即
   `AttributeError: 'NoneType' object has no attribute 'filter_count'`。补
   `suites.bind_head_ground_to_terrain(cfg)` 后同一命令 `metadata.json` 为 `complete`。
   这条是审阅指出的，此前只跑 selftest 与旧数据 compare 不足以证明 capture 可用。
2. 白名单曾把 `rl_exp/tools/{diagnose,verify}` 整目录放行，导致 690 个旧脚本漏删；二次枚举补齐。
3. 候选审计把 `conversion.log` 当必绑输入，但该文件来自旧流程的 shell 重定向，新转换不产生；
   已从绑定表移除，并在 `--export_dir` 指向正式资产目录时直接拒绝。
4. 圆足导出的 skeleton 绑定原先比对路径（`Path(build['candidate']).resolve() == skeleton`），
   与相邻的 `locate()` 回退不一致，传副本/迁档即误报；改为只比对摘要。

## 边界

- `acceptance/records/` 是历史记录，只读不改写，其内部路径指向退网文件属预期。
- 归档目录 `rl_exp/out/archive/pre-refactor/` 被 `.gitignore` 忽略：它是本机归档，不是备份；
  需要异地留存时应另行备份该目录。
- `rl_exp/lizard2_palm_spatial/lizard2_palm_spatial.usda` 零引用，已随之退网；URDF 与 meshes 保留，
  因为圆足导出对它们做字节绑定。
