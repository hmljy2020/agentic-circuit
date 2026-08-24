# Superscalar NPU 阶段性总结

日期：2026-08-24

阶段状态：M0、M1 固定验证配置已完成；M1 的 StateArray/结构化 ACIR 优化主线已收口，
M2 尚未开始。

## 1. 当前做到哪里

目前已经从 primitive 语义验证推进到一个可运行的 L0 token 级 superscalar NPU 调度核。
这还不是完整 NPU，但已经包含动态调度最关键的控制结构，并且走通了完整工具链：

```text
ACIR 解析与验证
  → canonicalize/CSE
  → topology freeze
  → ACIR→ACSim
  → C++ 生成与编译
  → gfsim 周期仿真
```

### M0：语义与测量基线

M0 用三个独立模型确认了 Queue、event queue、固定优先级仲裁和 `ac.try_transfer` 的核心语义：

- Queue 的读写遵循 committed-state snapshot，本 tick 的写入到下一 tick 才可见；
- event queue 可以表达固定完成时间，且下游背压不会造成事件丢失或重复消费；
- `ac.try_transfer` 能把 source 的旧 head 原子地移动到 destination，输出满时两边都不更新；
- `ac.arbitrate` 可提供确定性的固定优先级选择；
- 同时建立了逐周期 trace、守恒检查、确定性检查以及 IR、耗时、RSS、ticks/s 的测量方法。

### M1：Superscalar 调度核

M1 实现了固定 2-wide 配置的调度器：

- 2-wide dispatch、issue、completion 和 retire；
- 8-entry issue window、8-entry ROB、16 个逻辑寄存器；
- `Scalar/VEC/CUBE/DMA-token` 四类执行路径，固定 latency 分别为 `1/2/8/4` cycle；
- producer map 和 RAW 依赖跟踪，同 bundle 的 lane1 能看到 lane0 rename；
- oldest-ready 乱序发射、FU 占用和 completion bandwidth reservation；
- 乱序完成、严格顺序退休以及 window/ROB/FU 的全链背压；
- event completion 与显式 CUBE 8-stage pipeline 逐周期差分验证。

16 条验收 workload 在 29 ticks 内产生 64 条阶段 trace。被 CUBE RAW 阻塞的老指令不会阻塞
无关年轻指令，多种 FU 能重叠执行；指令可以乱序完成，但最终严格按程序顺序退休。

## 2. 为 ACIR/ACSim 补齐的通用能力

### 2.1 原生 StateArray

新增了 provider-free 的 `ac.state_array`、`ac.state_read` 和 `ac.state_write`，覆盖 dialect、
parser/printer、verifier、process planning、ACIR→ACSim、C++ codegen、runtime 与统计。

StateArray 明确表达了：

- 固定容量、元素类型和读写端口；
- 动态索引访问；
- 所有读取观察同一 committed snapshot；
- 写入先形成 proposal，在 Xfer 边界验证端口、地址和写冲突后原子提交；
- packet 和标量元素都直接生成 `gfsim::StateArray<T>`，无需 extern binding/provider。

这使 window、ROB、producer table、completion ring 和 CUBE pipeline 不必再展开为大量不同名字的
scalar state，同时保留了硬件端口和原子提交意图。

### 2.2 紧凑 bounded `scf.for`

编译链现在能够保留 bounded `scf.for`，不再按静态 trip count 复制 process action。支持：

- induction variable 和动态 StateArray 索引；
- `iter_args` 归约及 loop result；
- loop result 驱动后续无结果 `scf.if`；
- 循环内嵌套的纯 `func.call`；
- 在 ACSim 中用显式 bounded CFG backedge 表达同 tick 循环。

因此 oldest-ready、first-two-free、window 更新和 ROB 更新都已改为结构化循环，而不是 Python
生成的 N 路比较/select 树。

### 2.3 StateArray 稀疏提交与 runtime 热路径

状态更新从“每 tick 无条件重写所有 entry”改为 guarded sparse commit：

- producer table 只提交 completion/dispatch 真正改变的 entry；
- completion ring 只合并 cursor 和两个 issue 候选；
- window、ROB、FU、CUBE pipeline 只在字段实际变化时写入；
- 同 entry 的多个候选先确定最终值，再产生至多一个 proposal；
- runtime 写冲突查询改为 O(1)，epoch 结束只清理实际触碰的端口和 proposal；
- 同一 StateArray 在一个 epoch 内缓存 commit-participant 注册。

### 2.4 Canonicalization、CSE 与记录构造

- topology freeze 前执行 `canonicalize,cse`，消除重复纯 SSA 计算；
- 删除常量 false 的 `ac.state_write`；
- 复用同 block、同 array/index/port/type 的精确重复 read；
- 完整 next-record 直接使用一次 `ac.record.create`，不再串联多个 `record.with`；
- packet helper 使用原地 field set，减少中间 packet 复制。

这些优化只消除可证明的冗余，不合并不同地址/端口的访问，也不弱化运行时冲突检查。

### 2.5 C++ CFG 生成

多 block process 的活跃 SSA 值由 `std::optional`/`reference_wrapper` 改为有类型的局部变量和
引用指针，CFG 边直接赋值；合法 CFG 保证到达 block 前参数已经由前驱定义。这样保留显式
控制流，同时让 C++ 编译器更容易消除搬运和 dispatch 开销。

## 3. 优化效果

以下以 compact M1 迁移前的同一语义模型为基线，最终版本仍保持
`16 instructions / 64 traces / 29 ticks`，且连续两次输出逐字节一致。

| 指标 | 优化前 | 当前 | 变化 |
|---|---:|---:|---:|
| raw ACIR 行数 | 3,222 | 1,189 | -63.1% |
| optimized ACIR 行数 | 2,516 | 1,013 | -59.7% |
| ACSim 行数 | 3,424 | 1,188 | -65.3% |
| generated C++ 行数 | 24,406 | 16,443 | -32.6% |
| C++ 生成/内部编译 | 35.86 s | 8.66 s | -75.9% |
| cxxgen peak RSS | 522,420 KB | 298,436 KB | -42.9% |
| 空载仿真速度 | 6,076～6,083 ticks/s | 26,547～26,616 ticks/s | +336%～338% |
| StateArray committed writes | 1,595（旧模型推导） | 250（当前实测） | -84.3% |

当前完整产物规模为：raw ACIR 85,692 B、optimized ACIR 61,099 B、frozen ACIR
254,117 B、ACSim 270,497 B、generated C++ 646,622 B。完整 M1 验收中实测最高 RSS 为
326,808 KB，低于 1.9 GB 的执行限制。

性能提升不来自把调度器替换成外部行为 provider，而来自保留结构化循环、减少静态复制、
稀疏提交状态以及降低生成 C++ 的 CFG 搬运成本。因此 ACIR 中的调度和状态语义仍然可见、
可验证，也保留了继续探索 RTL lowering 的基础。

## 4. 验收状态

统一验收命令为：

```bash
./examples/chao/superscalar/m1/run.sh
```

最近一次完整执行结果：

- M1 parser、verify、canonicalize/CSE、freeze、ACIR→ACSim、C++ 生成/编译/链接、语义和
  benchmark：PASS；
- StateArray runtime：5/5 PASS；
- 本轮定向 lit：6/6 PASS；compact-loop 独立组：4/4 PASS；
- gfsim 全量单测：208/208 PASS；Compiler Driver：7/7 PASS；
- 全量 lit：117/125 PASS。

全量 lit 剩余 8 项均报 activation edge 与静态依赖不完全一致，失败集合与本轮优化开始前相同，
位于工作区并行进行的 Flow/activation 改动区域。本轮没有跳过或弱化 verifier，因此不能把全仓
回归写成已全部通过。

## 5. 当前认识与遗留问题

### 已验证的方向

1. `StateArray + bounded loop + guarded commit` 是表达 issue window、ROB 和表结构状态的有效
   通用组合，不需要为 NPU 调度器增加专用 op。
2. ACIR 保留结构化表示后，后端仍可以生成低层 CFG，但不必先在 Core IR 中静态展开；这同时
   改善了人类可读性、编译产物规模和仿真速度。
3. event queue 适合表达固定时间的 completion，但 FU 的 II、capacity 和完成带宽仍需显式状态
   与 reservation 建模，不能把 event queue 本身当成完整硬件 resource。
4. 优化必须同时比较周期语义、IR/C++ 规模、编译时间、RSS 和 ticks/s；只让 IR 变短并不足以
   证明后端更高效。

### 尚未解决

- `ac.resource` 仍缺少通用 acquire/release/complete 执行语义；M1 的 FU 占用逻辑因此较冗长；
- resultful `scf.if` 尚未支持真正的 merge block/phi lowering，不能对含副作用分支简单改写成
  eager `arith.select`；
- event queue 没有声明每周期 dequeue width，M1 通过显式 completion reservation 保证双宽；
- 当前只验证固定 2-wide、8-entry window/ROB 配置，生成器尚未完成宽度和容量参数化 sweep；
- M1 仍是 token 模型，没有真实寄存器值、TileReg、bank/端口冲突、DMA 数据移动、Cache 或 HBM；
- 全仓 activation/Flow 的 8 个回归失败仍需由对应改动收口。

## 6. 下一阶段建议

下一步进入 M2，但应先冻结当前 M1 指标作为不可回退基线。M2 优先让 Scalar/Vector register
和 TileReg 携带真实值，并显式加入读写端口、bank 冲突、ready/ownership 与 bypass。每完成一个
小功能，都继续审视：现有 StateArray/Queue/process 组合是否清晰，是否需要标准组件、
canonicalization/lowering 优化，或确有必要增加端口化 resource 等通用 primitive。

在扩大模型前，还应补做 `window/ROB = 4/8/16`、`width = 1/2/4` 的规模 sweep，以确认当前
结构化表示和仿真性能随参数增长时仍然可控。

详细语义结果见 [`REPORT.md`](REPORT.md)，逐项优化过程与历史数据见
[`OPTIMIZATION_LOG.md`](OPTIMIZATION_LOG.md)，任务验收状态见
[`STATE_ARRAY_OPTIMIZATION_PLAN.md`](STATE_ARRAY_OPTIMIZATION_PLAN.md)。
