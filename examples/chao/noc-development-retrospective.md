# NoC 开发复盘：从功能打通到高效微结构探索

更新时间：2026-08-22

## 1. 总体判断

NoC 开发没有走错方向。它成功验证了 AC 的核心理念：

- 微结构、状态和资源可以显式进入 IR；
- 同一模型可以贯通 ACPy、ACIR、Frozen ACIR、ACSim、C++ 和 runtime；
- runtime 不需要知道 Mesh、Ring 或 XY routing；
- Python 可以作为实验控制器，通过 `model.step()` 驱动编译后的模型；
- Packet、Queue、仲裁、背压和统计可以组合成真实可执行系统。

但 NoC 也暴露出当前架构的主要瓶颈：

> AC 已经具备“表达和执行微结构”的能力，但尚未形成适合大规模自动化探索的紧凑编译与仿真架构。

当前已经到达一个架构转折点。继续增加 VC、multi-flit、adaptive routing 等功能，
会进一步放大现有的 IR 和代码展开问题。下一阶段应暂缓 NoC 功能扩展，优先改善
通用 IR 抽象、结构复用、编译缓存和仿真内核。

## 2. 开发历程与关键决策

### 2.1 从 NoC 声明到完整可执行链路

最早的问题是 stdlib 中的 Router、TrafficSource 和 Sink 只有声明，没有完整 lowering
和 runtime 语义。

采取的方案是增加 compiler-native `RingNoC` 和 `MeshNoC`，由 ACPy lowering 在编译期
生成 Queue、Link、Resource、Router process、Local injection/ejection、routing 和
arbitration 逻辑，从而打通：

```text
ACPy → ACIR → Frozen ACIR → ACSim → C++ → executable
```

第三方评价：

- 作为 MVP，这是正确且务实的选择；
- 它证明了 AC 的通用组件足以构造 NoC；
- 但整个网络被生成为一个 specialized module，每个 Router 的完整逻辑被复制，扩展性不足。

这是一个适合“证明能做”的实现，不应直接成为长期规模化实现。

### 2.2 Ring 闭环和 module-cycle OOM

Ring 涉及闭环。如果通过模块递归或零延迟连接表达，容易形成 module instantiation
cycle。最终实现让每条 directed link 都成为有状态 Queue，Ring 的环发生在 Queue
网络中，不形成 module instantiation cycle。

同时修复了 ownership 分析在检测 cycle 前递归展开导致的 OOM。

第三方评价：这是一个应该长期保留的设计。反馈路径必须经过显式状态，不能依赖组合
环或模块递归。它既符合硬件语义，也有利于 verifier 和调度器。

### 2.3 静态 ACPy 与运行时流量注入

一开始曾考虑在 ACPy process 中编写完整 traffic generator，但 ACPy 是静态
elaboration 环境，不适合用普通 Python 循环逐 tick 控制已经编译的模型。

后续引入了：

- 严格版本化的 C ABI；
- `ModelRuntime.step()`；
- host ingress/egress；
- Python TrafficManager；
- warmup 和 measurement window；
- Bernoulli injection、pending retry 和统计采集。

这形成了清楚的职责划分：

```text
Python
  - 实验控制
  - 流量策略
  - 参数扫描
  - 数据采集

编译模型
  - 微结构状态
  - Queue/backpressure
  - arbitration
  - cycle progression
```

第三方评价：这是 NoC 开发中最成功的架构决策之一。Python 没有绕过 Queue 或调度
屏障，runtime 也没有获得 NoC 专用知识，非常适合作为未来 DSE 控制层的基础。

### 2.4 General Packet 的贯通

Packet 没有被做成 NoC 专用消息，而是先作为通用 ACIR 类型打通：

- 定宽布局；
- field get/with；
- serialize/deserialize；
- Queue/Flow；
- host byte ABI；
- NoC 从指定字段读取 destination。

第三方评价：这个实现顺序正确。Packet 是通用数据结构，不应该依附于 NoC。

当前边界也定义得比较清楚：

- 一个 Packet 是一个原子 Queue 元素；
- Packet 不等于 multi-flit packet；
- 没有 head/body/tail；
- 没有跨 flit 的 VC ownership。

不应通过字段命名或 payload 大小假装已经支持 multi-flit。

### 2.5 Queue depth 与 VC ownership 的混淆

BookSim 对比初期，曾尝试把 Queue depth 调成 1，以近似 VC 被长时间占用。后来确认：

```text
buffer capacity != VC ownership duration
```

Queue depth 只决定能缓存多少元素，不能表达 flit 已离开当前 buffer、但 downstream VC
尚未释放，或者仍在等待 tail credit。

因此后续增加了：

- 显式 egress owner；
- reverse credit Queue；
- credit delay；
- VA/SA pipeline state；
- `wait_for_tail_credit`。

第三方评价：后来的修正是正确的。但这个过程说明，微结构状态不能通过调整无关参数
近似。DSE 工具尤其需要保持参数正交，否则搜索结果很容易被误解。

### 2.6 用 Queue 表达内部状态

为了不增加 NoC runtime 黑盒，当前把 VC owner、pipeline phase/countdown、round-robin
pointer 和 delayed credit 都存入普通 Queue。每 tick 执行：

```text
try_recv state
→ scalar combinational logic
→ try_send next state
```

这个方案的优点是：

- 复用了现有 Queue/runtime；
- reset、ownership 和调度机制统一；
- 状态在 ACIR 中可见；
- 快速打通了功能。

缺点是：

- 标量 register 被建模成完整 Queue runtime object；
- 每次更新产生多组 invoke、capture 和 dispatch；
- Queue depth 被部分用于实现 epoch 隔离；
- 使用 `100`、`200`、`-128` 等 magic integer 编码状态机；
- IR 和 C++ 明显膨胀。

第三方评价：这是合理的过渡实现，但不适合作为长期微结构状态模型。AC 需要一个明确
的通用 state cell/register 语义，定义 read-old/write-next、tick commit、reset、
ownership、typed value 和可选 enable。它不是 NoC primitive，而是流水线、控制器、
计数器和协议状态机都能使用的基础能力。

### 2.7 Round-robin 展开与 4×4 OOM

最初 round-robin 在 Python lowering 中被展开为 pointer 比较、rotated priority、
blocked prefix、selected、next pointer 和大量 `andi/ori/select/cmpi`。

2×2 可以运行，但 4×4 input-queued 模型在 ACIR→ACSim 阶段触发内存爆炸。

最终解决方案是扩展通用：

```mlir
ac.arbitrate round_robin
```

它具有显式 pointer 输入、one-hot grants、next pointer 输出、ACIR verifier、紧凑
ProcessState action、单个 ACSim invoke 和 C++ helper。同时修复了 ProcessState
canonical JSON 一次性构造大对象造成的内存峰值。

结果是 4×4 lowering 峰值降至约 194 MB，并完成全链编译和运行。

第三方评价：这是一个很有价值的正面样例。稳定、通用、可验证且展开代价高的语义，
应作为 primitive 保留到后端，而不是在前端提前变成标量网络。

但它只解决了 round-robin 本身。Router 的 route/request/SA/transfer/state-update 仍然
展开，所以代码规模问题只是缓解，没有根治。

## 3. 当前代码膨胀说明了什么

4×4 input-queued Packet Mesh 的实际生成规模为：

| 阶段 | 行数 | 大小 |
|---|---:|---:|
| ACIR | 9,075 | 806 KB |
| Frozen ACIR | 8,466 | 2.11 MB |
| ACSim IR | 13,130 | 1.64 MB |
| 生成的 C++/headers | 39,971 | 1.80 MB |
| process C++ 部分 | 34,047 | 1.39 MB |

ACIR 中还包含：

```text
264  ac.try_transfer
2264 arith.andi
1384 arith.cmpi
680  arith.select
```

ACSim 中包含 1,209 个 `acsim.invoke`。

### 3.1 Router 候选矩阵按平方展开

当前每个 Router 枚举所有 ingress × egress：

```text
corner:   3 × 3 = 9
edge:     4 × 4 = 16
interior: 5 × 5 = 25
```

4×4 全网候选数为：

```text
4 × 9 + 8 × 16 + 4 × 25 = 264
```

每个候选又配套 route、owner、pipeline、space、grant 和 transfer 逻辑。因此当前复杂度
更接近：

```text
O(nodes × router_radix²)
```

而不是理想的线性端口处理。

### 3.2 Fixed-priority SA 仍在后端展开

VA round-robin 已经紧凑化，但 SA 的 fixed-priority resource arbiter 仍被转换成布尔
网络。因此只压缩了一部分 allocator。

### 3.3 Frozen metadata 被反规范化复制

Frozen ACIR 中大量空间来自 `ac.frozen_owners` 等 owner/path/specialization 元数据。
少数行超过 100 KB，属于元数据复制，不是真实微结构逻辑。

### 3.4 C++ 按 process 生成独立直线代码

16 个 Router 分别生成 process C++。相同 helper 被复制进多个 header，结构相似的
FlowSource/FlowSink 也缺少共享。process C++ 占全部生成源码的大部分。

## 4. 值得长期保留的方案

从第三方视角看，以下原则是稳固的：

1. **Runtime 保持通用。** 不加入只理解 Mesh、Ring 或 XY routing 的专用执行引擎。
2. **结构和状态保持显式。** Link、Queue、credit、owner、resource 不能藏进无法分析的黑盒。
3. **Python 负责实验控制。** `model.step()`、host ingress 和 TrafficManager 是未来自动化探索的正确基础。
4. **Packet 是通用类型。** 不为 NoC 特化数据类型系统。
5. **反馈必须经过显式状态。** Queue 环而不是 module cycle，应继续作为基本规则。
6. **坚持真实端到端验收。** verifier、freeze、ACSim、C++、runtime、守恒和确定性都需要验证。
7. **只公开真正支持的参数。** VC=1、atomic packet 等限制明确，比虚假的可配置接口更健康。

## 5. 需要调整的做法

### 5.1 Textual generator 承担了过多微架构实现

当前 Python lowering 不仅决定拓扑，还直接生成完整 Router 状态机和数千个 SSA
operation。

长期应让 generator 负责参数验证、拓扑、节点和 channel 实例化、静态 route descriptor
及 primitive 组合，而不是负责手写状态编码、仲裁算法、完整 request matrix 和所有
next-state 逻辑。

### 5.2 不应继续以“小布尔 primitive”解决规模问题

新增 `and/select/cmp` 一类 primitive 没有意义。值得增加的是中等粒度、通用且后端
不展开的语义，例如：

- state cell/register；
- resource allocator；
- batch switch transfer；
- table-driven route/request generation。

### 5.3 也不应直接增加 `MeshRouter` 黑盒

一个覆盖 routing、VA、SA、credit、buffer 和 timing 的 `ac.mesh_router_step` 虽然最省
代码，却会固化某一种 NoC、降低 verifier 能力、阻碍替换 allocator 或 flow-control，
也无法被非 NoC 微结构复用。

合适的抽象位置介于“单个布尔门”和“整个 Router”之间。

### 5.4 BookSim 对比开始得偏早

现有曲线能说明趋势，但不能证明周期级等价，因为双方仍有 event ordering、switch
traversal、credit 可见周期、allocator 顺序、injection trace 和统计口径差异。

Benchmark 应被定位成微结构语义校准工具，而不是当前阶段的正确性证明。

### 5.5 测试过多依赖文本形态

统计特定 Queue 名、字符串或 `try_recv` 数量适合 MVP，但会妨碍后续合法压缩。应逐步
转向语义报告：Router 数量、channel 数量、state 数量、allocator policy/width、
candidate matrix、ownership、pipeline stage 和 transfer exclusivity。

## 6. 面向自动化微结构探索的目标架构

AC 最终需要的不只是“能编译一个模型”，而是：

```text
参数空间
   ↓
快速生成或复用模型
   ↓
快速编译或直接装载
   ↓
高吞吐仿真
   ↓
统一指标采集
   ↓
设计点比较、筛选和复现
```

### 6.1 ACPy：设计空间与结构生成

负责静态结构、参数约束、design-space declaration、topology、component composition
和 workload-independent specialization。

### 6.2 ACIR：紧凑微结构语义

建议至少具备：

```text
Queue/channel
State cell/register
Resource allocator
Batch transfer
Packet/record
Pipeline/timing
Explicit resource ownership
```

这些 primitive 必须跨领域可复用，完整描述状态和副作用，能被 verifier 理解，并保持
到 ACSim，而不是在中途重新展开。

### 6.3 ACSim：数据驱动的执行计划

当前逐 SSA invoke 的方式适合一般性验证，但不一定适合大规模 DSE。更理想的形式是：

- 相同 primitive 使用共享 kernel；
- 实例差异通过静态 descriptor/table 表示；
- 状态放在连续数组中；
- 避免每个实例生成独立 C++ 函数；
- 避免每个布尔 operation 都成为 dispatch unit；
- 保留确定性的 tick/commit barrier。

### 6.4 Experiment runtime：探索和测量

需要逐步形成 compile artifact cache、specialization fingerprint、workload trace 输入、
warmup/measurement window、counter snapshot/reset、参数扫描、reproducible seed、统一结果
输出和多个 design point 的批处理。

现有 `ModelRuntime.step()` 和 Python TrafficManager 已经是这一层很好的起点。

## 7. 建议的实施优先级

### P0：建立工具自身的性能基线

在继续增加功能前，对 2×2、4×4 和未来更大结构固定记录：

- ACIR/Frozen ACIR/ACSim operation 数和大小；
- C++ 行数和 executable 大小；
- 编译时间和 peak RSS；
- simulation ticks/s；
- 每 tick 的 runtime invocation 数。

没有这些指标，就无法判断一次“优化”只是缩短了文本，还是改善了真实探索效率。

### P1：增加通用显式 state primitive

替换用 Queue 保存的 owner、pipeline phase、countdown 和 RR pointer。这是 NoC、流水线、
cache controller、DMA 和协议状态机都需要的基础能力。

### P2：将 allocator 和 batch transfer 紧凑化

可以考虑类似：

```text
ac.allocate
  requests
  resource sets
  policy
  optional state
→ grants, next_state
```

以及：

```text
ac.transfer_batch
  ingress queues
  egress queues
  grants
→ fired mask
```

它们应一直保留为紧凑 ACSim action，并使用共享 C++ kernel。这比增加 `MeshRouter` 更
通用，也比 264 个独立 `try_transfer` 更紧凑。

### P3：修复后端结构复用

包括 helper 全局按签名去重、Router process implementation 按结构共享、实例坐标和
Queue 映射进入 descriptor、FlowSource/FlowSink 共享实现，以及 Frozen ownership 元数据
改为共享表引用。

### P4：加入编译缓存和多 design-point 运行

对参数进行分类：

- 改变结构的参数产生新 specialization；
- 只改变初始状态或实验条件的参数使用 runtime 配置；
- 相同 specialization 直接复用编译产物。

对于 DSE，很多参数扫描不应该每次从 ACPy 重新编译全部 C++。

### P5：之后再扩展 NoC 语义

等紧凑基础设施稳定后，再考虑 multi-flit、VC > 1、link latency、speedup、adaptive
routing、QoS 和更准确的 BookSim pipeline。否则每增加一项功能，都会乘到当前已经
展开的候选矩阵上。

## 8. 最终评价

NoC 项目最大的价值不是交付了一个 Mesh 模拟器，而是暴露了 AC 从“可执行 IR”走向
“高效微结构探索平台”必须解决的核心问题。

目前可以客观概括为：

| 维度 | 评价 |
|---|---|
| 语义完整性 | 较好 |
| 端到端可执行性 | 较好 |
| 验证和可复现性 | 较好 |
| 微结构可组合性 | 初步具备 |
| IR 紧凑性 | 不足 |
| 后端结构复用 | 不足 |
| 编译吞吐 | 尚不适合大规模 DSE |
| 仿真吞吐 | 需要正式基线和优化 |
| 自动化实验管理 | 已有原型，尚未形成系统 |

最重要的战略建议是：

> 不要把 AC 发展成拥有大量专用组件黑盒的模拟器，也不要继续依赖前端展开所有微结构
> 细节。应建立一套少量、通用、中等粒度、可验证、能够贯穿到共享 runtime kernel 的
> 微结构 primitive。

`ac.arbitrate round_robin` 已经证明这条路线有效。下一步应把同样的方法推广到 state、
allocator 和 batch transfer，并同时建设缓存、性能指标和实验管理能力。这样 AC 才能
从“能表达一个设计”真正迈向“高效探索大量设计”。
