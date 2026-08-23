# M1 简短报告

日期：2026-08-23

状态：`DONE`（固定 2-wide 验证配置）

## 结果

M1 已形成可由公开 ACIR 入口解析、freeze、lower 到 canonical ACSim、生成/编译 C++ 并运行的
L0 superscalar NPU 调度核。模型使用 2-wide dispatch/issue/completion/retire、8-entry window、
8-entry ROB、16 个逻辑寄存器和 Scalar/VEC/CUBE/DMA-token 四类 FU。

验收 workload 共 16 条指令、64 个阶段 trace，在 29 ticks 内完成。检查结果为：

- 每条指令恰好 dispatch、issue、complete、retire 一次；所有阶段每 tick 宽度不超过 2；
- RAW consumer 严格晚于最新 producer completion；同 bundle 的 lane1 能看到 lane0 rename；
- 被 CUBE RAW 阻塞的 seq3 未阻塞独立的 seq4/5/6，出现真实多发射和 latency hiding；
- seq2/seq4 先于更老的 seq1 完成，但 retire 始终为 seq1→seq16；
- 四类 FU 均满足 `complete_tick = issue_tick + {1,2,8,4}`；
- completion reservation ring 防止不同延迟的 FU 在未来同 tick 产生超过双宽的完成；
- CUBE event completion 与显式 8-stage committed-state pipeline 逐周期、逐 tag 相等；
- 连续两次运行的 trace 字节完全一致。

## 新增的通用能力

为避免用 8 个不同名字的 scalar state 拼装 window/ROB，本阶段打通了 provider-free 的：

```mlir
ac.state_array @state element T entries N read_ports R write_ports W ...
%value = ac.state_read @state[%index] port %port : T
ac.state_write @state[%index] %value when %enable port %port : T
```

读取观察同一个 committed snapshot；guarded write 只产生 proposal，Xfer 边界前统一验证端口、
地址和同地址写冲突，全部合法后才提交。packet 和标量元素均由 native C++ codegen 生成
`gfsim::StateArray<T>`，无需 `module.extern` 或 binding/provider。

实现覆盖 dialect 声明、parser/printer、verifier、graph/process lowerability、process-state plan、
ACIR→ACSim、C++ 生成、runtime 和统计。额外修复了 packet StateArray 值穿过 `scf.if` CFG 时，
block argument 泄漏为裸 `!ac.packet`、导致 canonical ACSim 拒绝的问题，并加入回归测试。

## 验收证据

统一命令：

```bash
./examples/chao/superscalar/m1/run.sh
```

最终一次完整执行退出码为 0：semantic 与 benchmark 均 PASS，StateArray runtime 3/3，定向 lit
5/5。构建限制为 `ulimit -v 1900000`、单线程；实测最高 RSS 为 579,224 KB。

| 阶段 | 时间 / s | peak RSS / KB |
|---|---:|---:|
| ACIR verify | 0.34 | 66,740 |
| freeze | 0.47 | 69,824 |
| ACIR→ACSim | 4.07 | 505,268 |
| C++ 生成、内部编译和链接 | 45.63 | 579,224 |
| runner link | 3.26 | 327,680 |
| 10,000 tick benchmark | 1.77 | 55,168 |
| targeted lit | 11.44 | 250,576 |

| 产物 | 大小 | 行数 |
|---|---:|---:|
| ACIR | 234,043 B | 3,321 |
| frozen ACIR | 793,682 B | 3,313 |
| ACSim | 819,552 B | 4,455 |
| generated C++ | 1,358,669 B | 28,627 |

空载 10,000 tick 实测约 5,490 ticks/s。该数字是本固定展开调度器的仿真成本基线，不是 NPU
指令吞吐。

## ACIR 审视

1. `StateArray` 是必要的通用 primitive：它使索引、端口、snapshot 和提交边界都可验证；用
   Queue 或任意 process 局部变量替代会丢失硬件状态意图。
2. 当前 ACIR 仍将 8-entry window/ROB、16-entry producer map 和 9-entry reservation ring 完全
   展开。仅一个小调度核就生成 3,321 行 ACIR 和 28,627 行 C++，lowering 4.07 s、仿真只有
   约 5.5k ticks/s。后续优先研究 bounded-loop 专门 lowering、批量 StateArray read/write、
   record 字段访问融合和增量 next-state，而不是继续复制表达式。
3. `ac.resource` 尚无 acquire/release/complete 的通用执行语义。本模型用 FU `inflight`、II 和
   completion reservation 显式状态实现，正确但冗长。候选方向应是可复用的 reservation-table/
   capacity 标准组件或更通用的端口化 resource 语义，不应新增 NPU 专用 op。
4. event queue 本身不声明每周期 dequeue width。M1 显式只取两次，并用 reservation ring 在
   issue 前阻止未来三重冲突。这保持了固定 latency 和 RTL 亲和性，但写法很大；值得探索
   verifier 可理解的 multi-grant/带宽资源组合。
5. 一个大 process 让 observation/decision/commit 的周期边界正确，却让大量 packet SSA 跨
   `scf` merge。M2 应比较层次化多个 process 与单 process 的代码规模、唤醒和提交开销。

## 下一步

M2 先让 Scalar/Vector register 与 TileReg 携带真实值，并显式加入读写端口和 bank 冲突。
在扩大 NPU 前应先保存 M1 固定基线，做 4/8/16-entry window/ROB 与 1/2/4-wide 的生成规模
sweep；当前生成器只支持验证配置，参数化重构不能被描述成已经完成。
