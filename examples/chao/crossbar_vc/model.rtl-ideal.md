# `crossbar_vc` RTL 亲和 ACIR 草案说明

对应文件：[`model.rtl-ideal.mlir`](model.rtl-ideal.mlir)。

这是一份自包含、可执行的 ACSim/C++ 模型。`ac.arbitrate
greedy_fixed_priority` 与 `ac.try_transfer` 均已打通 ACIR、ACSim、gfsim
和 C++ codegen；模型复用普通版本的 system、producer、sink 与 runner，
只替换 scheduler。

目标是把 Crossbar 的每周期行为明确写成：

```text
观察 Queue 已提交状态
        ↓
计算路由请求
        ↓
执行确定性仲裁
        ↓
原子提交 Queue 到 Queue 的传输
```

## 结构

模型包含两个物理输入和两个物理输出，每个物理端口有 A、B 两个虚拟
通道，因此共有八个逻辑 Queue：

```text
输入：in0_A、in0_B、in1_A、in1_B
输出：out0_A、out0_B、out1_A、out1_B
```

四个现有 `ac.resource` 表示物理带宽约束：

- `@pin0` 由 `in0_A/in0_B` 共享；
- `@pin1` 由 `in1_A/in1_B` 共享；
- `@pout0` 由 `out0_A/out0_B` 共享；
- `@pout1` 由 `out1_A/out1_B` 共享。

这些 resource 不表示额外缓存，只表示每周期最多使用一次的物理 lane。

## 每周期运行逻辑

### 1. Observe

调度 process 首先用 `ac.peek` 读取四个输入 VC 的旧队头和 valid，再用
`ac.space` 读取四个输出 VC 的剩余空间：

```mlir
%h0a, %v0a = ac.peek @in0_A : i32
%space0a = ac.space @out0_A
```

这些读取都来自周期开始时的 committed snapshot，不会修改 Queue。

### 2. Request

Flit 的低两位表示目的输出。草案用普通 `arith` 提取目的地址并生成八个
request：

```text
request = input_valid
          && route(input_head) == destination
          && destination_has_space
```

例如：

```mlir
%a0_o0_valid = arith.andi %v0a, %dst0a_o0 : i1
%req_a0_o0 = arith.andi %a0_o0_valid, %w0a : i1
```

这一阶段只有组合计算，还没有选择赢家。

### 3. Arbitrate

真正的选择发生在 `ac.arbitrate`：

```mlir
%g0, %g1, %g2, %g3, %g4, %g5, %g6, %g7 =
  ac.arbitrate greedy_fixed_priority
    candidates [
      %req_a0_o0 uses [@pin0, @pout0],
      %req_a1_o0 uses [@pin1, @pout0],
      ...
    ]
    : (i1, i1, i1, i1, i1, i1, i1, i1)
```

仲裁器按文本顺序扫描 candidate。只有 request 为真且 candidate 使用的
所有 resource 都未被更早 winner 占用时，才输出对应 grant。

候选顺序是硬件策略的一部分：

1. 所有 A 请求排在 B 请求之前；
2. 同一 class、同一输出下，物理输入 0 排在输入 1 之前。

resource 冲突同时保证：

- 每个物理输入每周期最多发送一个 Flit；
- 每个物理输出每周期最多接收一个 Flit；
- 使用不同输入和不同输出的两条路径可以同时获得 grant。

八个 grant 是普通 `i1`。它们必须直接用于对应的 transfer；定义它们的
arbiter op 和 result 编号为 verifier 提供 grant provenance，不需要额外的
`!ac.grant_set` 类型。

### 4. Commit

每条静态 Crossbar 路径对应一条 `ac.try_transfer`：

```mlir
%f0 = ac.try_transfer @in0_A to @out0_A when %g0 : i32
```

其语义为：

```text
fire = enable && source.readable && destination.writable
```

当 `fire=true` 时，在同一个 Xfer barrier 原子完成：

```text
从 source 弹出 committed snapshot 中的旧队头
把同一个值压入 destination
```

当 `fire=false` 时，两个 Queue 都不变化。因此不需要依靠
`try_send → try_recv → assert` 来提供功能正确性。

## 当前 lowering

ACIR→ACSim 会把固定优先级仲裁器线性展开为普通 `arith` 布尔 SSA；resource
只在编译期作为 capacity-1 冲突 token，不会生成 runtime object、binding、
helper、数组或通用仲裁循环。生成的 C++ 是直接的 `bool` 局部运算。

`ac.try_transfer` 则生成 compiler-known Queue invoke，并在 Xfer 阶段原子
更新 source/destination。可用下面的命令生成 frozen ACIR、ACSim、
ModelPlan、C++、对象文件和可执行文件：

```sh
bash examples/chao/crossbar_vc/run.sh --rtl-ideal
```

所有生成物均写入被忽略的 `build-rtl-ideal/`。

## 未来 RTL 映射

`ac.arbitrate` 可以 lower 成固定优先级选择和资源占用组合逻辑；多条
静态 `ac.try_transfer` 可以合并成数据 mux、FIFO pop enable 和 push
enable。例如物理输出 0 可形成：

```verilog
out0_fire = g0 | g1 | g4 | g5;
out0_data = g0 ? in0_A_head :
            g1 ? in1_A_head :
            g4 ? in0_B_head : in1_B_head;

in0_A_pop = g0 | g2;
in1_A_pop = g1 | g3;
```

Queue 的 pop/push 在时钟边沿一起更新。

## `ac.arbitrate` v1 范围

当前接口是：

```mlir
%g0, ... = ac.arbitrate greedy_fixed_priority
  candidates [
    %request0 uses [@resource0, @resource1],
    ...
  ] : (i1, ...)
```

当前已支持：

- ODS 定义、parser/printer 和 verifier；
- request/result 数量与类型检查；
- resource 必须可解析且 capacity/issue-width 合法；
- 按 candidate 文本顺序执行确定性 greedy matching；
- capacity-1 resource 的互斥 grant provenance；
- 固定优先级版本无持久状态；
- ACIR→ACSim 的线性布尔 SSA 展开和 C++ 代码生成。

尚未支持 capacity>1、公平/round-robin 仲裁、跨 epoch reservation 与 RTL
backend。Round-robin 需要显式指针状态，并且只在对应 transfer 实际 fire
后更新。

### `ac.try_transfer`（已实现）

建议接口是：

```mlir
%fire = ac.try_transfer @source to @destination when %enable : T
```

当前实现包括：

- source/destination Queue 解析；
- payload、协议和时域一致性检查；
- enable 和 fire 均为 `i1`；
- 对 source pop 和 destination push 发布成对 proposal；
- 任一侧不能接受时，两侧都不提交；
- destination 得到的值必须等于旧 source head；
- commit 后正确更新 Queue 统计和 readable/writable 唤醒；
- ACSim compiler-known invoke 与 gfsim 原子 Xfer；
- C++ 生成调用 `source.tryTransferTo(destination, enable)`。

verifier 只接受直接来自同一 arbiter 不同 result 的 enable，并要求相关
candidate 共享 capacity-1 resource。布尔改写、不同 arbiter、同一 grant
驱动多条 transfer，以及与同方向 send/recv 混用都会被拒绝。

## 不需要新增的 primitive

当前方案不需要：

- `!ac.grant_set<N>`：普通 `i1` result 加 SSA provenance 足够；
- `ac.resource.arbitrate`：使用通用 `ac.arbitrate` 即可；
- `ac.transfer_select`：ACPy/stdlib 可以把它展开为若干静态
  `ac.try_transfer`；
- `ac.route`：现有位运算和比较已经适合 RTL；
- `ac.writable`：现有 `ac.space > 0` 已能表达。

这些 primitive 已足够用于 ACSim/C++ 仿真；RTL-lowerable profile 仍是后续
工作。
