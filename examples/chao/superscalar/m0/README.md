# M0：ACIR 控制语义与测量基线

M0 是 superscalar NPU 路线的独立基线阶段，不实现 NPU 调度器，也不修改编译器。它用三个
自包含模型固定后续控制核依赖的 Queue、事件时序、仲裁和原子传输语义。

## 模型

| case | 验证内容 | semantic ticks |
|---|---|---:|
| `queue` | 深度 1 FIFO、peek/recv 值一致、背压、容量守恒 | 6 |
| `event_latency` | 固定延迟、同-ready-tick顺序、completion 背压 | 12 |
| `arbitrate_transfer` | 双输入固定优先级、单输出、原子 Queue transfer | 4 |

每个 runner 还有独立的 10,000-tick benchmark 模式。benchmark 数值只用于建立本机基线，
不作为功能断言；semantic 模式包含精确统计和守恒断言，并由脚本连续运行两次做字节级比较。

## 运行

仓库需要已有 `build/dev-llvm22` 工具和库。执行：

```bash
./examples/chao/superscalar/m0/run.sh
```

脚本顺序执行 verifier、freeze、ACIR→ACSim、model plan、C++ 生成、runner 链接、两次语义
运行、benchmark 和相关 targeted lit 测试。它设置 1.9 GB 虚拟内存上限，不启动并行构建。

临时产物位于 `m0/build/`：

- `timing.tsv`：各阶段耗时和 peak RSS；
- `sizes.tsv`：各层 IR 和生成 C++ 规模；
- `<case>/semantic-1.txt`：确定性语义输出；
- `<case>/benchmark.txt`：native ticks/s；
- `targeted-lit.txt`：相关仓库测试结果。

阶段结论见 [REPORT.md](REPORT.md)，primitive 编译路径见
[PRIMITIVE_MATRIX.md](PRIMITIVE_MATRIX.md)。
