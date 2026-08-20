# 参数化声明组件：分层语义、当前能力与实现路线

> 本文讨论：像 crossbar 这样由 ACIR primitive 组合而成的组件，能否在
> Python 中声明一次，按 `n_in` / `n_out` 等静态参数生成不同拓扑，再被其他组件
> 多次实例化。文中严格区分 Python 源码、ACPy、冻结 ACIR 和运行时实例四个层次。
> 基于 2026-08-20 的工作树快照；项目正在快速演进，具体实现状态应以代码和测试为准。

---

## 1. 结论

需要把“参数化组件”拆成两种复用：

| 能力 | 当前状态 | 准确含义 |
|---|---|---|
| 同一个 concrete module 实例化多次 | 已支持 | 一个端口签名、拓扑和静态参数均已冻结的 `ac.module`，可通过 `ac.instance` / `ac.array` 创建多个具有独立运行时状态的实例 |
| 同一个 ACIR module 用不同参数生成不同端口数量或拓扑 | 当前 executable lowering 不支持 | `static_args` 必须与定义的 `static_params` 完全相等，不能在 lowering 时把 `N=2` 和 `N=4` 展开成两种模块体 |
| 一个 Python component 定义按不同参数生成多个 ACIR specialization | 规范设计支持，前端尚未贯通 | Python elaboration 应为每组静态参数生成一个端口和拓扑均已固定的 concrete ACIR module |

推荐的分层模型是：

```text
Python component factory: Crossbar(n_in, n_out)
                 │ elaboration / specialization
                 ├── concrete ACIR module: Crossbar__2x2
                 └── concrete ACIR module: Crossbar__4x4
                                      │ ac.instance
                                      ├── instance A（独立状态）
                                      └── instance B（独立状态）
```

因此，当前缺口不是“ACIR 完全不能复用组件”，而是“前端尚不能把一个参数化源码定义
稳定地具体化为多个可执行 ACIR specialization”。

---

## 2. 冻结 ACIR 为什么不能充当模板

### 2.1 `static_params` 是已经解析的 specialization 数据

`ac.module` 的 `parameters {...}` 是具体 attribute 字典，不是带未绑定变量的模板形参。
模块括号内是普通函数类型参数，不能写成 C++ 模板式的 `@X(N = 2)`。

当前 ACIR→ACSim lowering 要求 placement 的静态实参与定义的冻结参数完全相等：

```cpp
// lib/Conversion/ACIRToACSim/ACIRToACSim.cpp
if (staticArgs && staticArgs != declaredParams)
  return lowerError(
      placement, "ACLOWER-PARAM-PHASE",
      "placement static arguments must exactly equal the frozen static parameters ...");
```

这些参数会进入 specialization 描述和指纹，也可以携带具体符号 attribute；但当前
lowering 不会把参数名替换到下面这些位置：

```mlir
ac.queue @q ... entries 4 ...
ac.array @workers ... shape [4] ...
```

这里的 `4` 必须在冻结 ACIR 中已经具体化。

### 2.2 `ac.array` 的“规范能力”和“当前可执行能力”不同

规范允许 `ac.array` 元素携带 index-derived static parameters；IR verifier 也要求每个
元素带一个具体静态参数字典。但当前 executable lowering 仍会逐个检查参数是否等于
目标 module 的冻结 `static_params`。

所以当前应表述为：

- `ac.array` 可以创建字面量 shape 的多个实例；
- IR/spec 为 per-element specialization 留有表示；
- 不同元素使用不同 specialization 的路径尚未由当前 v0.2 lowering 贯通；
- 它也不能从一个尚未求值的 `N` 自动得到 `shape [N]`。

### 2.3 `ac.module.generated` 尚不可执行

`ac.module.generated` 已有 IR 声明和 provider 注册检查，但当前 ACIR→ACSim lowering
明确以 `ACLOWER-UNSUPPORTED-CONSTRUCT` 拒绝它。因此它是预留接口，不是现阶段可用的
参数化组件路径。

---

## 3. 队列寻址和模块边界

### 3.1 queue runtime op 使用模块内符号

当前 queue 操作使用 `FlatSymbolRefAttr`：

```mlir
%head, %valid = ac.peek @in0 : i32
%accepted = ac.try_send @out0 %head : i32
```

它们不是 SSA queue handle，因此冻结后的 runtime process 不能写成下面这种动态索引：

```text
ac.try_send queues[%i], %value
```

如果 scheduler 要在当前 IR 中操作多个 queue，通常需要在 elaboration 时把访问展开为
`@in0`、`@in1`、……这些具体符号。

### 3.2 `IsolatedFromAbove` 不等于组件无法跨模块连接

`ac.module` 是 `IsolatedFromAbove`。直接使用 `@queue` 符号的 runtime op 必须解析到
所属模块中的资源；父模块 process 不能绕过组件边界直接操作子实例的内部 queue。

但这只限制“跨模块直接访问内部符号”，不排除正常的组件连接。一个可复用组件应通过
模块参数、结果、flow、endpoint 或 port 暴露接口，把内部 queue 和 scheduler 封装起来：

```text
parent flow/endpoint ── child public interface ── child internal queue/process
```

因此需要分别确认两个问题：

1. 内部 scheduler 对内部 queue 的访问——当前 native queue 路径已经支持；
2. public endpoint/flow 与内部 queue 之间的连接——这是构建真正可复用 router/crossbar
   仍需单独贯通和验证的边界。

“父进程不能直接驱动子 queue”是封装规则，不应被解释成“子模块不能实现 crossbar”。

---

## 4. elaboration 与运行时循环不是一回事

规范规定：创建拓扑的 Python 循环在 elaboration 阶段执行；process 中的运行时循环
可以保留为 `scf`。

### 4.1 Python elaboration 循环

它负责生成结构：实例数量、queue 数量、端口展开和 scheduler 的静态访问集合。

```python
@module
def crossbar(*, n_in: Static[int], n_out: Static[int]):
    # 概念示例：循环在 emit ACIR 前完成
    inputs = [make_input(i) for i in range(n_in)]
    outputs = [make_output(i) for i in range(n_out)]
```

完成 elaboration 后，ACIR 里只剩具体数量和具体符号，不保留 `n_in` 变量。

### 4.2 process 中的 `scf.for`

`scf.for` 属于运行时控制流，不创建 queue、实例或端口。它可以用于实现固定拓扑上的
scheduler 算法。

目前 crossbar 示例记录了 static `scf.for` 经 process-state expansion 时 proposal op
未被正确保留的问题。该问题应视为 process lowering 缺陷，并用最小失败测试固定；它
不是“ACIR 没有 elaboration”的证据，也不应作为结构生成路线。

---

## 5. 三条实现路线

### 路线 1：补齐 ACPy elaboration（推荐的长期方案）

让 Python 源码承担参数化定义，针对每组静态参数生成 concrete ACIR specialization。
生成后的 ACIR 只使用现有 primitive，不需要修改 ACIR public op inventory，也通常不需要
bump contract epoch。

这条路线最终可以提供接近“import 一个类，再按参数实例化”的源码体验；但其产物仍然
是多个冻结 specialization，而不是一个在 ACIR lowering 时展开的模板。

### 路线 1a：独立 Python ACIR 生成器（最短验证路径）

先写一个受测试约束的 Python 生成器，根据 `n_in` / `n_out` 输出完整 `.mlir`：

- 生成具体 queue 声明；
- 静态展开所有 queue 符号访问；
- 生成固定 scheduler；
- 输出 concrete module 和实例；
- 交给现有 freeze、ACIR→ACSim 和 C++ codegen。

它符合“拓扑在 Python elaboration 中生成”的分层原则，也能最快验证不同规模的
crossbar；但它绕过 ACPy 的 schema、normalize、ownership 和诊断体系，不能替代路线 1。

### 路线 2：在 ACIR 中新增 elaboration 机制（契约级方案）

可以设计 freeze 前展开的 `ac.static_for` / `ac.unroll`。如果该 op 在 freeze 前完全
消失，展开器可以直接生成具体 queue symbol，因此**不必然**要求 SSA queue reference。

只有希望循环保留到 freeze 后，并在运行时按索引选择 queue 时，才还需要：

- queue collection/reference 类型；
- index/select op；
- 动态或受限静态寻址语义；
- 对 ownership、effects、wake 和 codegen 的相应扩展。

这会改变“ACIR Core 不承担 elaboration”的现有边界，应独立设计和评审；不能把两种
方案默认捆绑。

---

## 6. ACPy 当前缺口

已有基础包括：

- `Static`、`Flow`、`Endpoint`、`ResourceRef` 等类型表面；
- `QueueSpec`、`queue()` 和 protocol/resource 验证数据模型；
- 静态表达式求值器对受限 `range`、tuple/list comprehension 的支持；
- ACPy entity inventory 中为 `static_if`、`static_for`、`collection`、`capture`、
  `escape` 等预留的实体种类；
- process CFG builder 和 effect 分类框架。

尚未形成闭环的部分是：

| 缺口 | 当前表现 | 需要完成的能力 |
|---|---|---|
| 结构 `for` / `if` normalization | module normalizer 仅接受有限语句，结构 `for` 会报 unsupported | 静态求值、稳定 expansion path、`static_for`/展开实体、确定性命名 |
| queue/protocol 进入 ACPy lowering | 已有 Python spec，但没有完整进入 normalized entity、所有权和 ACIR 发射 | queue/protocol 声明、符号分配、所属 module、时间域和容量发射 |
| queue process effects | 默认 registry 主要注册 suspension op | 注册并验证 `try_send`、`try_recv`、`peek`、`space` 等 effect 及结果 |
| process capture/resource resolution | `_emit_process` 当前拒绝 captures | 把 Python queue 引用解析为所属 module 的稳定 ACIR symbol |
| process CFG→ACIR | 只支持单 block、无 action、以 `yield_sim` 结束 | action、SSA、arith、`scf.if`、循环、assert 和 suspension 发射 |
| public interface→internal resource | 尚缺少可复用组件的端到端证据 | endpoint/flow/port 与内部 queue/process 的连接和 lowering |
| specialization manager | 尚不能从同一 Python 定义产生并缓存多个具体 ACIR module | specialization key、稳定符号、去重、指纹和调用点重写 |

不宜用“完成约 30%”描述当前状态，因为缺少统一统计口径。更准确的结论是：数据模型、
规范和部分分析框架已存在，但真实 queue-based component 的前端到 runtime 闭环尚未完成。

---

## 7. 推荐实施顺序及逐步验证

### 第 1 步：固定最小目标语义

定义一个固定 1-in/1-out module：内部一个 queue、一个 producer process、一个 consumer
process；先不引入参数化和跨模块 endpoint。

**验证：** 手写等价 ACIR 能 freeze、lower、生成 C++ 并运行，统计满足无丢失、无重复。

### 第 2 步：让 queue 声明进入 ACPy/ACIR

把已有 `QueueSpec` 接入 normalized ownership 和 `_lower_acir.py`，生成稳定的
`ac.protocol` / `ac.queue` 声明。

**验证：** Python 输入生成的 ACIR 与 golden 一致；重复运行字节级确定；非法容量、类型、
重复符号和跨 module 所有权均有负测试。

### 第 3 步：注册 queue effects 和 capture

在 process 构造前注册 queue runtime op，建立 Python queue 引用到 ACIR queue symbol 的
解析，允许 process 捕获合法的 module-owned resource。

**验证：** `try_send` / `try_recv` / `peek` / `space` 的正负构造测试；跨模块直接引用被
稳定诊断。

### 第 4 步：打通直线 process action 发射

先支持 constant、基础 arith、单次 queue op、assert 和 `yield_sim`，不立即实现完整 CFG。

**验证：** 第 1 步模型完全由 Python 生成，并通过 ACIR verifier、ACSim verifier、C++
编译和运行时检查。

### 第 5 步：支持条件控制和背压

增加 queue op 的多结果 SSA、`scf.if` 和失败重试/`await_queue` 路径。

**验证：** 深度 1 queue 在下游暂停时不丢数据，恢复后继续；两次运行输出完全一致。

### 第 6 步：支持结构 elaboration

实现 module body 的静态 `for` / `if`、collection canonicalization、稳定 expansion path，
把固定规模的重复实例规范化为 `ac.array` / `ac.instances`，把 queue 符号访问展开。

**验证：** `N=1/2/4` 生成正确数量的实例、queue 和访问；静态展开上限、非静态条件、非法
迭代器均有负测试。

### 第 7 步：实现 specialization 管理

同一 Python component 用不同静态参数时生成不同 concrete module symbol；相同参数去重，
同一 concrete module 可以多次实例化并拥有独立状态。

**验证：** 同一设计同时包含 2×2 和 4×4 specialization；两个 2×2 实例共享定义但不
共享 mutable state；manifest 和 fingerprint 稳定。

### 第 8 步：贯通 public endpoint/flow 与内部 queue

定义组件 public interface，连接父模块和子模块，不允许父 process 直接访问子内部符号。

**验证：** 两级 router/crossbar 组合可以通过公开接口传输；故意引用子内部 queue 时
verifier 报错；生成代码不需要 extern binding/provider。

### 第 9 步：参数化 crossbar 端到端

生成 N×M input/output queues 和静态展开的 matching scheduler，覆盖竞争、背压、公平性
策略、无丢失和确定性。

**验证：** 至少运行 1×2、2×2、2×3；每个配置做生成物结构检查、C++ 编译运行、统计
守恒和双运行确定性检查。

---

## 8. 近期建议

1. 用路线 1a 快速证明 1×2、2×2、2×3 concrete ACIR 都能端到端运行；
2. 同时按第 1～5 步打通 ACPy 的最小 native queue process；
3. 在推进 N×M elaboration 前，先决定 public endpoint/flow 如何映射到内部 queue；
4. 不把 `scf.for` proposal bug、per-element specialization 和 generated module 当作已经
   可执行的能力；分别建立最小测试和 capability ledger；
5. 路线 2 只有在确实需要“ACIR 文本自身就是模板”时再立项。

---

## 9. 关键证据索引

- module / instance / array 定义：`include/acir/Dialect/ACIR/ACIROps.td`
- static argument equality：`lib/Conversion/ACIRToACSim/ACIRToACSim.cpp`
- generated module rejection：`lib/Conversion/ACIRToACSim/ACIRToACSim.cpp`
- queue runtime op 的符号 operand：`include/acir/Dialect/ACIR/ACIROps.td`
- Python elaboration 与 process loop：`docs/specs/acir-core-v0.2.md`
- Python-to-ACIR 静态控制与 collection：`docs/specs/python-to-acir-lowering-v0.2.md`
- ACPy module normalizer：`src/agentic_circuit/_normalize.py`
- ACPy queue/resource 数据模型：`src/agentic_circuit/_resources.py`
- ACPy effect registry：`src/agentic_circuit/_frontend.py`
- ACPy process emission：`src/agentic_circuit/_lower_acir.py`
- process static-for expansion：`lib/Analysis/ProcessStateExpansion.cpp`
