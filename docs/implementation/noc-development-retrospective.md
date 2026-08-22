# NoC 开发复盘与后续架构建议

更新时间：2026-08-22

已提交基线：`fa48468`

状态说明：本文记录从初始 OOM 到紧凑仲裁完成验收的全过程；历史失败不会被改写成通过。

## 1. 摘要

NoC 工作已经证明 AC 可以用同一套显式 Queue、process、resource、Packet 和
host runtime 机制描述一个可执行网络，而不需要在 ACSim 中加入 NoC 黑盒。当前
已经打通：

- RingNoC 和 MeshNoC 的 ACPy 声明、ACIR 生成、freeze、ACSim、C++ 和 executable；
- 单 flit `i32` 与原子 Packet 的端到端传输；
- Local、单跳、多跳、Ring wrap-around、XY routing、背压和非法目的地址；
- Python `model.step()` 驱动的运行时注入、统计采集与确定性吞吐曲线；
- VC=1 下的显式 owner、反向 credit、VA/SA 延迟和 round-robin 状态；
- 2×2 AC/BookSim 的可复现数据与图片。

这条路线总体上符合 AC 的设计初衷：结构和状态是静态、显式、可验证的，runtime
只执行编译后的模型，不理解 NoC 拓扑。然而，后期为了快速逼近 BookSim 的 IQ
微架构，过多逻辑被直接展开进 Python textual lowering。结果是语义虽然可执行，
表达一度不够紧凑：4×4 IQ 模型曾在 ACIR→ACSim 阶段于 1.9 GB 限制下 OOM。现已用
通用 `ac.arbitrate round_robin`、紧凑 ProcessState action 和分段 canonical JSON
序列化解决，全链编译与运行通过。

最重要的结论不是“需要一个专用 NoC runtime”，而是：

> ACIR 需要保留对验证和后端有价值的通用语义，避免 generator 过早把仲裁、状态
> 选择等固定算法展开成大量标量组合逻辑。

## 2. 已完成能力与边界

| 方面 | 当前能力 | 明确边界 |
|---|---|---|
| 拓扑 | 单向 Ring 2～16；Mesh 最大 4×4 | 无 Torus、双向最短 Ring、任意拓扑 DSL |
| 路由 | Ring clockwise；Mesh deterministic XY | 无 adaptive、escape routing |
| payload | 完整 `i32`；原子定宽 Packet | Packet 仍是一个 Queue 元素，不是 multi-flit packet |
| 流控 | ready-valid；Mesh 可选显式 credit owner | VC 数固定为 1 |
| Router timing | elastic；IQ 的 VA/SA/credit 参数 | 尚未与 BookSim 的完整 RC/ST/link event ordering 对齐 |
| 仲裁 | greedy fixed priority；显式 pointer 的紧凑 round-robin | round-robin 固定为单共享资源、单 grant |
| runtime 控制 | ABI 3 host input/output、`ModelRuntime.step()`、reset、statistics | 没有 NoC 专用动态 runtime |
| 验证 | Queue 守恒、容量、错误 ejection、确定性重复运行 | 2×2 曲线不能证明周期级微架构等价 |

已提交 IQ 2×2 实验在注入率 1.0 时的平均吞吐为：

| 模型 | packet/node/tick |
|---|---:|
| AC elastic | 0.6842 |
| AC credit owner | 0.5676 |
| AC input queued，VA1/SA1 | 0.2283 |
| BookSim IQ | 0.1176 |

这些数据说明 owner 和 VA/SA timing 是重要因素，但当前 AC 与 BookSim 仍不是同一
周期模型，不能把曲线接近程度直接解释为定量验证完成。

## 3. 开发过程中遇到的问题与采取的方案

### 3.1 从声明式 schema 到可执行网络

早期 stdlib 中的 Router、TrafficSource 和 Sink 更接近占位 schema，没有完整的
lowering/runtime 语义。最终选择 compiler-native `RingNoC`/`MeshNoC` generator，
在编译期生成 Queue、resource 和 process。

这个决定是正确的：它避免了尚未定义清楚的 runtime 黑盒，也让 topology、routing
和 backpressure 能进入 ACIR verifier。但它也埋下了一个问题：整个网络生成成一个
specialized module，每个 Router process 都被完整复制。

### 3.2 环形连接与模块循环

Ring 的闭环不能用零延迟模块递归表达，否则会与 module ownership/cycle 分析冲突。
实现采用每条 directed link 一个有状态 Queue，闭环发生在 Queue 连接层，不形成
module instantiation cycle。

同时修复了 module ownership 在检测实例循环前递归展开、导致测试 OOM 的问题。
这个方案清晰且应保留：网络反馈必须经过显式状态，不能依赖组合环。

### 3.3 ACPy 静态编译与运行时流量注入

最初考虑在 ACPy process 中实现完整 traffic generator，但静态 elaboration 不适合
用 Python 控制每个运行时 tick。后来增加严格版本化的 host ABI 和
`ModelRuntime.step()`：Python TrafficManager 负责 Bernoulli 决策，编译模型仍通过
正常 Queue/backpressure 接收输入。

这是侵入性较小、概念也更清楚的方案。它把“被测微架构”和“实验控制器”分开，
并没有让 Python 绕过 Queue 或调度屏障。

### 3.4 Packet 表达

Packet 首先作为通用 ACIR 类型打通到 ACSim/C++，随后才连接到 ACPy 和 NoC。
这是比“为 NoC 特制一个消息结构”更好的顺序。当前 Packet 是原子定宽值，完整进入
和离开 Queue；它解决了字段化路由和 payload 保真，但并未解决 multi-flit、head/tail
或跨 flit 的 VC ownership。

### 3.5 Queue depth 与 VC ownership 混淆

早期曾试图通过把 Queue depth 调小来近似 BookSim 中 VC 被占用的时间。这个思路
不准确：buffer capacity 和 allocation ownership 是两个正交概念。depth=1 只能限制
缓存数量，不能表示一个 flit 已离开当前 Queue、但 VC 仍等待 downstream credit 的
状态。

后续增加了显式 egress owner 和反向 credit Queue。该修正是必要的，也说明微架构
时序不能靠调整容量参数替代。

### 3.6 Credit、VA 和 SA 状态

为了保持 runtime 通用，owner、credit countdown 和 pipeline state 都使用普通 Queue
保存，scheduler 每 tick `try_recv`、计算 next state、再 `try_send`。这成功复用了现有
ACIR/ACSim 能力，没有增加 NoC runtime component。

但当前状态编码使用了 `100 + VA countdown`、`200 + SA countdown`、`-128` 等 magic
integer。它在短期内实现简单，却降低了可读性，并把状态机编码细节泄露进大量生成
文本。Queue depth=2 也部分承担了“同一 epoch 读旧状态、写新状态”的 register 功能，
语义不够直接。

### 3.7 Round-robin 展开、4×4 OOM 与最终修复

ACIR 原先的 `ac.arbitrate` 只接受 `greedy_fixed_priority`。为实现 round-robin，
lowering 手工生成 pointer position、blocked prefix、available、term、selected 和
next-pointer 的布尔网络。

在 2×2 中这种展开可以工作，也通过了确定性和公平性测试；扩展到 4×4 IQ 后，基线
数据为：

- 原始 ACIR 约 1.3 MB；
- frozen ACIR 约 3.2 MB；
- 约 1.4 万行；
- ACIR→ACSim 在 `ulimit -v 1900000` 下触发 LLVM OOM。

一次未提交实验尝试把 VA 拆成 per-egress arbiter。独立拆分 SA 时，ACIR verifier
无法证明同一 ingress 的多个 `try_transfer` 互斥，因此真实失败；恢复全局 SA 后
定向 verifier 重新通过。最终没有停留在这个临时拆分方案，而是新增了通用的显式
状态 policy：`i32` pointer 输入、one-hot grants 和 `i32` next pointer 输出。相同候选
宽度共享一份 C++ helper，ACSim 保持单个 invoke，不引入 NoC runtime 或动态分配。

第二个真实瓶颈出现在 ProcessState canonical report：一次性构造整棵 JSON DOM 再生成
完整字符串造成峰值内存放大。序列化器改为逐元素 canonicalize，最终 canonical bytes
保持不变。4×4 lower 在 1.9 GB 限制下实测峰值约 194 MB，完整 C++ link 和 runtime
通过。原始 ACIR 从约 1.3 MB 降至 806,476 bytes，frozen 从约 3.2 MB 降至
2,111,259 bytes。

## 4. 做得比较好的地方

### 4.1 没有把 NoC 塞进 runtime 黑盒

Link、ingress、egress、owner 和 credit 都能在 ACIR 中被看见。统计、守恒和
backpressure 仍由通用 Queue/runtime 完成。这保留了 AC “编译结构、显式资源”的
核心价值。

### 4.2 从早期就固定了可验证的范围

节点编号、route bits、XY 顺序、非法 destination、单 flit、VC=1 等规则被明确固定，
避免了表面可配置、实际语义不完整的接口。非法配置在 frontend 带源码位置失败。

### 4.3 公共描述符已经与拓扑决策解耦

NoC scheduler 接收 ingress、egress、route request 和 timing descriptor，不直接知道
North/East/South/West。Ring 若将来启用同类 timing，不需要复制 Mesh 的 owner/credit
状态机。

### 4.4 验收覆盖了真实后端和 runtime

测试没有停留在“ACIR 文本里出现某个字符串”，还包含 freeze、ACIR→ACSim、C++、
shared library、runtime delivery、Queue conservation、capacity peak 和两次输出 hash。
OOM 和 verifier 失败也被如实保留，没有通过放宽断言制造成功。

### 4.5 Benchmark 产物可追溯

配置、raw CSV、summary、PNG 和 SHA-256 被放在非 `build-*` 目录，重复构建不会删除。
2×2 IQ sweep 两次运行字节一致，这为后续微架构调整提供了稳定基线。

## 5. 之前做得不够好的地方

### 5.1 过早把算法展开成标量 ACIR

最大的问题曾是把“round-robin 仲裁”当成 Python emitter 的代码生成技巧，而没有先
判断它是否是 ACIR 应保留的通用语义。Python helper 即使抽取得很漂亮，生成后的
ACIR、ProcessState 和 C++ 仍然重复。

更好的原则是：如果一个操作具有稳定契约、编译器可利用的整体性质，并且展开会
显著膨胀，就应尽量晚展开，或者一直保留到共享后端 helper。

### 5.2 `ac.arbitrate` 的扩展点没有被及时使用

现有 op 已有 `policy` 字段，却只允许 fixed priority。新增 round-robin 时另行手写
选择网络，使 verifier 看不到 fairness、one-hot 和 pointer 更新是一个整体。

更紧凑的方向是扩展统一的 `ac.arbitrate`：

- `greedy_fixed_priority` 保持现有无状态接口；
- `round_robin` 接收显式 pointer 并返回 next pointer；
- grants 的资源互斥和 one-hot 性质由同一 verifier 维护；
- pointer 的持久化仍在显式 Queue/state 中，不藏进 runtime。

不应为每种算法创建互不相关的 NoC op，也不应把任意 QoS/adaptive 策略仅作为字符串
塞入 policy。只有共享 request/resource/grant 契约的算法才属于 `ac.arbitrate`。

### 5.3 整网单 module 便于起步，但复用不足

“一个 NoC specialization 生成整个网络”简化了连接和 ownership，却让每个节点重复
route decode、state update 和 scheduler body。对于 4×4，拓扑只增加到 16 个节点，
生成代码和后端中间状态却已有明显压力。

Router module 复用值得研究，但不应立即实施。ACIR module 当前以 Flow 为边界，若
为了复用额外插入 ingress/egress Queue，可能改变 buffer 数和 hop timing。应先压缩
通用 primitive；只有仍有必要时，再设计不会改变 Queue ownership 的 parameterized
Router/Channel 结构。

### 5.4 状态机表达不够类型化

magic integer 使错误状态也可能被普通算术悄悄传播。更清楚的长期方案是通用的显式
state cell/register，或至少由 compiler 内部 typed enum 描述 IDLE/VA/SA/WAIT_CREDIT，
最后统一编码，而不是在 emitter 多处拼接常数。

在没有定义清楚 commit-epoch、reset 和 ownership 前，不应仓促新增 state primitive；
短期可先集中状态编码器和 verifier assertion，消除散落常数。

### 5.5 结构测试过多依赖文本细节

部分测试统计具体 Queue 名、`try_recv` 次数或字符串片段。它们能防止早期回归，但会
阻碍合法的紧凑化。后续应增加语义级查询或 canonical report：Router 数、link 数、
allocator 宽度、状态 owner、最大 candidate 数。文本检查只保留关键 ABI/diagnostic。

### 5.6 BookSim 对比开始得早于微架构对齐

初始 AC elastic 与 BookSim IQ 曲线差异很大是预期结果，但实验名称一度容易让人把它
理解成同微架构验证。后续文档已经澄清，但更好的流程应先建立逐项映射表，再画对比
曲线。

目前仍未完全对齐的项目包括：

- BookSim 独立的 switch traversal final stage 和 channel event ordering；
- separable input-first allocator 与 AC resource arbitration 的准确 grant 顺序；
- downstream dequeue 到 credit 可见之间的周期定义；
- source queue、pending retry 和 ejection buffering；
- Python RNG 与 BookSim RNG 即使 seed 相同，也不会产生相同 packet trace；
- AC 测量 delivered throughput，而适配器读取 BookSim accepted packet rate，有限窗口
  边界只能近似守恒。

因此当前结果适合做“语义逐步补齐的趋势图”，尚不适合声称定量等价。

## 6. 更紧凑、清晰、高效的目标结构

建议把 NoC 相关实现稳定在三层：

```text
ACPy / stdlib generator
  - 参数验证、拓扑、坐标、路由策略
  - 产生 Router/Link 描述符
                 │
                 ▼
ACIR semantic primitives
  - Queue / try_transfer / resource
  - packet field
  - ac.arbitrate policy + explicit state
  - 通用、可验证，不包含 Mesh/Ring 特例
                 │
                 ▼
ProcessState / ACSim / C++
  - 一个 primitive 对应一个紧凑 action/invoke
  - 相同 policy/宽度共享 helper specialization
  - 无隐藏 NoC runtime、无动态拓扑
```

### ACIR primitive 的准入标准

一个常用逻辑不应仅因为“门很多”就成为 primitive。至少应满足大部分条件：

1. 语义稳定且跨领域复用；
2. 展开会造成显著 IR 或编译内存膨胀；
3. verifier 能利用其整体性质；
4. 后端能提供更紧凑或更准确的实现；
5. 状态和副作用可以完整、显式地定义；
6. 不依赖某个拓扑、协议或 benchmark 特例。

按这个标准，round-robin 属于 `ac.arbitrate` policy；XY routing、Mesh 和 Router 本身
仍应留在 generator/stdlib 层。

## 7. 优化执行结果与后续优先级

### P0：建立规模预算（已完成本轮基线）

- 固定 1×1、2×2、4×4 的 ACIR bytes、operation count、frozen bytes、lower peak RSS、
  generated C++ LOC、编译时间和 object size。
- 将 4×4 IQ 的 1.9 GB OOM 作为真实回归并已解决，没有提高限制。
- 保留 2×2 tick、争用顺序和 CSV hash 作为语义基线。

### P1：扩展统一的 `ac.arbitrate`（已完成）

- 增加显式状态的 `round_robin` policy，而不是单独的 NoC primitive。
- 一个仲裁在 ProcessState 中保持一个 action，在 ACSim 中保持一个 invoke。
- 相同 policy 和 candidate width 只生成一份 C++ helper；调用点不重新内联完整网络。
- verifier 统一负责 candidate/resource/grant 数量、互斥、pointer 规范化和 next-state。
- fixed-priority 的现有 ACIR、fingerprint 和输出保持不变。

### P2：简化 NoC scheduler（VA 已完成，状态编码仍可整理）

- 每个 egress 的 VA 使用统一 arbiter，删除手工 position/blocked/term 网络。
- SA 保留能够同时证明 ingress 和 egress 冲突的 resource arbitration。
- 集中定义 pipeline state 编码、credit state 转移和 deterministic naming。
- 对 route request 增加 one-hot 语义检查，使 per-output 分解有明确前提，而不是依赖
  人工推理。

### P3：修正 benchmark 可比性

- 先对齐 switch traversal、link 和 credit 可见周期，再解释吞吐差异。
- 同时报告 accepted、delivered 和 measurement 结束时 in-flight 数量。
- 长期使用预生成 packet trace 或统一 RNG/traffic specification，避免“同 seed 不同流量”。
- 在 2×2 通过逐周期 trace 后再运行 4×4；网络规模不能替代微架构对齐。

### P4：仅在仍有必要时复用 Router 结构

- 评估 corner、edge、interior specialization 是否能在不增加 Queue 层级的情况下共享
  process definition。
- module factoring 必须证明 Queue 数、hop timing、owner path、freeze ordering 和统计
  identity 不变。
- 如果模块边界会引入额外 FlowLink/Queue，应放弃该方案，优先优化 ProcessState 的
  per-process 生命周期和 canonical serialization 内存。

## 8. 建议保留的工程纪律

- 所有 native build 继续使用 1.9 GB 限制和单线程；OOM 是产品问题，不是通过提高
  机器资源掩盖的问题。
- 每个性能优化必须同时证明语义未变：verifier、runtime tick、争用顺序、守恒和
  benchmark hash。
- 新增 primitive 必须有独立通用测试，不能只由 NoC 示例间接覆盖。
- ACIR、ACSim 和生成 C++ 都要记录规模；只减少 Python 源码不算 lowering 优化。
- 不以关闭 verifier、放宽断言、缩小模型或减少统计来获得“通过”。
- benchmark 文档必须明确“趋势比较”还是“周期等价验证”。

## 9. 结论

NoC MVP 的主要价值，是验证了 AC 的通用 primitives 足以承载真实的有状态互连模型：
网络不需要特殊 runtime，Python 也可以通过稳定 ABI 控制编译后的系统。当前瓶颈并非
表达能力不足，而是抽象下降得太早。

本轮已经把仲裁提升为统一、紧凑、显式状态的 `ac.arbitrate` policy，并让该语义一直
保留到共享 C++ helper，同时解决了 4×4 ProcessState 序列化内存峰值。下一阶段应把
精力放在 BookSim 周期语义对齐和逐周期 trace，而不是继续增加 NoC 专用 primitive。
只有新的规模证据表明仍有必要时，才评估 Router module 复用。
