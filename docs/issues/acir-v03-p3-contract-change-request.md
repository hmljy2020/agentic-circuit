# ACIR v0.3 P3 最小共享 Contract Patch 请求

## 1. 请求范围

本文把 `acir-v03-capability-gap-audit.md` 中的 B1、B2、B3 收窄为 P3
`source → compute → observe` 原生 round-trip 所需的最小共享 patch。它是授权和
审阅说明，不代表已经修改 ACIR dialect。

请求允许前端以**独立 contract commits** 修改以下 B 类内容：

```text
B1-P3: #ac.queue_contract、!ac.queue<T,C>、!ac.var<T>
B2-P3: 三个 primitive 的 Graph 合法性和 Queue linear-use verifier
B3-P3: ac.source、ac.compute、ac.observe 与 canonical ac.var op family
```

以下内容不在本 patch：

```text
ac.queue transport op；route/fork/merge；array/field/policy；
pool/table/reorder/issue/engine；ACIR→ACSim；gfsim；CodeGen。
```

## 2. 当前无法表达的前端语义

当前 ACPy 已能确定性生成如下 semantic graph：

```text
Queue<Input> = source()
Queue<Output> = compute(Queue<Input>) {
  Var<Input> -> Var<Output>
}
observe(Queue<Output>)
```

当前 ACIR v0.1 只有无 SSA result 的 owned-state `ac.queue` symbol，且没有
`!ac.queue`、`!ac.var`、上述三个 primitive 或 pure Var region。因此不能用现有
endpoint/instance/process op 做语义等价 lowering，也不能输出可由 `acir-opt`
注册解析的 P3 artifact。

最小 ACPy 复现为：

```python
@ac.system
def minimal(cfg: ac.const[Config]) -> None:
    source = ac.source(Input)
    result = ac.compute(source, transform)
    ac.observe(result)
```

对应 fixture：
`tests/python_frontend/fixtures/acpy_v03/minimal/system.py`。

## 3. 目标 ACIR 结构

下面固定 P3 所依赖的端口和 region 形状。具体 assembly punctuation 可在实现时按
MLIR parser/printer 约束机械调整，但 operand/result/region/type 不能改变。

```mlir
!qin = !ac.queue<
  !ac.struct<@types::@Input>,
  #ac.queue_contract<depth = 1, latency = 1, rate = 1,
                     domain = @core, ordering = fifo>
>

!qout = !ac.queue<
  !ac.struct<@types::@Output>,
  #ac.queue_contract<depth = 1, latency = 1, rate = 1,
                     domain = @core, ordering = fifo>
>

ac.module @minimal() parameters {} graph {
  %source = ac.source {boundary = "input"} : !qin
  %result = ac.compute %source : !qin -> !qout {
  ^bb0(%record: !ac.var<!ac.struct<@types::@Input>>):
    %value = ac.var.get %record ["value"]
      : !ac.var<!ac.struct<@types::@Input>> -> !ac.var<i16>
    %one = ac.var.constant 1 : !ac.var<i16>
    %sum = ac.var.binary add %value, %one
      : !ac.var<i16>, !ac.var<i16> -> !ac.var<i16>
    %output = ac.var.struct ["value"](%sum)
      : (!ac.var<i16>) -> !ac.var<!ac.struct<@types::@Output>>
    ac.var.yield %output : !ac.var<!ac.struct<@types::@Output>>
  }
  ac.observe %result {name = "result", fields = []} : !qout
  ac.return
}
```

`!qin`/`!qout` 只是本文的排版别名，不要求进入实际 ACIR。

## 4. Type 与 attribute contract

### `#ac.queue_contract`

字段固定为：

| 字段 | 类型 | P3 verifier |
| --- | --- | --- |
| `depth` | positive i64 | `>= 1` |
| `latency` | positive i64 | `>= 1` |
| `rate` | positive i64 | `>= 1` |
| `domain` | FlatSymbolRef | 非空；P3 不要求已有 time-domain symbol |
| `ordering` | closed enum | P3 只接受 `fifo` |

### `!ac.queue<T, C>`

- `T` 是 immutable payload；不能是 Queue 或 Var type；
- `C` 必须是完整 `#ac.queue_contract`；
- Queue 是 topology SSA value，不是 runtime pointer；
- 它不替换或 reinterpret v0.1 owned-state `ac.queue` op。

### `!ac.var<T>`

- 只允许存在于 `ac.compute` region 和 canonical `ac.var.*` op；
- 不能作为 topology primitive 的 Queue operand/result；
- 不具有 occupancy、latency、backpressure 或 runtime identity。

## 5. Primitive port contract

| Op | Operands | Results | Region | 状态/背压 |
| --- | --- | --- | --- | --- |
| `ac.source` | 无 | 一个 `Queue<T>` | 无 | boundary producer；结果 edge 可背压 |
| `ac.compute` | 一个 `Queue<T>` | 一个 `Queue<U>` | `Var<T> -> Var<U>` | 无持久状态；严格原子 1:1 |
| `ac.observe` | 一个 `Queue<T>` | 无 | 无 | non-consuming、non-backpressuring |

共同 verifier：

1. Queue value 恰有一个 SSA producer；module block argument 只在未来 scope/module
   边界中作为合法外部 producer，P3 root 不使用；
2. 每条 Queue 最多一个 consuming use；`ac.observe` 不计入；
3. `ac.compute` operand/result payload 必须分别等于 region 输入/输出 Var payload；
4. compute region 单 block、一个 terminator、不得包含 Queue/state/runtime effects；
5. source/compute/observe 只允许作为 `ac.module` Graph 的直接 child；
6. P3 不实现 cycle verifier；反馈 cycle 的 latency proof 在 P5 B2 完整 patch 中加入。

## 6. Canonical Var op family

P3 注册冻结文档中的完整名字闭集：

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

P3 正例首先覆盖 `constant/struct/get/binary/yield`。其余 op 也必须能
parse/print，并至少验证：全部动态值为 `!ac.var`、结果类型显式、operand/result
arity 合法。详细 field path/type、array extent、cast legality 会在其首次被前端使用
的阶段加强，不能因此改变 op 名称或 region boundary。

## 7. 预计修改文件

### B 类

```text
include/acir/Dialect/ACIR/ACIRAttributes.td
include/acir/Dialect/ACIR/ACIRTypes.td
include/acir/Dialect/ACIR/ACIRTypes.h
include/acir/Dialect/ACIR/ACIROps.td
lib/Dialect/ACIR/ACIRTypes.cpp
lib/Dialect/ACIR/ACIROps.cpp
test/ACIR/v03-types-valid.mlir
test/ACIR/v03-types-invalid.mlir
test/ACIR/v03-minimal-valid.mlir
test/ACIR/v03-minimal-invalid.mlir
```

如果 typed AttrDef 需要单独生成头文件，则最小增加：

```text
include/acir/Dialect/ACIR/ACIRAttributes.h
```

### D 类最小例外

当前 CMake 只从 `ACIRAttributes.td` 生成 enum。为注册 typed QueueContractAttr，
需要在以下文件增加 attrdef declaration/definition tablegen，除此之外不改配置：

```text
include/acir/Dialect/ACIR/CMakeLists.txt
```

该 D 类改动只生成方言源码，不改变 LLVM 路径、preset、依赖版本或合作者构建
profile。

### A 类后续

共享 contract 通过后，前端另一个 commit 修改：

```text
src/agentic_circuit/_lower_acir_v03.py（新增）
tests/python_frontend/test_lower_acir_v03.py（新增）
tests/python_frontend/fixtures/acpy_v03/minimal/system.ac.mlir（新增）
```

## 8. 验证证据要求

Contract commits 必须独立通过：

```text
cmake --build build/dev-llvm22 --target acir-opt
llvm-lit build/dev-llvm22/test/ACIR -v
acir-opt test/ACIR/v03-minimal-valid.mlir -o /dev/null
not acir-opt test/ACIR/v03-minimal-invalid.mlir -o /dev/null
```

前端 emitter commit 必须通过：

```text
PYTHONPATH=src <python3.11> -m unittest discover -s tests/python_frontend -v
acir-opt tests/python_frontend/fixtures/acpy_v03/minimal/system.ac.mlir -o /dev/null
```

并检查不同 workspace root、Python hash seed 和重复编译得到 byte-identical ACIR。

## 9. Downstream impact

- ACIR→ACSim 暂时不需要接受这些 op，P3 gate 只要求 ACIR parser/verifier；
- 下游 capability inventory 应把三个 primitive 和 Var op 标记为未实现，而不是让
  ACIR parser 拒绝它们；
- 不修改 ACSim、conversion、gfsim、Provider 或 CodeGen；
- v0.1 owned-state `ac.queue` op 继续保留，P4 再单独解决它与 v0.3 transport
  `ac.queue` op 的同名 contract hard break。

## 10. 授权句式

以下任一句明确回复即可允许实施：

```text
同意按 acir-v03-p3-contract-change-request.md 实施 B1-P3/B2-P3/B3-P3，
并允许必要的 ACIRAttributes tablegen 最小 CMake 改动。
```

或：

```text
共享 contract 由合作者实现；前端停在 semantic artifact，等待其提交。
```
