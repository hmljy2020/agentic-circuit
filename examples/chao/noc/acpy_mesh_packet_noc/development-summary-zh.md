# ACPy Packet Mesh NoC 开发总结与后续设计建议

更新时间：2026-08-24

范围说明：本文基于已经提交并完成验收的 NoC/Packet/round-robin 里程碑，以及
[`noc-development-retrospective.md`](../../noc-development-retrospective.md) 的历史记录。
工作区中尚未完成验收的其他实验性改动不计入“当前已支持”能力。

## 1. 项目定位

`acpy_mesh_packet_noc` 的价值不只是实现了一个 Mesh NoC。它是 AC 项目的一个纵向
验证案例，用来回答以下问题：

1. ACPy 能否描述包含拓扑、队列、路由、仲裁、背压和流水线状态的微结构；
2. 这些描述能否完整经过 ACPy、ACIR、Frozen ACIR、ACSim、C++ 和 executable；
3. 编译后的模型能否由 Python 逐周期控制，并用于自动化参数扫描；
4. AC 能否产生可复现的饱和吞吐曲线，并与 BookSim 这样的成熟模拟器进行校准；
5. 当前 IR 和后端是否足够紧凑、高效，能够支撑大规模设计空间探索。

目前前四项已经形成可运行闭环，第五项暴露出明显不足。因此项目已经从“证明 AC 能
表达 NoC”进入“改善 AC 的通用微结构抽象和执行效率”阶段。

## 2. 当前已打通的系统

当前完整路径为：

```text
Python TrafficManager
  - injection rate / seed / destination
  - warmup / measurement
  - pending retry
              │ offer_bytes / take_bytes
              ▼
编译后的 Packet MeshNoC
  - host ingress / egress
  - Queue / backpressure
  - deterministic XY routing
  - VC owner / reverse credit
  - VA / SA timing
  - round-robin arbitration
              │
              ▼
ACPy → ACIR → Frozen ACIR → ACSim → C++ shared library
              │
              ▼
ModelRuntime.step()
```

Python 只负责实验控制，不能绕过模型中的 Queue、仲裁和 tick barrier。编译模型负责
所有微结构状态变化，runtime 不需要理解 Mesh、XY routing 或 BookSim。这一边界符合
AC 最终成为自动化微结构探索工具的目标。

## 3. 基础模型和固定语义

### 3.1 Packet

ACPy 中的消息定义为：

```python
@packet(endianness="little")
def Message(destination: i32, payload: i32) -> None:
    pass
```

它是一个 8 字节、不可变、定宽的原子值：

- `destination` 是 XY routing 使用的字段；
- `payload` 随 Packet 原样到达；
- host ABI 使用精确的 8 字节输入和输出；
- 一个 Packet 当前等于一个 Queue 元素，也等于一个 single flit；
- Packet 大小本身不会自动产生多个 flit、多个 link cycle 或 VC reservation。

### 3.2 Mesh

当前公开模型支持：

- 2×2 和 4×4 Mesh；
- node ID 为 `y * width + x`；
- deterministic XY routing；
- Queue depth 2；
- VC 数固定为 1；
- input/output speedup 固定为 1；
- Local injection 和 Local ejection；
- 非法目的地址不从 ingress pop；
- host 通过 `nodeN` 名称选择固定入口和出口。

### 3.3 验证标准

模型不仅检查“是否收到 Packet”，还检查：

```text
accepted_transactions
  == completed_transactions + queue_occupancy
```

以及：

```text
queue_occupancy_peak <= configured_depth
```

另外覆盖 Local、单跳、多跳、反向路径、错误 ejection、背压恢复、竞争、公平性、reset
和重复运行确定性。

## 4. 开发过程中遇到的问题和解决方案

### 4.1 问题一：stdlib 只有 NoC 相关声明，没有可执行语义

早期的 Router、TrafficSource 和 Sink 更接近占位 schema，没有完整 lowering 和 runtime
实现，无法仅通过组合这些占位组件得到可执行 NoC。

#### 解决方案

实现 compiler-native `RingNoC` 和 `MeshNoC` generator，在 elaboration/lowering 阶段生成：

- 本地和链路 Queue；
- ingress/egress resource；
- Router scheduler process；
- destination decode；
- route request；
- arbitration；
- `ac.try_transfer`；
- Local flow import/export。

#### 客观评价

这个方案适合 MVP：它最快证明了现有 ACIR Core 可以构造可执行网络。但整个网络被生
成为一个 specialization，每个 Router 的代码被完整复制。它是功能闭环方案，不是长期
规模化方案。

### 4.2 问题二：Ring 闭环与 module instantiation cycle

如果把 Ring 的反馈表达成零延迟模块递归，会形成 module cycle。ownership 分析过去还
会在报告 cycle 前递归展开，导致 OOM。

#### 解决方案

- 每条 directed link 使用有状态 Queue；
- Ring 闭环只发生在 Queue 连接层，不形成 module instantiation cycle；
- ownership/topological ordering 在递归展开前检测 module cycle。

#### 新增 primitive

这一问题没有新增 NoC 专用 primitive，而是正确使用已有 Queue 状态语义，并修复编译器
cycle diagnostic 顺序。

#### 客观评价

该方案应长期保留。任何模型反馈都必须经过显式状态，不能依赖组合环。

### 4.3 问题三：ACPy 是静态 elaboration，难以逐周期产生随机流量

把 Bernoulli traffic generator 直接写入 ACPy process 会把实验控制与被测微结构混在
一起，也不利于同一个编译产物扫描多个 injection rate 和 seed。

#### 解决方案

增加严格版本化的 host ABI 和 Python runtime 控制：

- `host_input_queue` 和 `host_output_queue`；
- 精确宽度 byte offer/take；
- `ModelRuntime.step()`；
- reset、input/output discovery 和 statistics；
- Python `UniformTraffic`；
- 每个 source 一个 pending Packet，遇到背压时重试；
- warmup 和 measurement window。

#### 新增 primitive

这里主要增加的是 runtime 边界和 ABI，不是 NoC ACIR primitive。host offer 仍经过普通
Queue 和正常 Work/Xfer barrier。

#### 客观评价

这是项目中最值得保留的设计之一。它形成“Python 管实验、编译模型管微结构”的清晰
分层，也是未来自动化 DSE 控制器的基础。

### 4.4 问题四：普通 i32 难以同时表达路由字段和业务 payload

单个 `i32` 可以验证最简单 NoC，但无法清楚区分 destination 和 payload，也不适合作为
通用数据结构。

#### 解决方案

先打通通用 Packet，再将 Packet 接入 NoC：

- `ac.packet` 类型声明；
- `ac.record.create`；
- `ac.record.get`；
- `ac.record.with`；
- `ac.packet.serialize`；
- `ac.packet.deserialize`；
- Packet Queue/Flow；
- Packet 的 ACSim/C++ 定宽布局和 host byte ABI。

MeshNoC 通过 `route_field="destination"` 读取顶层 `i32` 字段，完整 Packet 原样转发。

#### 新增 primitive

本阶段真正打通的是通用 Packet/record primitive family，而不是 `NoCPacket` 或其他专用
类型。

#### 客观评价

实现顺序正确：Packet 是通用数据语义，NoC 只是消费者。但当前 Packet 仍是一个原子
Queue 元素，不代表 multi-flit packet。

### 4.5 问题五：用 Queue depth 模拟 VC 占用时间不正确

早期曾尝试将 `queue_depth` 调成 1，以逼近 BookSim 中一个 VC 被占用较长时间的效果。
这个思路混淆了两个正交概念：

```text
buffer capacity != VC ownership duration
```

一个 flit 离开本地 Queue 后，VC 仍可能等待 downstream 消费和 tail credit。减小 Queue
深度不能表达这段 ownership。

#### 解决方案

增加 topology-neutral 的显式状态：

- 每个 network egress 一个 owner；
- downstream ingress 消费后产生 reverse credit；
- credit 使用普通 i32 Queue 传输；
- owner 等到 credit 可见后释放；
- `wait_for_tail_credit=True` 明确控制 release 语义。

#### 新增 primitive

这一阶段没有增加 credit 或 VC 专用 primitive。owner、credit 和 countdown 都使用普通
Queue、process、算术和 `try_recv/try_send` 表达。

#### 客观评价

语义修正是必要且正确的，也证明了通用 primitive 的表达能力。但用 Queue 保存标量
owner 状态会产生较大的运行时和代码生成开销，应视为过渡实现。

### 4.6 问题六：只有 VC ownership，仍缺少 BookSim 的 Router pipeline

加入 owner 后，AC 饱和吞吐下降，但仍远高于 BookSim。原因是 AC Router 仍接近单阶段
elastic forwarding，没有显式 VA 和 SA 等待。

#### 解决方案

增加 `router_pipeline="input_queued"` 模式：

- 每个 ingress 具有 IDLE、VA、SA 状态；
- `vc_alloc_delay=1`；
- `sw_alloc_delay=1`；
- VA grant 后保持 egress owner；
- SA 完成且 downstream writable 时才能 transfer；
- backpressure 时不能丢失 owner 或错误 pop ingress。

#### 新增 primitive

此阶段没有增加 pipeline primitive。pipeline phase 和 countdown 暂时编码成 i32 状态，
并通过 Queue 在 tick 之间保存。

#### 客观评价

它成功验证了 VA/SA timing 对饱和吞吐的重要影响，但 magic integer 状态和 Queue-based
register 让 IR 可读性和执行效率下降。长期需要通用的显式状态单元。

### 4.7 问题七：手工展开 round-robin 导致编译爆炸

最初 round-robin 在 Python emitter 中展开成：

- pointer position；
- rotated priority；
- blocked prefix；
- available/selected；
- next pointer；
- 大量 `cmpi/andi/ori/select`。

2×2 可以运行，但 4×4 input-queued 模型在 1.9 GB 限制下触发 ACIR→ACSim OOM。

#### 解决方案

扩展统一的 `ac.arbitrate`，增加显式状态 policy：

```mlir
%g0, %g1, %next = ac.arbitrate round_robin
  state %pointer
  candidates [
    %r0 uses [@output],
    %r1 uses [@output]
  ] : (i32, i1, i1) -> (i1, i1, i32)
```

其语义包括：

- request 输入；
- one-hot grant；
- 显式 pointer 输入；
- 显式 next pointer 输出；
- 无 request 时保持规范化 pointer；
- verifier 检查 policy、candidate 和资源约束；
- ProcessState 中一个紧凑 action；
- ACSim 中一个 invoke；
- C++ 中按候选宽度生成共享算法 helper；
- 不使用动态拓扑或 heap allocation。

#### 新增 primitive

本阶段最关键的新 primitive 是：

```text
ac.arbitrate round_robin
```

它不是 NoC 专用操作，而是可被 crossbar、scheduler、issue logic 和其他资源竞争模型复用
的通用仲裁语义。

#### 客观评价

这是“primitive 应贯穿整个编译链”的成功案例。只在 ACPy emitter 中抽取 Python helper
不会减少后端代码；只有 ACIR、ProcessState、ACSim 和 C++ 都保持紧凑语义，才能真正
降低编译成本。

不过当前仅 VA round-robin 得到紧凑实现。SA 的 fixed-priority resource arbitration
仍会在 ACIR→ACSim 中展开，问题尚未完全解决。

### 4.8 问题八：ProcessState canonical report 本身造成 OOM

大型模型的 ProcessState report 曾一次性构造完整 JSON DOM 和完整 canonical string，
造成明显峰值内存放大。

#### 解决方案

将顶层数组改为逐元素 canonicalize 和输出，在保持 canonical bytes 不变的同时降低峰值
内存。

#### 新增 primitive

没有新增 primitive，这是 compiler infrastructure 的内存优化。

#### 客观评价

该修复解决了独立于 NoC 语义的真实基础设施瓶颈。最终 4×4 lowering 在 1.9 GB 限制下
实测峰值约 194 MB。

## 5. 逐步向 BookSim 对齐的结果

所有 2×2 模型使用相同的 uniform Bernoulli traffic、one-flit Packet、VC=1、depth=2、
三个 seed、2000 warmup 和 2000 measurement ticks。

在请求注入率 1.0 时：

| 模型 | packet/node/tick | 相对上一阶段补充的语义 |
|---|---:|---|
| AC elastic | 0.6842 | ready-valid、单阶段转发 |
| AC credit owner | 0.5676 | VC owner、reverse credit、round-robin |
| AC input queued | 0.2283 | ingress VA/SA state、VA1、SA1 |
| BookSim IQ | 0.1176 | 完整 BookSim IQ event model |

这个过程说明：

1. 只调 Queue depth 不能解释差异；
2. VC ownership 会降低可用输出通道频率；
3. VA/SA pipeline 是更显著的吞吐限制；
4. 每补充一项真实微结构语义，AC 曲线都会向 BookSim 移动；
5. 当前仍不能声称周期级或定量等价。

4×4 input-queued 对比中，在请求注入率 1.0 时：

| 模型 | packet/node/tick |
|---|---:|
| AC IQ | 0.1246 |
| BookSim IQ | 0.0781 |

低注入率下两者比较接近，例如请求注入率 0.04 时分别约为 0.03998 和 0.03942；进入
饱和区后差距扩大。这表明基本注入和路由行为相近，差异主要由竞争、pipeline、credit
和 channel event ordering 放大。

这些结果应被描述为“可复现的趋势对比和语义校准”，而不是“BookSim 定量验证完成”。

## 6. 当前已有 primitive 与临时组合方案

必须区分“已经进入 ACIR Core 的 primitive”和“为了完成 NoC 暂时用已有 primitive
拼出的组件语义”。

### 6.1 已经新增或打通的通用 primitive

| 能力 | ACIR 表达 | 后端状态 |
|---|---|---|
| Packet 类型 | `ac.packet` | 定宽布局贯通 ACSim/C++/ABI |
| Packet 字段 | `ac.record.create/get/with` | 紧凑 helper |
| Packet 边界 | `ac.packet.serialize/deserialize` | 精确宽度 bytes |
| 原子 Queue 转移 | `ac.try_transfer` | 保持 Queue 守恒和背压 |
| 固定优先级仲裁 | `ac.arbitrate greedy_fixed_priority` | 当前仍可能展开 |
| Round-robin 仲裁 | `ac.arbitrate round_robin` | 紧凑 action/invoke/helper |

其中真正为解决本轮编译爆炸而增加的新通用 primitive 是
`ac.arbitrate round_robin`；Packet family 则是在 NoC 之前作为通用数据语义打通，再被
NoC 使用。

### 6.2 目前仍用通用 Queue/process 拼出的语义

以下能力已经能够执行，但还没有紧凑 primitive：

- VC owner；
- round-robin pointer 的持久化；
- ingress pipeline phase；
- VA/SA countdown；
- reverse credit；
- delayed credit visibility；
- candidate request matrix；
- switch transfer matrix。

这种实现证明了 ACIR 的表达完备性，却不是理想的规模化执行形式。

## 7. 当前仍未与 BookSim 对齐的语义

### 7.1 Router 周期事件顺序

BookSim 的 routing computation、VC allocation、switch allocation、switch traversal 和
channel traversal 有明确的 event ordering。当前 AC IQ 只显式建模了 VA 和 SA 等待，
尚未完整对齐 RC、ST 和 channel visibility 的周期边界。

### 7.2 Credit 可见时序

当前 credit 使用普通反向 Queue，已经保证不会同 tick 瞬时返回，但 downstream dequeue、
credit generation、reverse channel traversal 和 upstream owner release 的精确周期仍需与
BookSim 逐事件对齐。

### 7.3 Allocator 语义

BookSim 使用 separable allocator。当前 AC 的 VA 使用 per-egress round-robin，SA 使用
resource-constrained fixed-priority 证明 ingress/egress exclusivity。双方 grant 顺序和
同周期状态更新顺序尚未完全一致。

### 7.4 Source 和 ejection buffering

Python 每个 source 维护一个 pending Packet，host ingress、local injection Queue 和
ejection Queue 的层级与 BookSim injection/ejection buffer 并不完全相同。

### 7.5 Traffic trace 和统计口径

- Python RNG 与 BookSim RNG 即使使用相同 seed，也不会产生相同 trace；
- AC 当前主要报告 delivered Packet throughput；
- BookSim adapter 当前读取 accepted packet rate；
- 有限 measurement window 中，accepted、in-flight 和 delivered 不完全相等。

要做严格定量对比，应先给双方输入相同的预生成 trace，并统一测量窗口和 throughput
定义。

### 7.6 Multi-flit 和多 VC

当前一个 Packet 就是一个 flit，VC 固定为 1。BookSim 中完整 packet lifetime、head/tail、
跨 flit VC ownership 和多个 VC 的 allocation 尚未表达。

## 8. 当前实现的效率问题

4×4 IQ 模型的实际规模为：

| 阶段 | 行数 | 大小 |
|---|---:|---:|
| ACIR | 9,075 | 806 KB |
| Frozen ACIR | 8,466 | 2.11 MB |
| ACSim IR | 13,130 | 1.64 MB |
| C++/headers | 39,971 | 1.80 MB |
| process C++ | 34,047 | 1.39 MB |

每个 Router 当前枚举 ingress × egress：

```text
corner:   3 × 3 = 9 candidates
edge:     4 × 4 = 16 candidates
interior: 5 × 5 = 25 candidates
```

4×4 全网产生 264 个 `ac.try_transfer`，并伴随 2264 个 `arith.andi`、1384 个
`arith.cmpi`、680 个 `arith.select` 和 1209 个 ACSim invoke。

主要原因包括：

1. generator 过早展开 route/request/transfer matrix；
2. fixed-priority SA 在后端重新展开为布尔网络；
3. 标量状态使用完整 Queue runtime object；
4. Frozen owner metadata 被重复附着到大量 operation；
5. 每个 Router process 生成独立 C++ 直线代码；
6. 相同 helper、FlowSource 和 FlowSink 实现缺少全局复用。

### 8.1 4×4 仿真速度基线

对 4×4、VC=1、depth=2 的 IQ 模型进行了相同口径的空载和饱和测速。每次测试先
warmup 100 ticks，再测量 500 ticks，独立重复 3 次。饱和测试每 tick 尝试向 16 个
Local ingress 注入 Packet，并回收所有 ejection；runner 同时检查 Packet 长度和目标
node，误路由会直接失败。

| C++ 优化 | 空载 ticks/s | 饱和核心 `ModelRuntime.step()` | 饱和含 Python 注入/回收 |
|---|---:|---:|---:|
| `-O0` | 204.57 | 177.71 | 174.68 |
| `-O2` | 316.60 | 276.14 | 271.17 |
| `-O2/-O0` | 1.55× | 1.55× | 1.55× |

饱和端到端平均 tick 时间由约 5.72 ms 降到 3.69 ms。Python traffic driver 只使
`-O2` 结果从 276.14 降到 271.17 ticks/s，开销约 1.8%，因此当前主要瓶颈不在
Python ABI，而在生成模型和 ACSim runtime 热路径。`-O2` 带来明确但非数量级的
改善，不能替代对 scheduler 展开、细粒度状态对象和通用事件调度的结构优化。

`-O2` 数据来自隔离的已知正常提交 `eed1140`，完整的 elaborate、freeze、lower、
C++ link 和 runtime smoke 均通过。该构建还有显著的编译代价：`cxxgen-link` 用时
695.99 s；一个中心 Router scheduler 单独优化编译用时 147.25 s、peak RSS 约
251 MiB。旧版构建器对单条 compiler command 固定 120 s timeout，因此测试时只在
`/tmp` 隔离 worktree 将 timeout 提高到 300 s，主线尚未接受这一改动。

当前 HEAD `dbf2eb7` 即使重建工具链，4×4 模型仍在 ACIR→ACSim 阶段触发
`activation edges must exactly equal computed static dependencies`，所以尚无当前
HEAD 的有效 `-O2` 数据。该失败没有通过关闭 verifier 绕过；对照说明回归位于
`eed1140` 之后的 state-array 相关提交中，但还需要进一步 bisect 才能定位具体提交。

## 9. 下一阶段需要补充的通用设计和 primitive

后续不应简单增加 `ac.mesh_router` 或 `ac.booksim_router` 黑盒。Router、Crossbar、Link、
Packetizer 和 Reassembler 应继续属于 component/generator 层。ACIR primitive 应保持跨
领域、可验证、状态和副作用明确，并能一直保持到共享 runtime kernel。

### 9.1 P0：先定义周期语义和性能基线

在新增 primitive 前，需要固定：

- tick 内 read/propose/arbitrate/transfer/commit 顺序；
- state old-value 和 next-value 可见性；
- Queue dequeue/enqueue 可见周期；
- link traversal 和 credit traversal 的周期定义；
- accepted、injected、delivered 和 in-flight 的统计口径；
- ACIR/ACSim operation 数、C++ 大小、编译时间、peak RSS 和 ticks/s 基线。

否则 primitive 虽然能减少文本，却可能改变仿真语义或没有改善真实性能。

### 9.2 P1：通用 ticked state cell

建议设计一个通用显式状态 primitive，暂可称为 `ac.state_cell` 或 `ac.register`，但需要
避免与已有 protocol declaration `ac.state` 混淆。

需要定义：

- typed initial value；
- read-old/write-next；
- tick commit；
- reset；
- optional write enable；
- 单写者 ownership；
- verifier 和 statistics 语义。

它可以替换：

- VC owner Queue；
- ingress phase Queue；
- countdown Queue；
- round-robin pointer Queue。

该 primitive 也可用于流水线控制、cache controller、DMA、scoreboard 和协议状态机，
具有明确的跨领域复用价值。

### 9.3 P2：让整个 `ac.arbitrate` family 保持紧凑

不一定需要新增另一个 allocator op。更优先的方案是完善现有 `ac.arbitrate`：

- fixed-priority 和 round-robin 都保持到 ProcessState/ACSim；
- 支持显式 candidate resource sets；
- verifier 维护 one-hot、资源互斥和 state contract；
- 相同 policy/width/resource shape 共用 C++ kernel；
- 避免 SA fixed-priority 再展开成大量布尔操作。

如果未来 age-based、weighted 或 QoS policy 不共享同一个 request/resource/grant 契约，
则不应仅通过任意字符串塞进 `ac.arbitrate`。

### 9.4 P3：原子 batch transfer primitive

建议设计通用的 variadic/batch transfer，例如暂称：

```text
ac.try_transfer_batch
  ingress queues
  egress queues
  grants
→ fired mask
```

它需要保证：

- 同一 ingress 至多 pop 一次；
- 同一 egress 至多 push 一次；
- 所有 transfer 在同一 epoch 原子决定；
- full/empty 时对应 grant 不会错误修改 Queue；
- fired mask 可用于 owner、credit 和 pipeline next-state；
- verifier 能检查 grant 与资源约束的来源。

这一 primitive 可以被 crossbar、bus、dispatcher 和多端口 scheduler 复用，而不是只服务
NoC。它应在 ACSim 中对应一个紧凑 action，并由共享 C++ loop/kernel 执行。

### 9.5 P4：紧凑的静态 request/route descriptor

XY、Ring clockwise 等拓扑策略不应成为 ACIR Core primitive。但 generator 可以生成
紧凑的静态 descriptor，由通用 predicate/table lookup 形成 request vector，避免为每个
ingress×egress 重复生成字段比较和布尔组合。

这一设计需要先确认：

- verifier 能否检查 destination coverage 和 invalid-destination stall；
- descriptor 是否独立于 Mesh/Ring；
- 后端能否用固定数组和循环执行；
- 是否真的比现有 arith/scf 表达更紧凑。

在契约没有稳定前，不建议仓促新增 `ac.route_xy` 等拓扑专用 primitive。

### 9.6 P5：通用延迟和 pipeline 表达

要和 BookSim 对齐，需要明确 RC、VA、SA、ST、link 和 credit 的时序。优先评估现有
`ac.event_queue`、`ac.schedule`、`ac.wait_for`、Queue 和 time-domain 能否组合成紧凑语义。

只有在以下条件成立时，才值得增加新的 delay/pipeline primitive：

- 现有组合会显著展开；
- tick visibility 可以形成稳定通用契约；
- 能被 compute pipeline、memory latency、DMA 和 interconnect 共同复用；
- ACSim/C++ 可以提供明显更高效的实现。

不应增加只模拟 BookSim 某个内部 stage 的专用 op。

### 9.7 P6：multi-flit 和多 VC 应主要作为 component 设计

ACIR 已有 Packet 和 Transaction 语义。multi-flit 更适合通过通用组件完成：

- `ac.std.Packetizer`；
- `ac.std.Reassembler`；
- flit record，包括 head/tail、packet ID、VC 等字段；
- 每 VC buffer、owner、credit 和 allocator state；
- packet completion 和 reassembly contract。

需要补充的底层能力主要是高效 state collection、allocator 和 batch transfer，而不是
新增一个“multi-flit NoC primitive”。

### 9.8 P7：后端共享与 DSE 基础设施

除了 primitive，还必须改进：

- helper 全局按签名去重；
- 相同 Router/process implementation 共享 C++；
- 实例差异通过静态 descriptor/table 表达；
- Frozen ownership metadata 使用共享表引用；
- specialization artifact cache；
- 结构参数和 runtime 实验参数分离；
- 相同 traffic trace 对多个设计点回放；
- 统一结果 schema 和 design-point fingerprint；
- 批量运行、失败记录和可复现报告。

如果缺少这些能力，即使单个模型可以运行，也难以高效扫描大量微结构参数。

## 10. 推荐实施顺序

```text
1. 固定 tick/event/statistics 语义和工具性能基线
2. 增加通用 ticked state cell
3. 让 fixed/RR ac.arbitrate 全链保持紧凑
4. 增加原子 batch transfer
5. 去重 Frozen metadata 和 C++ helper/process implementation
6. 使用共享 traffic trace 对齐 AC/BookSim 测量口径
7. 补齐 RC/ST/link/credit 周期语义
8. 在紧凑基础上实现 VC>1、Packetizer/Reassembler 和 multi-flit
9. 建设 specialization cache 和自动化 design-space runner
```

其中 1～5 解决 AC 自身的通用性和效率，6～7 才能提高 BookSim 定量可比性，8 扩展
NoC 表达能力，9 让这些能力真正服务于自动化微结构探索。

## 11. 最终结论

NoC 开发已经证明：AC 可以在不引入 NoC runtime 黑盒的前提下，描述并执行 Packet、
Queue、routing、backpressure、VC owner、credit、VA/SA 和 round-robin，并由 Python
逐周期驱动生成可复现吞吐曲线。

开发过程也证明了两个重要原则：

1. 微结构差异必须通过真实、正交的状态和事件语义表达，不能通过调整 Queue depth 等
   无关参数近似；
2. 一个稳定算法只有在 ACIR、ProcessState、ACSim 和 C++ 全链保持为紧凑 primitive，
   才能真正减少代码量和编译成本。

`ac.arbitrate round_robin` 是第二条原则的成功案例。但当前 owner、pipeline state、SA
和 transfer matrix 仍然过度展开，AC 与 BookSim 的周期事件模型也尚未完全一致。

因此下一阶段不应继续堆叠 NoC 特例，而应建设通用 ticked state、紧凑 arbitration、
batch transfer、共享后端 kernel 和 DSE 基础设施。这样才能把当前“能够执行一个 NoC”
提升为“能够快速、可靠地探索大量微结构设计”。
