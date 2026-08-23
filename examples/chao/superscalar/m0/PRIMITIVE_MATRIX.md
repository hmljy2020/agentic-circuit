# M0 primitive 能力矩阵

本表只覆盖 M1 调度核直接依赖的控制能力。声明以
`include/acir/Dialect/ACIR/ACIROps.td` 为入口；自定义验证主要位于
`lib/Dialect/ACIR/ACIROps.cpp`，lowering 位于 `lib/Conversion/ACIRToACSim/`，native
执行和生成路径位于 `lib/gfsim/`、`lib/Analysis/ProcessState*` 与 `lib/CodeGen/`。

| 能力 | verifier/freeze | ACSim 与 C++ | M0/仓库证据 | 当前结论 |
|---|---|---|---|---|
| `ac.queue` | 检查容量、payload、协议和 ownership；freeze 固定 owner | 生成 `gfsim::Queue<T>` runtime object | `queue`；`native-queue` tests | 已打通 |
| `ac.try_send` / `ac.try_recv` | 检查目标、payload、process 与 await 结构 | compiler-known Queue invoke | `queue` | 已打通，soft failure |
| `ac.peek` / `ac.space` | 检查 Queue、返回类型及 await 约束 | native peek/free-slot invoke | `queue`、`arbitrate_transfer` | 已打通，只观察 committed state |
| `ac.await_queue` | 必须位于匹配失败路径并引用同一 Queue | lowering 为 readable/writable wake | 三个 case；`queue-await-invalid` | 已打通 |
| `ac.event_queue` | 检查 event payload、capacity、ordering 和 domain | 生成 `gfsim::TimedEventQueue<T>` | `event_latency`；event queue tests | 已打通；未声明读端口/dequeue width |
| `ac.schedule` / `ac.try_event` | 检查类型、目标和 matching false branch | native schedule/receive invoke | `event_latency` | 已打通，schedule 可 soft reject |
| `ac.await_event` | 必须引用匹配的 event queue | lowering 为 event-queue wake | `event_latency` | 已打通 |
| fixed-priority `ac.arbitrate` | 校验候选、resource、grant provenance 与 effect exclusivity | lower 为普通 `arith` 布尔 SSA | `arbitrate_transfer`；arbitrate tests | 已打通，无持久状态 |
| round-robin `ac.arbitrate` | 额外检查 i32 state/next-state | compiler-known round-robin helper | targeted arbitrate tests | 已打通 lowering；M0 无动态 case |
| `ac.try_transfer` | 检查不同同类型 Queue、grant provenance和单读写冲突 | native `Queue::tryTransferTo`，一次 Xfer 原子提交 | `arbitrate_transfer`；try-transfer tests | 已打通 |
| `ac.resource` | 检查 capacity、issue width、II、latency 和 lifecycle 声明 | 供 `ac.arbitrate` 静态冲突分析；无通用运行时 reservation object | `arbitrate_transfer`；resource tests | **未打通 acquire/release/complete 执行语义** |
| `ac.process` / suspension | 检查 process region、effect 和 suspension 位置 | 生成显式 PC/live-slot/wake 状态机 | 三个 case；process tests | 已打通当前控制流子集 |
| `ac.yield_sim` | process terminator | 唤醒到下一 tick | 三个 case | 已打通 |
| `ac.assert` | 条件必须为 i1 | 生成 runtime functional assertion | 三个 case | 已打通；只验证，不提供原子性 |

## 对 M1 的直接影响

- Queue、event queue、fixed-priority arbitration 和 atomic transfer 足以搭建 token 级调度核。
- `ac.resource` 目前不能独立表达“检查 FU 可用、占用、按 II 再发射、完成后释放”的执行过程；
  M1 必须先用显式状态组合，或在获得最小失败证据后提出通用 resource 执行语义。
- fixed-priority 会展开为组合 SSA；候选数增大时需要测量 IR 和生成 C++ 的线性膨胀。
- round-robin 的 next-state 仍需由模型持久保存，声明本身不会自动拥有调度状态。
- 同一 process 每 epoch 可连续消费多个 ready event；M1 若只允许固定 completion width，必须在
  模型中显式仲裁和限制，不能把 event queue 当作隐式单读端口 FIFO。
