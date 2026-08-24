# M1 StateArray 优化进度

本文件跟踪从结构化 ACIR 到高效 StateArray 仿真的长程优化。真实数据与关键设计决定追加到
[`OPTIMIZATION_LOG.md`](OPTIMIZATION_LOG.md)。所有构建和验收使用 `ulimit -v 1900000`、
单线程；失败必须如实记录。

## 完成条件

- ACIR 保留紧凑的 bounded `scf.for`，ACSim/C++ 不按 entry 数复制循环体。
- `scf.for iter_args` 可表达 first-free、oldest-ready、count 等归约。
- M1 的 window、ROB、producer、FU、CUBE pipeline 和 completion ring 使用结构化访问与
  guarded sparse commit。
- StateArray runtime 冲突检查为 O(1)，commit/reset 为 O(有效访问数)。
- M1 保持 16 instructions、64 traces、29 ticks，且两次输出逐字节一致。
- 相对重新测得的 O1～O3 基线：optimized ACIR/C++ 行数下降至少 20%，cxxgen 时间下降
  至少 10%，ticks/s 提升至少 5%，committed writes 下降至少 30%。

## 进度

| ID | 内容 | 状态 | 验收摘要 |
|---|---|---|---|
| S0 | 锁定基线与记录格式 | DONE | 3222/2516/3424/24406，16/64/29 |
| S1 | StateArray snapshot/proposal/Xfer 语义回归 | DONE | 5 runtime tests + ACIR lit |
| S2 | 4/16/64/256 compact-loop 微基准 | DONE | 4 个 bound、4 份 C++ read call site |
| S3 | compact-loop lowerable subset | DONE | 静态正步长/上限诊断与 bounded backedge |
| S4 | ProcessPlan 不展开静态循环 | DONE | 单份 body，显式 bounded backedge |
| S5 | 同 tick ACSim CFG 与 C++ lowering | DONE | 无 suspend、两个 StateArray call sites |
| S6 | `iter_args`、`scf.if` 与纯调用 | PARTIAL | `iter_args`、无结果 if、嵌套 pure call 已通过；result-if 留作后续能力 |
| S7 | StateArray access canonicalization | DONE | false write 删除、同 block精确重复 read 复用 |
| S8 | M1 CUBE/FU/completion ring | DONE | 周期 oracle、三候选 ring、guarded commit |
| S9 | M1 producer/window/ROB | DONE | issue/first-free/oldest-ready 与 window/ROB 更新均为结构循环 |
| S10 | StateArray runtime 热路径 | DONE | O(1) 冲突、稀疏清理、epoch 注册缓存 |
| S11 | 规模与完整回归 | PARTIAL | 全部规模/性能门槛达标；全量仍为 117/125（外部 activation 回归） |

## 每步记录要求

每步记录起始 worktree、语义决定、关键改动、测试命令和退出码、before/after 指标、发现的
缺陷、遗留风险及下一步。仅能编译不能视为完成；仍被静态展开的循环不能标记为 compact。

## 本轮收口结论

StateArray 优化主线已经完成：紧凑循环、动态端口、稀疏 proposal、O(1) 冲突检查和 M1
结构化迁移均有真实验收。S6 仅剩通用的 resultful `scf.if`；它不是当前 M1 的依赖，不能用
简单 `arith.select` 在含副作用分支上替代，因此单列为下一轮 compiler CFG/phi 能力。
S11 未标 DONE 的唯一原因是工作区并行 activation/Flow 修改造成的 8 个全量回归失败。
