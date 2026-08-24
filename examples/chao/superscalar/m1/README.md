# M1：Superscalar 调度核

当前阶段的功能、优化与量化结果汇总见 [`STAGE_SUMMARY.md`](STAGE_SUMMARY.md)。

M1 是 L0 token 级的第一个 NPU 架构原型。它不计算真实数值，但指令格式、寄存器依赖、
调度状态、FU 占用、完成时间和退休顺序都由 ACIR 显式表达并进入生成的 C++ 仿真器。

## 固定配置

- 两路 bundle dispatch、最多两路 issue/completion/retire；
- 8-entry issue window、8-entry ROB、16 个逻辑寄存器，`r0` 永不产生依赖；
- `Scalar/VEC/CUBE/DMA-token` 延迟分别为 `1/2/8/4` cycle；
- 1 个 Scalar、2 个 VEC、1 个 CUBE、1 个 DMA-token 单元；
- oldest-ready 全局选择，producer map 保存 `sequence_id + 1` tag；
- 9-entry completion reservation ring，保证未来任一 tick 最多两个固定延迟完成；
- event queue 表示功能完成，显式 8 级 StateArray 流水线作为 CUBE 时序差分 oracle。

指令 packet 是五个 `i32` 字段：`sequence_id, opcode, rd, rs1, rs2`。opcode 编码为
`0=Scalar, 1=VEC, 2=CUBE, 3=DMA-token`。当前输入是严格递增的双 lane bundle，尚未建模
分支、异常、物理寄存器重命名和值数据。

## 运行逻辑

每个 tick 的 scheduler process 先读取所有 committed StateArray 和 Queue head，然后纯组合地：

1. 消费最多两个到期 completion，清除依赖和 FU inflight；
2. 从 ready window 项中选最老的两条；两条都检查 FU 和未来 completion slot，第二条还避开
   第一条本周期占用的 FU/完成带宽；
3. 检查 ROB/window credit，原子接受一个双 lane bundle 或一个单 lane head；
4. 在旧 ROB snapshot 上最多退休两条；
5. 向 StateArray 提交每个 entry 的唯一 next value，并调度 issue completion event。

StateArray 的读取看到同一 committed snapshot，写入是本 epoch 的 proposal，在 Xfer 边界统一提交。
同周期 completion 不会让已经开始的 issue/retire 组合判断偷看 next state。CUBE event completion
还必须逐周期匹配结构化 8-stage pipeline，否则模型内的 `ac.assert` 会令仿真失败。
reservation ring 的当前 slot 还必须等于 event queue 实际取出的数量，因此任意 workload 都不能
把三条固定延迟 completion 静默挤到同一条双宽完成通路上。

## 验收

```bash
./examples/chao/superscalar/m1/run.sh
```

脚本限制虚拟内存为 1.9 GB、所有构建和 lit 都单线程。它执行公开 ACIR 解析、纯 SSA
canonicalize/CSE、freeze、
ACIR→ACSim、C++ 生成/编译/链接、两次确定性语义运行、10,000 tick benchmark、StateArray
runtime 测试和定向 lit。证据保存在 `m1/build/`。

16 条验收指令覆盖 RAW、同 bundle rename/WAW、独立年轻指令越过被阻塞老指令、双发射、
多 FU 重叠、乱序完成和严格顺序退休。runner 逐条检查 `complete_tick = issue_tick + latency`、
每阶段每 tick 宽度不超过 2、依赖 consumer 晚于 producer completion，以及两次 trace 完全一致。

## 边界

`gen_model.py` 只是静态展开器，不是行为 golden；所有调度判断仍是生成 ACIR 中可见的
arith/record/state/event/queue op。当前窗口和 ROB 展开导致 IR 很大，这正是 M1 要测量和复盘的
问题。下一阶段不应继续复制这种展开，而应评估可索引 record state、批量状态访问、结构化
multi-grant 选择和 lowering 融合。
