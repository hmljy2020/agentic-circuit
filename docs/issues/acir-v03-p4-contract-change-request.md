# ACIR v0.3 P4 静态拓扑 Contract Change 请求

## 1. 请求结论

P4 前端已经能稳定产生 `queue/route/fork/merge`、typed selector/policy 和推导后的
scope I/O semantic graph。要让同一拓扑通过 native ACIR round-trip，需要批准以下
最小共享 contract patch：

```text
B1-P4: #ac.field、#ac.policy
B2-P4: v0.3 transport graph child、Queue linearity 扩展、scope outline
B4-P4: ac.queue、ac.route、ac.fork、ac.merge
```

本请求不包含 P5 deferred/cycle、不包含 pool/table/reorder/issue/engine，也不修改
ACIR→ACSim、gfsim 或 CodeGen。

## 2. Motivation

当前 P4 semantic artifact 已经明确区分：

- port arity：route/fork 的 result 数、merge 的 operand 数；
- Queue rate：每条 `!ac.queue` type 中的 contract；
- payload shape：Queue element type；
- selector/policy：typed static attribute；
- hierarchy：scope lexical def-use 推导出的 module operands/results。

当前 dialect 只注册 P3 的 `source/compute/observe`。用 generic op、字符串字段名或
pairwise merge tree 都会丢掉冻结语义，因此不能作为临时 lowering。

## 3. Proposed canonical attributes

### `#ac.field`

```mlir
#ac.field<
  root = !ac.struct<@types::@Packet>,
  path = ["kind"],
  leaf = i1
>
```

约束：

- root 必须是可解析的 named payload type；
- path 非空，每一段必须从前一类型解析；
- leaf 必须等于解析得到的最终 field type；
- route 的 field root 必须等于 input Queue payload。

### `#ac.policy`

P4 只打开无参数 `round_robin`：

```mlir
#ac.policy<kind = round_robin>
```

`priority/oldest` 需要 typed field 参数，留到使用它们的后续阶段再打开；不接受任意
字符串 policy。

## 4. Proposed transport operations

### `ac.queue`

```mlir
%buffered = ac.queue %input
  : !ac.queue<T, #input_contract>
 -> !ac.queue<T, #output_contract>
```

- 一输入一输出，payload 必须相同；
- input/result 是两条不同 Queue SSA edge；
- storage/timing 只来自 result Queue contract；
- 它是显式 transport block，裸 def-use 不生成该 op。

当前 v0.1 已有同名 owned-state `ac.queue @symbol ...`。建议保留一个注册 op，使用
custom parser/printer 和 epoch verifier 区分两种互斥 form：

```text
epoch 0.1: symbol-owned form only
epoch 0.3: Queue SSA transport form only
```

这样既不重解释旧 artifact，也不引入违反冻结名称的私有 `ac.transport`。

### `ac.route`

```mlir
%lane0, %lane1 = ac.route %input by #selector
  : (!ac.queue<T, #in>)
 -> (!ac.queue<T, #out0>, !ac.queue<T, #out1>)
```

- 一个 input，至少一个 result；
- 所有 result payload 等于 input payload；
- P4 direct-index profile 要求 selector 是整数 field 且 result 数覆盖其全部值；
- 单目标 delivery，只受选中 result 的 backpressure。

### `ac.fork`

```mlir
%left, %right = ac.fork %input
  : (!ac.queue<T, #in>)
 -> (!ac.queue<T, #left>, !ac.queue<T, #right>)
```

- 一个 input，至少一个 result；
- strict atomic broadcast；
- 所有 result payload 等于 input payload；
- 不保存 partial branch delivery 状态。

### `ac.merge`

```mlir
%joined = ac.merge (%left, %right) policy #ac.policy<kind = round_robin>
  : (!ac.queue<T, #left>, !ac.queue<T, #right>)
 -> !ac.queue<T, #out>
```

- 至少一个 input，一个 result；
- 所有 input/result payload 相同；
- input arity 从 operands 推导，不保存 count；
- frozen ACIR 不展开为 pairwise tree。

## 5. Scope lowering decision

采用已经确认的 outline 写法，不新增 `ac.scope/ac.scope_yield`：

```text
ACPy Scope
  -> ac.module（推导后的 Queue 参数/结果）
  -> 父 ac.module 中的 ac.instance
  -> 子 module 中的 ac.return
```

module symbol 使用完整 scope path 生成稳定且无冲突的名字；instance identity 使用
semantic scope identity。`ac.module/ac.instance/ac.return` 的现有 hierarchy verifier
继续负责签名对齐。

## 6. Native verifier additions

1. 四个 op 只允许在 epoch 0.3，且必须是 `ac.module` Graph 直接 child；
2. Queue payload relation、最小 arity和 attribute 闭集按上述规则检查；
3. Queue consuming-use 分类加入 queue/route/fork/merge/instance；
4. `observe` 保持 non-consuming，`return` 保持 hierarchy transfer；
5. outlined module argument/result与 `ac.instance` signature 继续精确一致；
6. text→text、bytecode round-trip 和非法 fixture 必须通过 native gate。

## 7. Downstream impact

后端会新增四个 Provider/Conversion capability，但 P4 前端 gate 不要求这些 Provider
已经实现。旧 epoch 0.1 owned Queue 的 parser/verifier 行为保持不变。P4 patch 不触碰
backend C 类路径。
