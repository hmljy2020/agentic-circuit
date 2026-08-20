# `crossbar_vc` RTL 亲和 ACIR 草案说明

对应文件：[`model.rtl-ideal.mlir`](model.rtl-ideal.mlir)。

这是一份设计草案，目前不能被 ACIR parser 接受。它保留现有
`ac.queue`、`ac.resource`、`ac.peek`、`ac.space` 和 `arith`，只建议增加
两个 Core primitive：`ac.arbitrate` 和 `ac.try_transfer`。

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
%f0 = ac.try_transfer @in0_A to @out0_A grant %g0 : i32
```

其语义为：

```text
fire = grant && source.readable && destination.writable
```

当 `fire=true` 时，在同一个 Xfer barrier 原子完成：

```text
从 source 弹出 committed snapshot 中的旧队头
把同一个值压入 destination
```

当 `fire=false` 时，两个 Queue 都不变化。因此不需要依靠
`try_send → try_recv → assert` 来提供功能正确性。

## RTL 映射

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

## 还需要实现的 primitive

### `ac.arbitrate`

建议的最小接口是：

```mlir
%g0, ... = ac.arbitrate greedy_fixed_priority
  candidates [
    %request0 uses [@resource0, @resource1],
    ...
  ] : (i1, ...)
```

需要实现：

- ODS 定义、parser/printer 和 canonical form；
- request/result 数量与类型检查；
- resource 必须可解析且 capacity/issue-width 合法；
- 按 candidate 文本顺序执行确定性 greedy matching；
- 保证每个 resource 的 grant 数不超过其容量；
- 固定优先级版本无持久状态；
- ACIR→ACSim、进程状态规划和 C++ 代码生成；
- RTL lowering 到 priority/matching 组合逻辑。

第一版只需要 `greedy_fixed_priority`。Round-robin 应在以后增加显式指针
状态，并且只在对应 transfer 实际 fire 后更新。

### `ac.try_transfer`

建议接口是：

```mlir
%fire = ac.try_transfer @source to @destination grant %grant : T
```

需要实现：

- source/destination Queue 解析；
- payload、协议和时域一致性检查；
- grant 必须为 `i1`；
- RTL profile 下，竞争路径的 grant 必须直接来自可验证的 arbiter；
- 对 source pop 和 destination push 创建一个不可拆分的事务组；
- 任一侧不能接受时，两侧都不提交；
- destination 得到的值必须等于旧 source head；
- commit 后正确更新 Queue 统计和 readable/writable 唤醒；
- ACSim/gfsim 的 grouped proposal 与原子 Xfer 支持；
- RTL lowering 到 FIFO data、pop enable 和 push enable。

## 不需要新增的 primitive

当前方案不需要：

- `!ac.grant_set<N>`：普通 `i1` result 加 SSA provenance 足够；
- `ac.resource.arbitrate`：使用通用 `ac.arbitrate` 即可；
- `ac.transfer_select`：ACPy/stdlib 可以把它展开为若干静态
  `ac.try_transfer`；
- `ac.route`：现有位运算和比较已经适合 RTL；
- `ac.writable`：现有 `ac.space > 0` 已能表达。

除两个 primitive 外，还需要补充 module/process 级冲突验证、ACSim
原子事务组、代码生成支持和未来的 RTL-lowerable profile；这些属于分析、
lowering 和 runtime 工程，不需要继续扩张 ACIR primitive 集合。
