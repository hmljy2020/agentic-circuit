# 从 ACPy 到 ACIR：前端实现教程与阶段记录

## 1. 这项工作的最终目的

用户希望用接近 Python 数据流程序的形式描述硬件拓扑：

```python
source = ac.source(Input)
result = ac.compute(source, transform)
ac.observe(result)
```

这里的 Python 不是仿真脚本。前端必须把它冻结为一种不再依赖 Python object、
callback 或执行顺序的 ACIR 图，之后 ACIR→ACSim、gfsim 或 Verilog 后端才能消费
同一个明确 contract。

整个编译路径分成三层：

```text
ACPy source
  │  AST capture、const elaboration、类型/线性检查
  ▼
ACPy semantic graph
  │  Queue contract freeze、primitive binding、Var region lowering
  ▼
frozen ACIR
  │  native parser/verifier 是前后端握手门
  ▼
ACSim / providers（不属于本前端任务）
```

semantic graph 的意义是把“理解 Python”和“拼写 MLIR”解耦。这样 ACIR 的文本
格式调整不会迫使 AST 分析重写，ACIR 缺少 primitive 时也不会诱使前端偷偷输出
私有方言。

## 2. 为什么先实现 Queue 和 Var 类型

P3 的最小链路有两种完全不同的值：

```text
Queue<T>：跨 block 传输 token 的 topology edge
Var<T>：一个 compute transaction 内部的纯组合值
```

如果两者都只使用普通 SSA `T`，后端和 verifier 将无法区分：

- 哪个值具有容量、延迟、速率和背压；
- 哪个值只能短暂存在于 pure compute region；
- 哪个 def-use 是硬件连接，哪个只是组合表达式；
- feedback cycle 是否经过了真实 timing boundary。

因此 B1-P3 新增：

```mlir
!ac.var<T>

!ac.queue<T,
  #ac.queue_contract<
    depth = D,
    latency = L,
    rate = R,
    domain = @clock_domain,
    ordering = fifo
  >>
```

注意 `!ac.queue` 是 SSA **type**；仓库原有 `ac.queue` 是 v0.1 的 owned-state
symbol **operation**。这一阶段没有把两者当成同一个对象，也没有修改旧 op。

## 3. QueueContract 为什么必须进入类型

裸 Python def-use 已经是一条物理上可物化的 Queue edge，而不是无限容量的零延迟
wire。若 depth/latency 只放在 producer 或 consumer 上，同一条 edge 可能被两端给出
不同解释；如果只放在 manifest，ACIR verifier 又无法独立验证拓扑。

把 contract 放入 Queue type 后：

```text
producer result type == consumer operand type
```

这一条普通 SSA 类型相等规则同时完成 payload 和 transport contract 对接。P3
目前冻结的规则是：

- `depth >= 1`：容量有限且非零；
- `latency >= 1`：裸 edge 是 timing boundary；
- `rate >= 1`：每次调度最多处理的 FIFO prefix；
- domain 必须是非空 symbol；
- 第一版只接受 FIFO ordering；
- Queue/Var 不能嵌套进 Queue payload，Var 也不能再包 Queue/Var。

这些不是 Python 运行时检查，而是 dialect attribute/type 构造时的 native verifier。
因此手写错误 ACIR、其他语言前端产生的错误 ACIR，也会以相同方式被拒绝。

## 4. B1-P3 实际做了什么

实现分为四个机械环节：

1. TableGen 定义 `QueueOrdering`、`QueueContractAttr`、`VarType` 和
   `QueueValueType`；
2. 为 dialect 打开默认 attribute parser/printer，并注册生成的 attribute；
3. 在 C++ invariant verifier 中检查正数约束和非法嵌套；
4. 增加文本、二进制 bytecode、二次 parse/print 与负例测试。

其中 CMake 的变化只让 TableGen 多生成 attribute declarations/definitions，不改变
LLVM 路径、preset 或依赖版本。

## 5. 当前解决程度

截至 B1-P3：

```text
已解决：ACIR 能区分 topology Queue 和 compute-local Var；
已解决：Queue transport contract 有 typed、可 round-trip 的单一表示；
已解决：非法 depth/latency/rate 和 Queue/Var nesting 被 native 拒绝；
未解决：source/compute/observe operation 尚未注册；
未解决：compute Var region 和 Queue consuming-use 尚未验证；
未解决：文件入口仍需要正式接受 contract epoch 0.3。
```

验证证据：

```text
acir-opt / acir-opt-internal 构建成功
v03-types-valid 文本 parse/verify 成功
5 个 v03-types-invalid case 均按预期失败
ACIRTypesTests 通过
```

当前 LLVM 安装不含 `FileCheck`/`split-file`，且 venv 的 `lit` launcher 仍引用旧
`/tmp` shebang；所以本阶段同时直接运行了正例和逐段负例。测试文件保留标准 lit
RUN lines，工具补齐后可以直接纳入完整 lit gate。

## 6. 为什么还需要文件 epoch 0.3

类型和 operation 注册解决的是“某段文本能不能被 dialect parser 识别”，文件
epoch 解决的是“整份 artifact 声明自己遵守哪一套 contract”。两者不能互相代替。

仓库原入口只接受：

```mlir
builtin.module attributes {ac.contract_epoch = "0.1"}
```

如果前端把新的 Queue SSA 语义仍标成 0.1，下游会误以为它遵守旧的
endpoint/owned-state contract；如果标成 0.3，旧入口又会在看到任何 operation
以前直接拒绝。因此 P3 增加一个很小的 epoch gate：入口同时识别 0.1 和 0.3，
已有 0.1 artifact 保持原样，新的前端 artifact 明确写 0.3，其他 epoch 继续失败。

这不是让 0.1 和 0.3 相互 reinterpret：

- 旧 `ac.queue` owned-state op 的意义没有改变；
- 新 `!ac.queue` 仍是独立的 SSA type；
- v0.3 primitive 自己会要求所在文件为 0.3；
- 后端仍可用 capability inventory 明确报告“不支持 v0.3”，而不是误执行。

## 7. 下一步阅读路线

后续章节将在实现时继续加入：

1. 为什么 ACIR 文件需要显式 epoch 0.3；
2. source/compute/observe 的 transaction 和 backpressure contract；
3. Var helper 如何从 Python AST lower 成纯 region；
4. Queue linear-use verifier 为什么把 observe 视为例外；
5. 最小 ACPy 如何生成可 native round-trip 的 ACIR。
