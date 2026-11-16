# TPC-DS SF1/SF3/SF10 维护扩展性、RelBench 4 次截断公平性与 G3 表达覆盖补证

本目录保存针对 PVLDB 审稿意见开展的三项零模型调用（zero-LLM）实证补证结果，对应论文第 6.2 节与第 6.6 节：

1. **TPC-DS SF1 → SF3 → SF10 共享验证与修复扩展性**（`scaling-summary.json`、`scaling-reports.tgz`）：
   - 在 `noctis`（48 逻辑 CPU Hygon C86 5390、98 GiB RAM、PostgreSQL 18.6）上按 `dsdgen` 标准比例生成并装载 `SF1`（`store_sales` 2,880,545 行，0.62 GB）、`SF3`（8,640,037 行，1.76 GB）与 `SF10`（28,802,398 行，5.77 GB）。
   - 基于 Q2/Q4 导出的 5 条共享 TPC-DS 定义，通过 `agentdb-mid replay-bench` 评测五类代表性更新：常规追加 `append`、原地 `UPDATE` 更正 `correct`（5.5 万 / 16.7 万 / 55.6 万行）、维表历史拉链 `dimhist`、版本化重述 `revision` 与整行重复装载 `dupload`。
   - 为真实模拟数仓表级快照，`src/bench/replaybench.rs` 的 `copy_learning_snapshot` 对维表保留主键索引并对全部表执行 `ANALYZE`，管理与探查连接超时随 `--sql-timeout-secs` 对齐。
   - **主要结果**：`SF1`、`SF3`、`SF10` 上 MAVRA（`condition/snapshot`）均取得 `54/54`（100%）正确、零错误服务；查询条数随规模保持常数（`append`/`correct` 33 条 vs. 逐定义 73 条；`dimhist` 40 vs. 52；`dupload` 54 vs. 120；`revision` 80–82 vs. 171）。数据库耗时随行数呈线性至亚线性增长：`append` 为 `21.3s → 60.9s → 142.6s`（10 倍数据仅 `6.7×`），原地 `UPDATE` `correct` 为 `18.1s → 48.9s → 160.2s`（`8.9×`），维表修复 `dimhist` 为 `8.0s → 22.9s → 70.4s`（`8.8×`），去重修复 `dupload` 为 `32.1s → 93.8s → 319.1s`（`9.9×`，较逐定义快 `3.4–3.7×`），重述修复 `revision` 为 `54.5s → 172.6s → 651.5s`（较逐定义快 `2.7×`）。

2. **RelBench 4 次规划调用截断对照**（`relbench-4call-truncation.json`）：
   - 在 `rel-stack` 与 `rel-trial` 的全部三轮无记忆运行（每库 36 个截点 2–5 复用会话）上，将规划调用上限截断至与 MAVRA 复用阶段相同的 `≤ 4` 次（MAVRA 实际均值仅 `2.7` 与 `3.7` 次）。
   - 无记忆在两库复用阶段合法无泄漏提交均为 `0/36`（首次合法验证中位数需 `10` 与 `18` 次规划调用），五截点 `user-badge` / `user-engagement` AUC 由 `0.850` / `0.862` 跌至 `0.608` / `0.634`，`study-adverse` MAE / `study-outcome` AUC 由 `40.27` / `0.671` 退化至 `48.80` / `0.602`。

3. **$I$ 的表达边界与 G3 覆盖率统计**（`g3-coverage.json`）：
   - 在线核验会话在表别名规范化后 G3 拒收率为 `0/664`（早期 510 会话批次同为 `0/510`）；静态基准覆盖率为 SSB `13/13`（100%）、TPC-DS 独立模板 `58/99`（59%，`82/99` 含星型聚合块）、TPC-H 聚合块 `13/25`（52%）与 BIRD `financial` 聚合块 `12/20`（60%），多事实 CTE、相关子查询及 `1:N`/环状连接在 G3 零误纳回退给智能体。
