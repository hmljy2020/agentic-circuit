# ACIR v0.3 DavinciOO Core Profile 能力缺口审计

## 1. 审计信息

```text
date:       2026-08-25
baseline:   b9cccf2 + P0 documentation commit f6a9d30
target:     acir-v03-davincioo-primitive-contract.md
scope:      read-only ACIR contract audit
```

本阶段只读取以下 B 类路径，没有修改 ACIR dialect、schema、contract inventory 或
后端实现：

```text
include/acir/Dialect/ACIR/
lib/Dialect/ACIR/
test/ACIR/
contracts/acir-v0.1.yaml
schemas/component.schema.json
schemas/stdlib/
```

## 2. 总结

当前 ACIR 是闭合且有测试覆盖的 epoch v0.1，但其核心模型与目标 v0.3 不同：

```text
current v0.1:
  ac.module/ac.instance hierarchy
  + symbolic owned-state ac.queue
  + endpoint/flow/channel protocol types
  + process try_send/try_recv effects

target v0.3:
  ac.module Graph hierarchy
  + linear !ac.queue<T, contract> SSA values
  + official Queue-in/Queue-out primitive ops
  + pure !ac.var<T> compute regions
```

可直接复用的主要基础只有：

- `ac.system` 选择 root module 的总体结构；
- `ac.module` 的 Graph region；
- Graph region 中 SSA 前向引用和循环；
- `ac.instance`/`ac.return` hierarchy 基础；
- `ac.struct`、`ac.enum` 和相关 named payload types；
- `ac.record.create/get/with` 的部分 immutable record 操作；
- native parser/verifier、contract inventory 和 lit coverage 基础设施。

不能直接复用的核心部分包括：

- 当前 `ac.queue` 是无 SSA result 的父拓扑 owned-state symbol，和目标
  Queue→Queue transport primitive 同名但语义相反；
- 不存在 `!ac.queue<T, QueueContract>`；
- 不存在 `!ac.var<T>`；
- 不存在 typed Queue contract、field descriptor 和 policy attributes；
- 不存在 named variadic operand/result segment contract；
- 13 个目标 primitive 没有对应 ODS ops；
- v0.1 stdlib schema 使用 endpoint/flow 和 `ac.std.*`，不能作为 v0.3 BlockSpec；
- Graph verifier 当前只允许既有 structural children，尚不允许目标 primitive ops。

结论：P2 的 ACPy semantic graph 可以在 A 类范围独立实现；P3 开始的 native
ACIR round-trip 需要先完成最小共享 contract 变更。

## 3. 基础类型与属性

| 目标 | 当前能力 | 结论 | 所需 contract change |
| --- | --- | --- | --- |
| `!ac.var<T>` | 不存在 | 缺失 | 新增 Var type，冻结其仅组合、无 occupancy/backpressure 语义 |
| `!ac.queue<T,C>` | 不存在；仅有 `!ac.flow`/`!ac.channel` | 缺失 | 新增 linear Queue SSA type |
| QueueContract | owned `ac.queue` op 有 entries/delay 等零散 attrs | 不兼容 | 新增 typed `#ac.queue_contract<depth,latency,rate,domain>` |
| struct payload | `!ac.struct<@types::@S>` + `ac.struct` | 可复用 | epoch/layout 规则需要复核，不必重造基础结构 |
| enum payload | `!ac.enum<...>` + `ac.enum` | 可复用 | 补齐冻结 layout/width policy |
| fixed array payload | `!ac.vector<N x T>` | 部分可用 | 决定新增 `!ac.array<N,T>`，或明确 vector 即 canonical array；当前 contract 要求前者 |
| union payload | 已存在 | 可复用但非当前必需 | 第一版 DavinciOO 不依赖 |
| field descriptor | record ops 使用非类型化字符串 field attr | 缺失 | 新增 canonical typed `#ac.field<Root::path>` |
| policy | schema/dictionary/string 分散表达 | 缺失 | 新增 closed typed `#ac.policy<...>` |
| Queue domain | 仅 `ac.event_queue`/`ac.time_domain` symbol attrs | 不兼容 | QueueContract 引用冻结 time domain identity |

### 最小目标类型示例

```mlir
!ac.queue<
  !ac.struct<@types::@PTOInst>,
  #ac.queue_contract<depth = 4, latency = 1, rate = 1, domain = @core>
>

!ac.var<!ac.struct<@types::@PTOInst>>

#ac.field<@types::@PTOInst::sources>
#ac.policy<oldest, by = #ac.field<@types::@PTOInst::rob_id>>
```

预期 verifier：

- depth/latency/rate 必须为正且冻结；
- Queue payload 不能嵌套 Queue；
- field root/path/leaf type 必须可解析；
- policy kind 和必需参数来自闭集；
- v0.1 flow/channel/owned queue 不能静默解释为 v0.3 Queue SSA。

## 4. Graph 与 hierarchy

| 能力 | 当前状态 | 结论 |
| --- | --- | --- |
| Graph region | `ac.module` 已使用 `HasOnlyGraphRegion` | 可复用 |
| 前向 SSA use | `hierarchy-valid.mlir` 已覆盖 | 可复用 |
| cyclic SSA | 同一测试已有双 instance cycle | 可复用基础机制 |
| cycle timing proof | 依赖 v0.1 instance/state boundary | 需升级到 QueueContract latency |
| scope outlining | 可通过 `ac.module` + `ac.instance` 表达 | 可复用，但与文档中的 `ac.scope` 拼写需要对齐 |
| primitive graph child | verifier 只接受固定 v0.1 structural op 集合 | 缺失 |
| Queue producer/use verifier | 面向 instance/value 与 owned symbol reference | 需新增 v0.3 linear Queue 检查 |

当前 `isStructuralGraphChild` 不接受任何目标 primitive op。新增 primitive 时必须同步
扩展 Graph child、producer/use、cycle timing 和 topology type verifier。

### Scope contract 待对齐项

目标文档目前列出 `ac.scope/ac.scope_yield`，而现有 ACIR 已有成熟的
`ac.module/ac.instance/ac.return` hierarchy。侵入性最小的方向是：

```text
ACPy with ac.scope(...)
  -> outline ac.module
  -> parent ac.instance
  -> ac.return
```

是否删除新 `ac.scope` IR op 的要求属于共享 contract 决定；P2 可以先使用抽象
`Scope` 节点，不依赖最终 ODS 拼写。

## 5. Variadic port groups

当前 `ac.instance`、`ac.array` 和 `ac.instances` 支持一个 variadic inputs group 和
一个 variadic outputs group，并使用 functional type 校验总 arity。

目标 primitive 需要多个命名 group，例如：

```text
ac.issue:
  operands = enqueue | wakeup | recheck_response
  results  = issued | recheck_request

ac.table:
  operands = access | update | query
  results  = accessed | updated | response
```

当前没有：

- `AttrSizedOperandSegments`；
- `AttrSizedResultSegments`；
- 等价的 named segment size attributes/verifier；
- 各 segment 的 payload relation。

因此“支持 variadic SSA”只能算部分基础，不能视为支持目标 named port groups。

### 最小目标示例

```mlir
%issued, %request = ac.issue
  enqueue(%enqueue)
  wakeup(%wakeup)
  recheck_response(%response)
  {...}
  : (...) -> (...)
```

预期 verifier 必须按 segment 分别检查 arity 和 payload，而不是只检查 operands
总数。

## 6. Pure compute/Var region

当前可复用：

- `ac.record.create`；
- `ac.record.get`；
- `ac.record.with`；
- MLIR builtin integer/float types；
- 已有 record declaration/layout verifier。

当前缺失：

- `ac.compute` Queue→Queue op；
- `!ac.var<T>` block argument/result type；
- pure region signature verifier；
- closed const capture；
- `ac.var.array/extract/select/unary/binary/compare/cast/yield`；
- compute region 禁止 Queue/state effect 的 verifier；
- nested field path 和多字段 immutable update canonicalization。

现有 record ops 可以作为部分实现基础，但不能单独构成冻结的 canonical Var region。

## 7. Primitive 逐项审计

| Primitive | 当前相近能力 | Type/ODS | Port groups | Verifier | Round-trip | 结论 |
| --- | --- | --- | --- | --- | --- | --- |
| `source` | `ac.trace.*` process effects、`ac.std.TraceSource` schema | 无目标 op | 无 | 无 | 无 | 新增 |
| `sink` | available `ac.std.Sink` endpoint component | 无目标 op | 不兼容 | 无目标 verifier | 无 | 新增 |
| `observe` | `ac.probe/stat` 使用 symbol target | 无 Queue-value observe | 不兼容 | 无 non-consuming Queue use | 无 | 新增 |
| `compute` | available `ac.std.Compute`、record ops | 无目标 op/region | 旧 endpoint 1:1 | 无 pure Var verifier | 无 | 新增 |
| `queue` | owned-state symbol `ac.queue` | 同名冲突 | 无 Queue SSA operand/result | verifier 语义相反 | 仅 v0.1 | 替换/epoch hard break |
| `route` | unavailable `ac.std.Router` | 无目标 op | 旧 schema 仅 1 in/1 out | 无 selector/result verifier | 无 | 新增 |
| `fork` | unavailable `ac.std.Fork/Broadcast` | 无目标 op | 无 strict variadic results | 无 atomic fanout verifier | 无 | 新增 |
| `merge` | unavailable `ac.std.Arbiter` | 无目标 op | 无 variadic inputs | 无 policy verifier | 无 | 新增 |
| `pool` | `ac.resource` owned-state symbol | 无目标 op | 不兼容 | 无 acquire/release transaction | 无 | 新增 |
| `table` | unavailable `ac.std.Scoreboard` 等 schema | 无目标 op | 无 access/update/query groups | 无 action/linearization verifier | 无 | 新增 |
| `reorder` | 无 | 无 | 无 | 无 | 无 | 新增 |
| `issue` | available `ac.std.Scheduler` 但仅 FIFO-like endpoint | 无目标 op | 无 wakeup/recheck groups | 无 resident/dependency verifier | 无 | 新增 |
| `engine` | `ac.resource` + component instance | 无目标 op | 无 Queue SSA completion | 无 latency_by verifier | 无 | 新增 |

旧 stdlib schema 即使 canonical name 接近，也不能作为“已有 primitive”计数，因为：

- contract epoch 是 0.1；
- 名称为 `ac.std.*`；
- 端口使用 endpoint/interface/protocol；
- 多数相关 schema 标记为 `declared_unavailable`；
- schema 不能表达目标 named Queue groups 和 typed descriptor。

## 8. BlockSpec/schema 缺口

当前 `schemas/component.schema.json` 是 v0.1 ComponentSchema，主要字段是：

```text
bindings/results/resources/address_behavior/protocol_contracts/effect/activation
```

目标 BlockSpec 还需要：

```text
opcode + contract epoch/version
named variadic operand/result groups
Queue payload relations
Queue port constraints
typed static parameters
field/policy/table-action descriptors
atomic transaction groups
timing/backpressure
design/verification/observation role
gfsim and PYC/Verilog provider identities
refinement observations
```

不能在现有 v0.1 schema 中塞入 optional 私有字段；应按 hard-break 方式建立新的
versioned BlockSpec，并同步生成 ODS/catalog/verifier metadata。

## 9. 必需的共享 Contract Change 集合

### `B1`：v0.3 types/attributes

```text
!ac.var
!ac.queue
!ac.array（或对 vector 的明确替代决定）
#ac.queue_contract
#ac.field
#ac.policy
```

### `B2`：Graph/topology verifier 升级

```text
允许 official primitive graph children
Queue unique producer / consuming-use verifier
observe non-consuming exception
named segment verifier support
Queue cycle latency boundary
v0.1 owned queue 与 v0.3 queue op hard break
```

### `B3`：最小纵向 primitive

```text
ac.source
ac.compute
ac.observe
canonical ac.var region ops
```

这是 P3 native parser/verifier 的最小 blocker。

### `B4`：静态 topology primitives

```text
ac.queue
ac.route
ac.fork
ac.merge
```

### `B5`：状态与调度 primitives

```text
ac.pool
ac.table
ac.reorder
ac.issue
ac.engine
```

### `B6`：BlockSpec 单一事实源

```text
v0.3 BlockSpec schema
ODS/catalog metadata generation or exact checked inventory
positive/negative/round-trip coverage requirement
provider capability inventory
```

### `B7`：contract epoch inventory

```text
contracts/acir-v0.3.yaml
parser rejection of incompatible v0.1 artifact
schema/capabilities/manifest epoch alignment
```

这些 change 必须分开审阅，不与普通 A 类 frontend 实现混成一个提交。

## 10. P2/P3 的执行边界

P2 可以立即实现：

```text
typed Program/Scope/BlockInstance
named PortGroup
QueueValue/QueueConstraint
payload/field/policy semantic records
VarRegion semantic representation
deterministic semantic snapshot
```

P2 不应：

- 修改 ODS；
- 输出 unregistered/private ACIR；
- 假设 v0.1 endpoint/owned queue 等于 v0.3 Queue SSA；
- 把 target primitives 临时 lower 为语义不等价的 `ac.instance`。

P3 在 `B1+B2+B3` 落地前可以完成 AST→semantic graph 和期望 ACIR golden 设计，
但不能把 native parser/verifier gate 标记为通过。

## 11. 审计完成结论

```text
P1 status: complete
P2 status: ready
P3 ACIR contract blocker: B1 + B2 + B3
downstream implementation: not required for P2/P3 frontend semantic work
```

本审计没有修改任何 B/C/D 类文件。
