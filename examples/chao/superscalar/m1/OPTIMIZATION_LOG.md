# M1 ACIR 优化记录

本文件记录结构化 ACIR 优化的语义决策、真实验收和性能数据。所有数据必须由
`./run.sh` 在 `ulimit -v 1900000`、单线程条件下生成；不能用弱化断言换取通过。

## O0：展开模型基线

- 基准提交：`30d59f6`。
- ACIR 3321 行，ACSim 4455 行，generated C++ 28627 行。
- 最近完整基线约 46 秒 C++ 生成/编译、5.5k ticks/s。
- 语义：16 条指令、64 条 trace、29 ticks，两次运行字节一致。
- 主要重复：943 `arith.cmpi`、856 `arith.select`、522 `arith.andi`、
  129 `ac.record.with`、55 次 StateArray read/write。

## O1：纯 SSA canonicalize/CSE

- 在 topology freeze 前增加 `canonicalize,cse`，保留原始、optimized 与 frozen
  三份产物。
- 只读实验将 ACIR 从 3321 行降至 2683 行，`arith.cmpi` 从 943 降至 560；证明
  CSE 是有效的第一步，但不能替代结构化循环和动态索引。
- Compiler Driver 同样先优化、再 freeze 并记录 fingerprint，避免命令行和库入口语义分叉。

## O2：StateArray 读端口扇出与循环端口

- 读端口定义改为“每 epoch 绑定一个地址”：同一端口、同一地址可重复观察；同一端口、
  不同地址仍失败。这对应真实硬件读口输出可以扇出。
- verifier 接受 bounded `scf.for` 归纳变量经 `arith.index_cast` 形成的端口编号。
- 新增真实 runtime 测试覆盖同址复用和异址冲突。
- 结构化微测试发现并确认旧缺陷：静态 `scf.for` 会在 process expansion 中展开，且原先
  forwarding 记录未绑定到消费者，导致循环体 proposal 被 ACSim 静默丢弃。forwarding
  绑定修复后 proposal 不再丢失，但 ACSim 仍静态展开；后续必须继续实现 compact loop
  lowering，不能把“可编译”误报为“结构化后端已完成”。

## O3：记录构造融合

- M1 的 next-state 会重写记录的全部字段，因此直接发出一个 `ac.record.create`，不再生成
  2～7 个串联的 `ac.record.with`。
- generated helper 先零初始化一个 packet，再用 `packetFieldSet` 原地填充各字段；兼容的
  `packetFieldWith` API 保留，用于确实只修改一个字段的场景。
- 这不是新增专用 primitive，也没有改变 packet layout、端序或 committed-state 语义。

## 每次完整运行应记录

| 版本 | ACIR 行 | optimized 行 | ACSim 行 | C++ 行 | cxxgen/s | RSS/KB | ticks/s | trace |
|---|---:|---:|---:|---:|---:|---:|---:|---|
| O0 | 3321 | - | 4455 | 28627 | ~46 | ~580000 | ~5500 | PASS |
| O1～O3 | 3222 | 2516 | 3424 | 24406 | 35.52 | 522868 | 6009 | PASS |

本次 O1～O3 的确定性语义结果仍为 16 条指令、64 条 trace、29 ticks；两次语义输出
逐字节一致。原始模型中 `arith.cmpi/select/andi` 分别为 943/856/522，optimized 中为
569/721/495。`record.with` 已从 M1 生成模型中消除，40 个完整记录用
`record.create` 一次构造；生成 helper 通过原地 field set 避免每个字段复制整个 packet。

## 尚未完成，不能误报

- `scf.for` 尚未在 ACSim/C++ 中保留为紧凑循环；静态循环仍由 process planner 展开。
- M1 的窗口 oldest-selection、indexed-select 和稀疏 StateArray commit 尚无结构化归约/
  动态更新 primitive，因此 Python 生成的源 ACIR 仍然偏大。
- 尚未定义独立的 RTL-lowerable profile；现有改动只改善验证、仿真 lowering 和生成代码。
- `record.update` 尚未成为 Core op；本轮先用完整 `record.create` 消除了 M1 最昂贵的
  `record.with` 链，避免在尚无清晰后端契约时仓促扩张 dialect。

## S10（进行中）：StateArray 稀疏 runtime bookkeeping

- 写冲突由遍历 proposal 列表改为 entry→proposal-slot 的 O(1) 查询。
- 只清理本 epoch 实际触碰的读写端口，并为 proposal/端口索引预留容量；Xfer 不再扫描
  全部端口。
- 同一 StateArray 在一个 epoch 内缓存 commit-participant 注册，仍保留所有 bounds、端口和
  冲突检查。
- 新增原子失败回归：同 entry 写冲突后，较早的 proposal 也不能部分提交；新增 1024-entry
  稀疏访问跨 epoch 端口复用测试。
- 真实验收：5/5 `GfsimStateArrayTest` 通过；旧展开 M1 保持 16/64/29，10,000 tick
  两次测得约 6,083/6,076 ticks/s；本节标记完成。完整全仓回归仍留到阶段收口。

## S4～S6：bounded compact loop lowering

- `ProcessStateExpansion` 不再按静态 trip count 创建 iteration-qualified action；每个
  `scf.for` 只保留 initialize/condition/body/increment。
- ACIR→ACSim 把循环变成同一 PC 内的 CFG 回边，不生成 suspend 或额外 tick。ACSim process
  携带精确 `(pc, source block, target block, trip count)` backedge descriptor；未声明回边仍被
  verifier 拒绝。
- loop induction 和 `iter_args` 都使用 old/next 两组 SSA 身份，latch 在回边上显式映射，
  避免块级 liveness 把入口值误认为块内已定义。
- runtime-object 依赖分析只追踪 owner/ref 类型；标量/packet 不可能产生 runtime owner，因而
  不再把合法的 loop-carried scalar phi 误报为 ownership dependency cycle。
- 定向测试中 4-trip StateArray 循环只生成一次 `.read` 和一次 `.proposeWrite` call site；
  generated C++ 为同 tick局部 CFG，随后又从 `for (;;) + switch` 改成 block-local direct
  `goto`，避免每条 CFG 边重复 dispatch。另一个测试覆盖 `scf.for iter_args` sum
  reduction，并真实编译 generated C++。
- 当前限制：`scf.if` 带 results 尚未进入 compact structured builder；循环内 pure
  `func.call` 已在后续 S6 收口中完成。

## S0 重新测量基线（compact M1 迁移前）

旧展开 M1 在新 compiler/runtime 上仍为 ACIR 3222、optimized 2516、ACSim 3424、generated
C++ 24406 行；lower 3.02 s，cxxgen 35.86 s / 522420 KB，约 6076～6083 ticks/s。语义保持
16 instructions、64 traces、29 ticks且确定。该数据是后续 M1 结构化迁移的比较基线。

## O1～O3 当时的真实验收

- `./examples/chao/superscalar/m1/run.sh`：PASS；包括公开 parser、优化、freeze、
  ACIR→ACSim、C++ 生成/编译/链接、语义、确定性、benchmark、runtime 和定向 lit。
- `lit -j1 -sv build/dev-llvm22/test`：122/122 PASS。
- `GfsimTests`：207/207 PASS。
- `CompilerTests`：7/7 PASS；其中新增用例确认 standard Driver 在 freeze skeleton 前消除
  重复纯 SSA。
- 所有构建使用 `ulimit -v 1900000` 和单线程。

## S2～S9：结构化循环与稀疏 M1 提交

- 新增 4/16/64/256 trip count 的真实 lowering/C++ 编译测试。四种规模在生成 C++ 中各只有
  一个 StateArray `.read` call site；静态 trip count 作为 ACSim bounded-backedge descriptor
  保留，不复制循环体。
- 修正多个 `scf.if` 与 loop 共存时把 DAG 汇合边误判为 loop backedge 的问题：现在只以
  显式 `ForIncrement` action 标识回边，再忽略这些回边做拓扑排序。
- fairness 改成“全部单份 action/CFG + 重复迭代”的保守上界，不再低估 M1 单 tick 路径。
- `canonicalize` 可删除常量 false 的 `ac.state_write`，并复用同 block、同 array/index/port/type
  的精确重复 committed read；不同 SSA 地址或端口不合并，保留运行时冲突和越界检查。
- producer rename table 不再每 tick 扫描 16 项：4 个源查询使用固定端口，两个 completion
  与两个 dispatch 形成最多四个 commit candidate；completion→lane0→lane1 的最终值先合并，
  再用 first-effective 去重，保证同 entry 最多一个 proposal。
- completion ring 从 9 项全写改为 cursor/issue0/issue1 三候选合并；window、ROB、FU、CUBE
  pipeline 都只在最终字段变化时 enable write，CUBE differential oracle 仍逐周期通过。

最终完整 M1 为 16 instructions、64 traces、29 ticks、确定性 PASS；StateArray committed
writes 实测 250，其中 producer 为 32。旧模型每 tick 无条件写 55 项，按相同 29 ticks推导为
1595，下降 84.3%。
1595 是由旧 ACIR 的 constant-true write 和 tick 数推导，并非旧 runtime 统计文件的实测值。

| 指标 | compact 迁移前 | 当前 | 变化 |
|---|---:|---:|---:|
| raw ACIR 行 | 3222 | 3127 | -2.9% |
| optimized ACIR 行 | 2516 | 2386 | -5.2% |
| ACSim 行 | 3424 | 3538 | +3.3% |
| generated C++ 行 | 24406 | 23748 | -2.7% |
| cxxgen | 35.86 s | 28.15 s | -21.5% |
| 空载仿真 | 6076～6083 ticks/s | 7052～7468 ticks/s | +16%～23% |
| committed writes | 1595（推导） | 250（实测） | -84.3% |

编译时间、仿真速度和提交数门槛已达到，但 ACIR/C++ 行数下降 20% 的规模门槛未达到。
guarded-change 和候选 merge 仍由 Python 静态复制；下一步要把 window oldest、first-free 和
候选 merge 表达为 `iter_args` 归约。

## 当前全量回归状态

- 本轮新增/相关测试 4/4 PASS；M1 `run.sh` 全链路 PASS，StateArray runtime 5/5、定向 lit
  6/6。
- 全量 lit 为 117/125 PASS。8 个失败共同报错 `activation edges must exactly equal computed
  static dependencies`，分布在 flow、typed-graph 与既有 ACSim fixtures；这些区域正被工作区
  中的并行改动修改。本轮没有弱化 verifier，S11 不能标为完成。
- 所有构建继续使用 `ulimit -v 1900000`、`-j1`。

## S6、S9～S11 收口：结构归约、pure call 与 CFG codegen

- M1 的 lane0/lane1 oldest-ready、前两个 free slot、window 更新和 ROB 更新改成 bounded
  `scf.for iter_args`。归约结果直接携带 winner 的字段，不再在循环后生成 N 路 select tree；
  ROB head/head+1 使用两个明确的动态读端口。
- compact continuation 现在把 induction、region iter_arg 和 loop result 映射到显式 synthetic
  value，因此 loop reduction 可以直接控制后续 `scf.if`。新增回归要求该分支真实 lower 并
  编译 generated C++。
- process 中的纯 `func.call` 按完整调用栈选择 expansion occurrence；return/argument forwarding
  会回填已创建的 loop latch operand。测试使用两层私有函数调用，覆盖此前会产生未物化
  call-result CFG 参数并导致崩溃的顺序。
- 多 block C++ 不再为每个活跃 SSA 值生成 `std::optional`/`reference_wrapper`。值使用有类型
  的零初始化 local，owner/reference 使用指针，边只做直接赋值；合法 CFG 保证到达块的参数
  已由前驱赋值。这样仍保留一份显式 CFG，同时让 C++ 优化器消除大量 optional 搬运。
- 评估过新增 `record.equal` 和把 CFG 重建成原生 C++ `for`。当前 ACIR/C++ 规模门槛和仿真
  性能门槛已经全部超过，因此没有为单个模型增加新 primitive，也没有引入第二套 loop
  codegen；原生循环重建仍是可独立探索的后续优化。

最终真实验收仍为 16 instructions、64 traces、29 ticks、250 次 StateArray commit（producer
32），两次语义输出一致。最新 release 数据如下：

| 指标 | compact 迁移前 | 最终结构化版本 | 变化 |
|---|---:|---:|---:|
| raw ACIR 行 | 3222 | 1189 | -63.1% |
| optimized ACIR 行 | 2516 | 1013 | -59.7% |
| ACSim 行 | 3424 | 1188 | -65.3% |
| generated C++ 行 | 24406 | 16443 | -32.6% |
| cxxgen | 35.86 s | 8.66 s | -75.9% |
| 空载仿真 | 6076～6083 ticks/s | 26547～26616 ticks/s | +336%～338% |
| cxxgen peak RSS | 522420 KB | 298436 KB | -42.9% |

`compact-loop-iter-args`、4/16/64/256 scale、native StateArray loop、canonicalization 四组
定向 lit 均通过；typed-local CFG CodeGen 单测通过；M1 `run.sh` 全链路通过。resultful
`scf.if` 仍需真正的 merge block/phi lowering，不能对含副作用分支偷换成 eager select。
全量 Gfsim 为 208/208、Compiler Driver 为 7/7；全量 lit 复测仍为 117/125，失败集合与本轮
开始前完全相同，均属于并行 activation/Flow 修改区域。
