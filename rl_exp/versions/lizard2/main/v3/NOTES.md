# lizard2 main/v3 运行记录入口

## 设计引用

目的与假设见 [PLAN.md](PLAN.md)。

## 本版重点变化

采用用户批准的候选机体，踝部只取消策略动作通道，保留可动关节与 PD。
完整差异及逐项理由唯一归 [diff.json](diff.json)。

## 实际执行与偏离

本轮只实施与自检；无训练 run、checkpoint 或训练覆盖参数，不冻结/tag。
实际命令、运行验证与限制归 `acceptance/records/2026-10-08-lizard2-v3-landing.md`。

## 结果回填

报告：`acceptance/records/2026-10-08-lizard2-v3-landing.md`。仿真/离线检查按该记录复读。

后续需求与文档状态核对：`acceptance/records/2026-10-09-lizard2-limit-requirement-and-status-sync.md`；本次仅更新文档，无新仿真或训练 run。

## 结论

本轮工程交付判定见报告；不把接口自检当作 mesh 碰撞、完整动作周期或策略效果验收。
