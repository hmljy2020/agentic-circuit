# ACIR Superscalar NPU 演进路线

更新时间：2026-08-22

文档状态：`ACTIVE`

## 1. 目标与范围

目标是逐步实现一个可运行、周期精确、可测量的 superscalar NPU，而不只是一个调度器演示。
最终系统应包含：动态调度控制核、Scalar/VEC/CUBE 执行单元、TileReg、复杂 DMA、本地存储、
Cache、HBM 模型以及连接这些组件的互连。

实现 NPU 和改进 ACIR 是同一条探索路线。每完成一个架构里程碑，都要用真实实现回答：

- ACIR 能否自然表达所需状态、并发、仲裁、背压和原子提交；
- 哪些重复结构适合标准组件，哪些确实需要新的通用 primitive；
- verifier、lowering、生成代码和 ACSim 分别缺少什么；
- IR 规模、编译时间、内存占用和仿真速度是否能随系统规模合理增长；
- 表示是否保留了继续 lower 到 RTL 所需的硬件结构。

`examples/phase5/npu` 的外部 C++ provider 可用作行为参考或差分 golden，但不能代替本目录
中的 ACIR 控制实现。计算单元内部的高成本数值计算可以阶段性抽象；调度、资源占用、数据移动、
存储层次和时序不能被一个黑盒掩盖。

## 2. 最终参考架构

最终架构按五个子系统组织，具体容量均应参数化，而不是固化成一次演示的常数。

| 子系统 | 目标能力 |
|---|---|
| 控制核 | 多宽 dispatch、issue window、依赖跟踪、动态发射、ROB、乱序完成与顺序退休 |
| 执行簇 | Scalar、多个 VEC、CUBE；显式 latency、II、capacity、端口和完成带宽 |
| 架构状态 | Scalar/Vector register、TileReg、谓词/状态寄存器以及明确的读写端口冲突 |
| 数据移动 | descriptor DMA、burst、对齐拆分、二维 stride、多 outstanding、响应重排和错误状态 |
| 存储与互连 | 本地 SRAM/缓冲、Cache、请求/响应 fabric、多通道 HBM 及其 bank/带宽/延迟模型 |

建议的数据路径是：

```text
                    ┌──────── control / scoreboard / ROB ────────┐
command stream ───▶ issue ──▶ Scalar / VEC / CUBE ──▶ completion
                         │          │       │
                         │      registers  TileReg
                         │          │       │
                         └────── memory request fabric ──────┐
                                                            │
global memory ◀─ HBM controller ◀─ HBM channels ◀─ Cache / DMA
                                      ▲              │
                                      └─ local SRAM ─┘
```

图只定义责任边界，不预先规定所有流量都必须经过 Cache。默认 DMA 可绕过 Cache，普通
load/store 可选择 cacheable；二者在 HBM 端共享带宽并接受仲裁。

## 3. 建模层次

路线采用逐级提高精度的方式，避免一开始同时解决所有问题。

| 层次 | 描述 | 用途 |
|---|---|---|
| L0：token | 指令和数据只携带 tag，FU 使用固定延迟 | 尽快验证动态调度和时间语义 |
| L1：transaction | 请求含地址、长度、端口和依赖；数据可摘要化 | 验证 DMA、Cache、HBM 和互连 |
| L2：value | 关键路径携带真实标量、向量或 tile 数据 | 做端到端功能 golden |
| L3：timing | 加入端口、bank、burst、队列、争用和流控 | 评估周期行为和仿真能力 |

每个组件必须注明当前达到的层次。不能把 L0 的固定延迟结果描述成 HBM 或 Cache 已实现；
也不要求所有组件同时达到 L3 才允许前进。

## 4. 工作方式

路线只长期维护“里程碑”，当前里程碑再拆成少量可执行任务。完成一个任务后，不继续无限细分，
而是进入一次实现验收；完成一个里程碑后，再进行完整 ACIR 审视并调整后续路线。

### 4.1 实现验收

- 在实现前写出该任务新增的行为边界和逐周期预期；
- 跑通 verifier、freeze、ACIR → ACSim、C++ 生成、编译和 runtime；
- 检查容量、守恒、唯一消费、背压、时间和确定性；
- 记录真实命令、退出状态、关键 trace、资源用量和对应提交；
- 不跳过、替换或减弱失败断言。

### 4.2 里程碑 ACIR 审视

每个里程碑完成后集中回答：

| 维度 | 问题 |
|---|---|
| 表达 | 哪些硬件意图仍依赖冗长或脆弱的 process 控制流？ |
| 抽象 | 应保持 primitive 组合、增加 canonicalization、标准组件还是新 primitive？ |
| 验证 | 哪些不变量可静态证明，哪些仍只能运行时发现？ |
| 编译 | IR/生成 C++ 在哪里重复，哪些 lowering 可融合或专门化？ |
| 仿真 | 热点来自唤醒、Queue、event、状态访问、调度还是跨语言调用？ |
| RTL | 状态、端口、仲裁、原子性和周期边界是否足够明确？ |

只有正确性和时序缺陷会立即阻塞主线。纯性能或易用性问题进入 backlog，在里程碑边界依据
数据决定是否处理。

## 5. 里程碑路线

### M0：语义基线与测量工具

目标：建立后续所有结论都能复用的验证和性能基线。

- 确认 Queue、event queue、`try_transfer`、arbitration、process suspension 的周期语义；
- 建立统一 trace、逐周期 golden、数量守恒和确定性检查；
- 测量各层 IR/C++ 大小、各编译阶段耗时与 RSS、native ticks/s；
- 固定低资源构建与运行方法。

验收门：能够解释并复现已有 primitive 的 committed-state 和周期可见性；空模型和最小
Queue/FU 模型均有可重复的规模及性能数据。

### M1：Superscalar 调度核

目标：完成当前旧路线所称的“最终原型”。它是第一个架构原型，而不是完整 NPU。

- 实现 Scalar、VEC、CUBE、DMA-token 四类固定时延执行路径；
- 实现参数化 dispatch、issue window、RAW 依赖跟踪、oldest-ready 发射和 FU 资源限制；
- 实现 ROB、乱序完成、顺序退休和各级背压；
- 用长延迟 CUBE/DMA-token 与短延迟计算重叠证明 latency hiding。

首个配置可使用 2-wide dispatch、8-entry window、8-entry ROB；这些只是验证点，随后应做
宽度和容量 sweep。

验收门：被阻塞的老指令不阻塞独立年轻指令；同周期存在多发射；执行可乱序完成但严格顺序
退休；满 window、ROB 和忙 FU 时无丢失或重复。

重点审视：可执行 resource 语义、可索引状态、multi-grant arbitration、多写原子提交、
issue window/ROB 展开造成的 IR 和仿真成本。

### M2：架构状态与 TileReg

目标：从 token 调度进入真实的数据依赖和端口冲突。

- 定义 Scalar/Vector register 与 TileReg 的类型、容量、生命周期和所有权；
- 让指令读取真实 operand，并在 completion/retire 的明确阶段写回；
- 为 TileReg 建立分配、占用、ready、释放和 producer/consumer 依赖；
- 建模多读写端口、同周期冲突、bank 冲突和必要的 bypass/forwarding。

验收门：CUBE 从两个 ready tile 取数并写回结果 tile；DMA 写 TileReg 与 CUBE 读 TileReg
存在确定的次序和背压；端口超额使用会被仲裁或 verifier 拒绝，不靠 process 执行顺序碰巧正确。

重点审视：`state array`、动态索引、端口化资源、批量字段访问和多读多写是否需要通用表示。

### M3：本地存储与片上数据通路

目标：建立执行单元、TileReg、DMA 之间可争用的真实数据通路。

- 加入 banked local SRAM、load/store queue 和请求/响应协议；
- 建立独立 request/response fabric，显式建模路由、仲裁、带宽和背压；
- 支持 tile 在 local SRAM、TileReg 和执行单元间搬运；
- 用多 bank 并行和同 bank 冲突验证吞吐差异。

验收门：并行访存只在端口与 bank 允许时发生；响应与原请求正确匹配；任意背压下数据、tag
和 credit 守恒。

重点审视：参数化互连、packet/transaction、banked memory、原子 request/response 和批量
事件调度的表示及生成代码规模。

### M4：复杂 DMA

目标：把固定延迟 DMA-token 替换为真正的数据移动引擎。

- 实现 descriptor queue、地址生成、长度与二维 stride；
- 实现 burst 生成、边界/对齐拆分、读写数据通道和完成通知；
- 支持多个 outstanding transaction、ID 分配、响应乱序和重组；
- 支持 global↔local、global↔TileReg 或经 local staging 的策略；
- 建模队列满、目的端慢、部分 burst 完成和错误状态。

验收门：非对齐、跨边界、二维 stride 和多 outstanding 搬运的数据结果正确；完成事件只在整个
descriptor 提交后产生；计算能与 DMA 流量真实重叠。

重点审视：transaction group、split/join、credit、reorder buffer、流式状态机能否由现有
primitive 清晰高效地表达。

### M5：HBM 子系统

目标：让访存延迟来自明确的 HBM 结构和争用，而不是一个常数。

- 建立可参数化 channel/pseudo-channel/bank、地址映射和 controller queues；
- 模拟 burst 传输、bank busy、行命中/冲突、读写 turnaround 和带宽；
- 让 DMA 与其他 global-memory client 共享 channel 并接受确定仲裁；
- 提供简单固定时延模式和争用感知模式，便于差分验证。

验收门：相同地址流在不同映射和 bank 冲突下产生可解释的周期差异；总线带宽不被超发；所有
请求最终得到且只得到一次响应。

重点审视：大量同构 bank/channel 的参数化表示、事件批处理、层次化 lowering，以及仿真器
能否避免逐 primitive 的过度唤醒。

### M6：Cache 与一致的内存视图

目标：加入可选 Cache，并明确它与 DMA、local memory 和 HBM 的关系。

- 先实现单级、阻塞式、write-through 或明确定义策略的最小 Cache；
- 再增加 set-associative tag/data array、替换、writeback 和 MSHR；
- 支持 hit、miss、miss 合并、eviction、下游背压和多个 outstanding miss；
- 明确 DMA bypass、flush/invalidate 或非一致内存区的可见性规则。

验收门：hit/miss/eviction 的数据和周期 golden 正确；MSHR 满会背压；DMA 与 cacheable 访问
不会在未定义的可见性规则下悄悄产生陈旧数据。

重点审视：associative lookup、存储数组、可组合 memory protocol、状态机优化，以及是否应将
Cache 保持为标准组件而不是新增专用 IR op。

### M7：端到端 Superscalar NPU

目标：把前述子系统组合成能运行代表性 workload 的完整原型。

- command stream 同时驱动 DMA、VEC、CUBE 和 Scalar 控制指令；
- TileReg/local SRAM 承载真实中间数据，Cache/HBM 提供 global memory；
- 支持必要的 event、barrier、fence、资源回收和错误传播；
- 运行至少一个 tiled GEMM/卷积子图及一个 DMA/计算高度重叠的合成 workload；
- 与软件参考模型做数值结果和允许范围内的逐周期差分。

验收门：端到端结果正确；能用 trace 解释 dispatch、搬运、计算、完成和退休；改变资源参数会
产生符合架构预期的吞吐变化，而不是只改变模拟常数。

重点审视：跨组件组合时暴露的 ACIR 协议碎片、全局唤醒风暴、IR 爆炸、编译瓶颈和层次化
组件边界。

### M8：扩展、优化与 RTL 路径

目标：证明模型不仅正确，而且能够扩展，并形成可执行的 ACIR 改进结论。

- sweep 发射宽度、window/ROB、VEC/CUBE 数、TileReg、DMA outstanding、Cache 和 HBM 参数；
- 针对实测热点实现 canonicalization、lowering 融合、生成代码专门化或 ACSim/runtime 优化；
- 定义 RTL-lowerable profile，挑选调度核、TileReg 端口或 DMA 子路径做 RTL lowering 试验；
- 总结保留、修改、新增和否决的 primitive/标准组件方案。

验收门：给出功能、IR 规模、编译 RSS/耗时、native ticks/s 随关键参数的曲线；优化有前后
对比且不改变逐周期结果；RTL 试验无需从任意 control-flow pattern 猜测资源和原子性。

## 6. ACIR 扩展原则

发现问题时先保存最小失败或膨胀案例，再按以下顺序选择方案：

1. 现有 primitives 的清晰组合；
2. canonicalization 或 lowering 优化；
3. 可 import 的标准组件；
4. 具有独立、通用硬件语义的新 primitive。

若新增 primitive，必须定义 committed-state、原子性、失败、时间、多写和资源冲突语义，并
补齐 parser/printer、verifier、freeze、ACSim lowering、C++ codegen、正负测试。迁移原始
NPU 场景后，要比较语义、IR/C++ 大小、编译时间、RSS 和 native 性能；没有明确收益则记录
否决原因。

优先关注通用能力，如端口化 resource、state/state array、transaction group、split/join、
credit、层次化参数组件和批量事件；避免 `ac.npu_scheduler`、`ac.cache`、`ac.dma` 这类把完整
微架构封成不透明黑盒的 op。

## 7. 统一记录

### 7.1 里程碑总览

| 里程碑 | 状态 | 主要产物 | 完成证据 | 复盘链接 |
|---|:---:|---|---|---|
| M0 语义与测量 | DONE | 三个自包含语义模型与测量脚本 | 3/3 runtime、19/19 targeted lit | [M0 报告](m0/REPORT.md) |
| M1 调度核 | DONE | 2-wide token 调度核、StateArray、周期 golden | 16 instructions / 64 traces、4/4 runtime、6/6 lit | [M1 报告](m1/REPORT.md) |
| M2 TileReg | TODO | — | — | — |
| M3 本地存储与互连 | TODO | — | — | — |
| M4 复杂 DMA | TODO | — | — | — |
| M5 HBM | TODO | — | — | — |
| M6 Cache | TODO | — | — | — |
| M7 完整 NPU | TODO | — | — | — |
| M8 扩展与 RTL | TODO | — | — | — |

状态只使用 `TODO`、`IN_PROGRESS`、`DONE`、`BLOCKED`。

### 7.2 当前里程碑任务

只展开当前里程碑，保持 3–6 项；完成或复盘后再替换本表，历史证据放入独立记录文件。

| 任务 | 状态 | 产物 | 验收命令/证据 | ACIR 发现 |
|---|:---:|---|---|---|
| M1-A token/指令格式与手算 timeline | DONE | `m1/runner.cpp` | 16 条逐周期 trace | packet/record 可表达格式 |
| M1-B 四类固定延迟执行路径 | DONE | event + CUBE 8-stage oracle | latency 等式与差分 assertion | 需要完成带宽 reservation |
| M1-C issue window、RAW 与 oldest-ready | DONE | `m1/gen_model.py` | RAW/WAW 与年轻指令越过 | 展开规模过大 |
| M1-D 2-wide dispatch/issue 与 FU 限制 | DONE | FU state + completion slots | 每阶段宽度≤2 | resource 执行语义缺失 |
| M1-E ROB、顺序退休与全链背压 | DONE | ROB/producer StateArray | 乱序完成、顺序退休、16/16 守恒 | StateArray 已打通 |
| M1-F 固定配置测量与 ACIR 复盘 | DONE | `m1/REPORT.md` | 统一脚本退出 0 | 参数 sweep 留作下一次重构 |

### 7.3 ACIR 与优化 backlog

| ID | 来源 | 最小证据 | 候选层次 | 正确性影响 | 规模/性能影响 | 决定 | 状态 |
|---|---|---|---|:---:|---|---|:---:|
| M1-STATE | M1 window/ROB | `state-array-*` tests | primitive | 是 | 去除命名 scalar state | 保留并继续优化 | DONE |
| M1-EXPAND | M1 scheduler | 3,321 行 ACIR / 28,627 行 C++ | lowering/标准组件 | 否 | 编译与仿真热点 | 做参数 sweep 后决策 | TODO |
| M1-RESOURCE | FU 与完成带宽 | `completion_slots` 展开 | 标准组件/通用 primitive | 是 | 大量组合 SSA | 研究 reservation/resource | TODO |
| M1-CFG | packet StateArray 穿过 scf | packet CFG regression | lowering bug | 是 | — | block arg 转为 acsim.value | DONE |

### 7.4 里程碑复盘模板

```markdown
## Mx 复盘（日期）

- 结果：DONE / BLOCKED
- 实际完成和未完成：
- 正确性与逐周期验收：
- 架构认识的变化：
- ACIR 表达/verifier/lowering 问题：
- IR、生成代码、编译和仿真数据：
- 新增、修改或否决的抽象：
- 后续路线调整：
```

## 8. 当前边界与下一步

M0 已完成，结果见 [M0 报告](m0/REPORT.md) 和
[primitive 能力矩阵](m0/PRIMITIVE_MATRIX.md)。当前只展开 M1；它是第一个 superscalar
控制原型，M2–M7 才逐步把它变成有真实状态、数据移动和存储层次的 NPU，因此不能在 M1
完成时宣称最终目标已经完成。

下一步执行 M1-A：定义 token/指令格式，并先手算同时覆盖 Scalar、VEC、CUBE 和 DMA-token
的逐周期 timeline。构建和运行继续采用单线程及 1.9 GB 虚拟内存限制。
