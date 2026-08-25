# ACIR v0.3 DavinciOO Core Profile：Primitive 冻结决定

## 1. 状态与适用范围

本文冻结当前 DavinciOO ACPy → frozen ACIR 前端所需的最小 primitive 闭集、
端口分组和结构语义。

本文的目标是使 `docs/issues/davincioo.py` 能够完整 lowering，且不引入
`rename`、`ready_table`、`dispatch` 等应用专用 opcode。本文不试图提前定义未来
所有硬件场景需要的通用积木。

在当前 DavinciOO 前端设计范围内：

- Issue #9、#10、#11、#14 提供总体目标和候选 catalog；
- `acpy-v03-confirmed-semantics.md` 冻结 ACPy 与拓扑语义；
- 本文冻结第一版 ACIR primitive inventory 和各 primitive 的结构 contract；
- Provider 内部数据结构、同 epoch 调度顺序和最终 ODS attribute 文本拼写不由
  本文冻结，但不得改变本文规定的端口、状态和 transaction 语义。

## 2. ACIR 结构与类型

以下构件是 frozen ACIR 的结构和类型系统，不属于硬件 primitive catalog，也不
绑定独立 Provider：

```text
structure:
  ac.system
  ac.scope
  ac.scope_yield

types:
  !ac.var<T>
  !ac.queue<T, QueueContract>
  !ac.struct<...>
  !ac.array<N, T>
  !ac.enum<...>

attributes:
  #ac.queue_contract<depth, latency, rate, domain>
  #ac.field<Root::path>
  #ac.policy<...>
```

`ac.system` 和 `ac.scope` 内部使用 graph-region 语义，允许反馈 Queue 形成循环
SSA def-use。每个循环仍必须包含至少一个 `latency >= 1` 的 stateful Queue edge。

`ac.scope` 只保留组合 hierarchy。其 Queue operands/results 由 ACPy lexical
def-use 推导，不能成为应用专用 opcode。

## 3. 第一版 primitive 闭集

```text
boundary:
  source, sink, observe

compute:
  compute

transport:
  queue, route, fork, merge

storage:
  pool, table

scheduling:
  reorder, issue

execution:
  engine
```

第一版共 13 个 primitive。未列在这里的名字不能由当前 ACPy 前端发射为
DavinciOO Core Profile 的 frozen ACIR leaf。

## 4. 所有 primitive 的共同约束

动态端口只通过 Queue SSA operands/results 表达：

```text
Variadic<!ac.queue<T>> operands
Variadic<!ac.queue<U>> results
```

共同规则如下：

1. 每个 Queue value 有且只有一个 producer。
2. 默认最多有一个 consuming use；`observe` 是非消费 use。
3. 多消费者必须显式经过 `ac.fork`。
4. 多 producer 必须显式经过 `ac.merge`。
5. port arity、Queue rate 和 payload shape 是不同概念，不能相互代替。
6. port arity 从 SSA operand/result segment 推导，不保存重复的 count attribute。
7. Queue 的 depth、latency、rate 和 domain 存在于 frozen Queue type，不在相邻
   primitive 上重复保存。
8. 父 topology 物理拥有 interconnect Queue；primitive Provider 只借用 typed
   endpoint。
9. 一个 primitive transaction 涉及的输入消费、输出产生和状态更新必须全部
   接受或全部拒绝。
10. payload immutable；任何字段变化都产生新的 SSA token。

## 5. Boundary primitives

### 5.1 `ac.source`

```text
() -> Queue<T>
```

- 从 harness 向系统产生 token；
- payload、rate 和 domain 由 result Queue type 确定；
- frozen ACIR 不携带 Python callback；
- harness binding 通过稳定 boundary identity 和 manifest 指定。

### 5.2 `ac.sink`

```text
Queue<T> -> ()
```

- 真正消费 token；
- 参与 backpressure；
- 占用 Queue 的一个 consuming use。

### 5.3 `ac.observe`

```text
Queue<T> -> ()
```

属性：

```text
name
fields: Array<FieldDescriptor>
```

- non-consuming；
- non-backpressuring；
- 不修改功能状态；
- 不计入 Queue consuming-use verifier。

## 6. Compute primitive 与 Var region

### 6.1 `ac.compute`

```text
Queue<T> -> Queue<U>
region: Var<T> -> Var<U>
```

- 无持久状态、严格 1:1；
- 接受一个输入 token 时恰好产生一个输出 token；
- 不丢弃、复制或合并 token；
- 保持 FIFO 顺序；
- region 只能操作 `ac.var` 并捕获 closed `ac.const`；
- block 自身不增加 latency，但输出 Queue edge 仍必须满足其 frozen contract。

第一版 canonical Var region op family 为：

```text
ac.var.constant
ac.var.struct
ac.var.get
ac.var.update
ac.var.array
ac.var.extract
ac.var.unary
ac.var.binary
ac.var.compare
ac.var.select
ac.var.cast
ac.var.yield
```

`with_fields` lower 为 `ac.var.update`，不是 Queue 方法或独立硬件 primitive。

## 7. Transport primitives

### 7.1 `ac.queue`

```text
Queue<T, Cin> -> Queue<T, Cout>
```

- 显式增加一个 transport boundary；
- 不修改、丢弃或复制 payload；
- operand 和 result 是两条不同的 Queue SSA edge；
- 新 transport 的容量、延迟、rate 和 domain 由 result Queue contract 表达；
- 裸 ACPy def-use 不生成 `ac.queue` op。

### 7.2 `ac.route`

```text
input(Queue<T>) -> outputs(Variadic<Queue<T>>)
```

属性：

```text
by: FieldDescriptor
mapping/default policy
```

- 确定性单目标分流；
- 每个 token 只进入一个 result；
- 只受被选 result 的 backpressure；
- result arity 直接由 results 推导；
- selector 必须静态证明覆盖全部值，或显式提供 default result；
- 输入 `rate > 1` 时仍只处理连续 FIFO prefix。

### 7.3 `ac.fork`

```text
input(Queue<T>) -> outputs(Variadic<Queue<T>>)
```

- strict atomic broadcast；
- 一个输入 token 同时复制到全部 results；
- 任一 result 不能接受时不消费输入；
- primitive 不保存 partial branch delivery 状态；
- 第一版不保留独立 `broadcast` alias。

### 7.4 `ac.merge`

```text
inputs(Variadic<Queue<T>>) -> output(Queue<T>)
```

属性：

```text
policy: #ac.policy<round_robin | priority | oldest, ...>
```

- 多输入、单输出确定性仲裁；
- input arity 由 operands 推导；
- frozen ACIR 不预先展开为 pairwise merge tree；
- `oldest` 等 policy 使用 typed field descriptor，不使用字符串字段名。

## 8. Storage primitives

### 8.1 `ac.pool`

```text
acquire(Variadic<Queue<A>>)
release(Variadic<Queue<R>>)
  -> acquired(Variadic<Queue<A>>)
```

必要参数和 descriptor：

```text
entries
acquire_group
acquire_valid
acquire_result
release_group
release_valid
release_key
```

语义：

- 管理有限且唯一的资源 ID 集合；
- 为 acquire token 中所有 valid element 原子分配资源；
- 资源不足时不消费 acquire token；
- 分配结果通过 immutable payload update 写入 acquired result；
- release token 回收其中的 valid resource ID；
- 一个 acquire transaction 不允许部分分配。

DavinciOO 使用它分配 VersionTag，并在退休时回收 `old_tag`。

### 8.2 `ac.table`

`ac.table` 是持久化 `Key -> Value/present` 状态，不是 SMAP 或 ReadyTable 专用
opcode。

端口分组固定为：

```text
access(Variadic<Queue<A>>)
update(Variadic<Queue<U>>)
query(Variadic<Queue<Q>>)
  ->
accessed(Variadic<Queue<A>>)
updated(Variadic<Queue<U>>)
response(Variadic<Queue<R>>)
```

允许的 typed table action 闭集为：

```text
read:
  key + valid -> value/result + optional present

write:
  key + valid + value/constant

exchange:
  key + valid + new value -> old value + old-present

query:
  request key/group -> response value/group

copy:
  request correlation field -> response correlation field
```

语义：

- 同一 access token 上的所有 action 原子执行；
- action descriptor 可以规定 `read_before_write`；
- access、update、query transaction 之间必须有确定且可串行化的线性化顺序；
- action 只能来自上述闭集，不能携带任意 lambda；
- 每组 input/result arity 和 payload relation 由 BlockSpec verifier 检查。

DavinciOO 中的两种组合为：

```text
SMAP:
  access = source address read + destination address/tag exchange

ReadyTable:
  access = source tag readiness read + destination tag clear
  update = completed destination tag set-ready
  query  = resident instruction readiness recheck
```

因此不生成 `ac.rename` 或 `ac.ready_table`。

## 9. Scheduling primitives

### 9.1 `ac.reorder`

```text
enqueue(Queue<T>)
completed(Queue<T>)
  ->
admitted(Queue<T>)
retired(Queue<T>)
```

必要参数和 descriptor：

```text
entries
identity
allocate_identity
policy = in_order
```

语义：

- enqueue 按程序顺序分配 resident entry 和 identity；
- admitted 是写入 identity 后的新 immutable token；
- completed 按 identity 标记 resident entry 完成；
- completion 可以乱序到达；
- 只有连续完成的 head entries 可以产生 retired；
- retired 保持程序顺序；
- 退休吞吐由 retired Queue rate 表达，不重复保存 width 属性。

### 9.2 `ac.issue`

端口分组固定为：

```text
enqueue(Variadic<Queue<T>>)
wakeup(Variadic<Queue<W>>)
recheck_response(Variadic<Queue<R>>)
  ->
issued(Variadic<Queue<T>>)
recheck_request(Variadic<Queue<Q>>)
```

必要参数和 descriptor：

```text
entries
policy

dependencies
dependency_key
dependency_valid
dependency_ready

wakeup_produces
wakeup_key

correlate_by
recheck_request_correlate
recheck_request_dependencies
recheck_response_correlate
recheck_response_ready
recheck_combine
```

语义：

- not-ready instruction 可以进入 resident window；
- admission 必须原子创建 resident entry 和 recheck request；
- request 不能在 entry resident 之前发出；
- response 返回前 entry 标记为 `pending_recheck`，不可参与 issue selection；
- wakeup 按 dependency key 更新 resident source-ready bits；
- response 按 correlation key 精确匹配 live resident entry；
- 初始 ready、recheck response 和 wakeup 按 `recheck_combine` 合并；
- DavinciOO 第一版使用 `monotonic_or`，迟到的 false response 不能清除已经收到的
  true wakeup；
- wakeup traffic 不能被 enqueue backpressure 或 pending response 阻塞；
- selection 可以越过 not-ready resident entry；
- ready entries 的选择顺序由 policy 决定。

DavinciOO 第一版由 Python 静态展开为每个 Engine lane 一个 singleton-port
`ac.issue`，不生成一个共享 entries 的集中式 Issue op。

## 10. Execution primitive

### 10.1 `ac.engine`

```text
input(Queue<T>) -> completed(Queue<T>)
```

必要参数：

```text
latency_by: FieldDescriptor
inflight
initiation_interval
kind
```

- 接受 instruction token，并在配置的延迟后产生 completion token；
- completion payload 保持同一个 immutable payload type；
- `inflight` 限制内部并发；
- 不接受 lambda；
- 多个 Engine results 必须在父 topology 中显式经过 `ac.merge`。

## 11. ACPy-only 构造

以下构造只存在于 Python elaboration/frontend，不进入 primitive catalog：

```text
@ac.config
ac.const
ac.jit
ac.queue.deferred
Python tuple/list
Python for/range
普通 Python helper
with_fields 方法
Queue method-call sugar
```

lowering 规则：

- `deferred` 在 bind 后消失，只保留真实 Queue SSA edge；
- const loop 静态展开 primitive instances；
- tuple/list 只承载静态端口集合，frozen ACIR 使用展开后的 operand/result segments；
- `with_fields` lower 为 `ac.var.update`；
- `q.route(...)` 规范化为 `ac.route(q, ...)`；
- `decode`、`dispatch`、`rename`、`ready_table`、`execute` 和 `retire` 只能是 scope
  名称或 composition，不是 opcode。

Queue 不向 ACPy 用户暴露 `peek/pop/push`，也不把 `ac.atomic` 作为当前公共
primitive。Provider 内部的 pop/push/ready-valid 行为由 BlockSpec transaction
语义约束。

## 12. 暂缓进入 catalog 的候选项

下列名字虽然出现在 Issue #10/#14 的候选集合中，但当前 DavinciOO 样例尚未给出
足够明确且不可由第一版闭集表达的应用场景，因此本次不冻结：

```text
broadcast
transform, predicate, reduce, scan
select
join, crossbar, pipeline
state, delay, counter, feedback
arbitrate, reserve, release
credit, barrier
memory
adapt, cdc
assert, probe
```

当前归并规则：

- `broadcast` 统一为 `fork`；
- `transform/predicate/reduce/scan` 暂由 `compute` 的纯 Var region 表达；
- `arbitrate` 暂作为 `merge` 或 `issue` 的 policy，而不是独立 block；
- 其余 primitive 只有在出现明确用例并确认端口、状态、timing 与 backpressure
  语义后才能加入后续 contract epoch/profile。

## 13. DavinciOO 覆盖性

该闭集直接覆盖当前目标拓扑：

```text
source
  -> compute(decode)
  -> reorder
  -> pool(tag allocation)
  -> table(SMAP)
  -> route
  -> table(ReadyTable access/update/query)
  -> per-lane issue
  -> per-lane engine
  -> merge
  -> table completion update
  -> fork(Issue wakeup + ROB completed)
  -> reorder retirement
  -> pool release
  + observe
```

其中 missed-wakeup 问题正式由以下 ACIR 端口表达：

```text
issue.recheck_request -> table.query
table.response -> issue.recheck_response
```

该协议属于 `table` 与 `issue` 的正式 BlockSpec contract，不能被 frontend 私下
实现为 callback、隐藏状态或未声明的跨 primitive 调用。
