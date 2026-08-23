# M0 简短报告

日期：2026-08-22

状态：`DONE`

## 基线

- HEAD：`eed11404f8d1146dac154681bf5704315071d207`
- 工具：`build/dev-llvm22/bin/acir-opt`、`acir-cxxgen`、gfsim、ACIRBindings
- 配置：`fast`、`x86_64-linux-gnu`、单线程 lit、`ulimit -v 1900000`
- 工作区：执行前已有其他 Agent 的未提交改动；M0 只修改 `examples/chao/superscalar/`
- 验收命令：`./examples/chao/superscalar/m0/run.sh`

## 功能结果

| case | 结果 | 关键结论 |
|---|:---:|---|
| Queue | PASS | 深度 1；tick 0/2/4 push，tick 1/3/5 pop；值保持且最终为空 |
| Event/FU | PASS | 固定延迟和同-ready-tick插入顺序正确；下游背压不丢事件 |
| Arbitrate/transfer | PASS | 双请求只选 source0；旧 head `10` 原子进入满后不再变化的 destination |
| 确定性 | PASS | 三个 semantic 输出各连续运行两次，字节完全一致 |
| targeted lit | PASS | 19/19，覆盖相关 ACIR、Conversion 和 CodeGen 正负测试 |

Queue 在 6 ticks 内 `accepted=3`、`completed=3`、peak occupancy=1。观察到的 push/pop
交错说明 process 读取 committed snapshot，本 tick 的 push 到下一 tick 才可被 consumer 读取。

Event/FU 在 12 ticks 内：dispatch `accepted=12`、`completed=10`、occupancy=2；completion
`accepted=10`、`completed=5`、occupancy=5；深度 1 result Queue `accepted=5`、
`completed=4`。事件只在 ready tick 可见，retire 因结果 Queue 满而 suspend 时不会重复 pop。
额外的 ordered queue 每 tick 依次插入 `70`、`71`，两者 ready tick 相同；payload assertion
证明消费顺序始终为 `70→71`。其统计为 `accepted=24`、`completed=20`、occupancy=4。

Arbitrate/transfer 在 tick 0 填充两个 source，tick 1 固定优先级选择 source0。结束时 source0
`accepted=2/completed=1/occupancy=1`，source1 `1/0/1`，destination `1/0/1`；所有 Queue
满足 `accepted = completed + occupancy`。输出满后没有 source pop，observer 的值断言证明
destination 保存的是 observed source0 old head。

## 规模与性能

| case | ACIR B | Frozen B | ACSim B | 生成 C++ B/行 | objects | ticks/s |
|---|---:|---:|---:|---:|---:|---:|
| Queue | 1,813 | 6,179 | 15,122 | 28,995 / 712 | 5 | 41,059.9 |
| Event/FU | 3,950 | 14,225 | 28,554 | 47,724 / 1,110 | 8 | 17,007.9 |
| Arbitrate/transfer | 3,417 | 10,089 | 16,767 | 29,652 / 777 | 7 | 32,474.4 |

10,000-tick benchmark 是饱和/背压微基线，不代表最终 NPU 吞吐。lowering 为 0.04–0.06 秒；
C++ 生成和内部编译为 7.70–10.42 秒，runner 链接为 2.52–2.73 秒，是当前最明显的固定成本。
实测 peak RSS 为 309,040 KB，低于本阶段资源限制。

## ACIR 审视

- Queue、event queue、fixed-priority arbitration 和 `try_transfer` 已足以开始 token 级 M1。
- `ac.try_transfer` 保留了 Queue-to-Queue 原子动作；模型不需要用 assertion 提供原子性。
- fixed-priority `ac.arbitrate` lowering 为布尔 SSA；候选规模扩大后的 IR/C++ 增长需要在 M1 测量。
- `ac.resource` 当前为声明和仲裁冲突元数据，没有通用 acquire/release/complete 执行语义。
- 一个 process 可在同一 epoch 连续完成两次 `try_event`；event queue 没有显式读端口或每周期
  dequeue width。仿真语义明确，但 M1 必须显式限制 completion bandwidth 才能保持 RTL 亲和。
- round-robin lowering 已有仓库测试，但持久 next-state 仍要由模型显式保存，M0 未做动态运行案例。
- 生成/链接固定成本已明显高于 IR pass 成本；M1 应分别记录增量 IR 膨胀与固定工具链开销。

第一次执行 targeted lit 时脚本遗漏 `-j1`，lit 启动 16 workers，18/19 通过，
`CodeGen/native-event-queue.mlir` 因 staging 文件争用失败。脚本修正为 `-j1` 后完整重跑，
19/19 通过。该失败属于 M0 脚本编排错误，原始功能断言没有被修改或削弱。

## 对 M1 的结论

M1 可以开始。先使用 Queue、event queue、显式状态和 fixed-priority arbitration 实现 token
级多执行单元；不要假定 `ac.resource` 会自动占用或释放 FU。遇到 II/capacity 原子更新需求时，
先保存最小失败模型和规模数据，再决定组合、标准组件、canonicalization 或新 primitive。
