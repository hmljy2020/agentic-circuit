# ACPy → ACIR 前端实施计划

## 1. 文档用途

本文是 ACPy → frozen ACIR 前端工程的可跟进实施计划。它记录阶段、任务、依赖、
完成条件和接口阻塞，并允许在开发过程中调整顺序和范围。

相关冻结文档：

- `acpy-v03-confirmed-semantics.md`：ACPy 和 DavinciOO 拓扑语义；
- `acir-v03-davincioo-primitive-contract.md`：第一版 ACIR primitive 闭集；
- `acpy-acir-frontend-change-boundary.md`：前端文件修改边界；
- `davincioo.py`：最终目标 ACPy 样例。

本文不重新定义上述 contract。发现冲突时，必须先记录为 contract issue，不能通过
修改本计划静默改变已冻结语义。

## 2. 状态约定

| 状态 | 含义 |
| --- | --- |
| `待开始` | 尚未开始，可以继续拆分或调整 |
| `进行中` | 当前正在实施；同一时间原则上只有一个主阶段处于此状态 |
| `阻塞` | 缺少已确认 contract、权限或外部实现，无法继续完成 |
| `完成` | 该阶段所有完成条件均已有验证证据 |
| `暂缓` | 当前 profile 不需要，明确留待后续 |

任务只有在测试、artifact 或审阅记录能够证明完成条件时才能标记为 `完成`。

## 3. 总体路线

```text
P0 基线
  -> P1 ACIR 能力缺口审计
  -> P2 ACPy v0.3 语义中间层
  -> P3 最小 source-compute-observe 纵向链路
  -> P4 静态拓扑与多端口
  -> P5 deferred 与反馈 Queue
  -> P6 reorder/pool/table 状态积木
  -> P7 issue recheck/engine
  -> P8 完整 DavinciOO 前端 gate
  -> P9 ac.jit 与 specialization cache 接口
  -> P10 稳定化与对接交付
```

每个阶段都遵循同一个小循环：

```text
最小 ACPy 用例
  -> 期望语义图
  -> 期望 ACIR
  -> contract 支持检查
  -> 前端实现
  -> ACIR parser/verifier
  -> determinism/golden
```

## 4. 阶段总表

| 阶段 | 目标 | 主要产物 | 依赖 | 文件类别 | 状态 |
| --- | --- | --- | --- | --- | --- |
| P0 | 固定当前构建和测试基线 | baseline 记录 | 无 | A/D 只读 | `完成` |
| P1 | 审计当前 ACIR 对 v0.3 contract 的支持 | capability-gap matrix | P0 | B 只读 | `完成` |
| P2 | 建立与 ACIR 文本解耦的语义中间层 | typed semantic graph | P1 contract 结论 | A | `完成` |
| P3 | 贯通最小无状态程序 | source→compute→observe ACIR | P2；相关 B contract | A；必要时 B 对齐 | `完成` |
| P4 | 支持静态拓扑、多端口和线性 Queue | route/fork/merge/scope | P3；相关 B contract | A；必要时 B 对齐 | `完成` |
| P5 | 支持 forward reference 和反馈图 | deferred/cyclic Queue | P4；graph-region contract | A；必要时 B 对齐 | `完成` |
| P6 | 支持通用状态积木 | reorder/pool/table | P5；相关 B contract | A；必要时 B 对齐 | `待开始` |
| P7 | 支持分布式发射和 recheck | issue/engine/recheck | P6；相关 B contract | A；必要时 B 对齐 | `待开始` |
| P8 | 完整编译 DavinciOO 样例 | frozen ACIR artifact | P7 | A；B 仅修复已批准缺口 | `待开始` |
| P9 | 提供 const-only JIT 外壳 | specialization/cache identity | P8 | A；配置变更需 D 对齐 | `待开始` |
| P10 | 稳定化并交付后端 | contract inventory 和 handoff | P8/P9 | A/B 文档；C 只读 | `待开始` |

## 5. P0：建立基线

### 任务

- [x] `P0.1` 检查并记录 `git status --short`，区分已有修改和本任务修改。
- [x] `P0.2` 确认 LLVM、CMake preset、Python 环境和构建目录。
- [x] `P0.3` 记录当前 frontend 单元测试命令及结果。
- [x] `P0.4` 记录当前 `acir-opt` parser/verifier smoke 命令及结果。
- [x] `P0.5` 记录当前完整构建中与 ACPy→ACIR 无关的已知失败。
- [x] `P0.6` 确认本计划后续默认不修改 C/D 类文件。

### 完成条件

- 构建和测试命令可以重复执行；
- 已有失败和新引入失败能够区分；
- 没有覆盖当前 worktree 中的用户/合作者修改；
- 形成一份带日期的 baseline 结果记录。

## 6. P1：ACIR 能力缺口审计

### 任务

- [x] `P1.1` 审计 `!ac.var<T>`。
- [x] `P1.2` 审计 `!ac.queue<T, QueueContract>` 及 depth/latency/rate/domain。
- [x] `P1.3` 审计 struct、array、enum payload 类型。
- [x] `P1.4` 审计 field descriptor 和 policy attribute。
- [x] `P1.5` 审计 graph-region cyclic SSA 支持。
- [x] `P1.6` 审计 named variadic operand/result segments。
- [x] `P1.7` 逐项审计 13 个 frozen primitives。
- [x] `P1.8` 审计 canonical Var region op family。
- [x] `P1.9` 为每个缺口写最小目标 ACIR 和预期 verifier 行为。
- [x] `P1.10` 把缺口分类为“已有可复用 / 需要修改 / 需要新增 / 暂时阻塞”。

### Primitive 审计表

| Primitive | Type/ODS | Port groups | Verifier | Parser round-trip | Contract change |
| --- | --- | --- | --- | --- | --- |
| `source` | 缺失 | 缺失 | 缺失 | 不支持 | 新增 B3 |
| `sink` | 缺失 | 缺失 | 缺失 | 不支持 | 后续新增 |
| `observe` | 缺失 | 缺失 | 缺失 | 不支持 | 新增 B3 |
| `compute` | 缺失 | 缺失 | 缺失 | 不支持 | 新增 B3 |
| `queue` | 同名但语义冲突 | 缺失 | 不兼容 | 仅 v0.1 | 替换 B2/B4 |
| `route` | 缺失 | 缺失 | 缺失 | 不支持 | 新增 B4 |
| `fork` | 缺失 | 缺失 | 缺失 | 不支持 | 新增 B4 |
| `merge` | 缺失 | 缺失 | 缺失 | 不支持 | 新增 B4 |
| `pool` | 缺失 | 缺失 | 缺失 | 不支持 | 新增 B5 |
| `table` | 缺失 | 缺失 | 缺失 | 不支持 | 新增 B5 |
| `reorder` | 缺失 | 缺失 | 缺失 | 不支持 | 新增 B5 |
| `issue` | 缺失 | 缺失 | 缺失 | 不支持 | 新增 B5 |
| `engine` | 缺失 | 缺失 | 缺失 | 不支持 | 新增 B5 |

### 完成条件

- 每个 primitive 和基础类型都有明确审计结论；
- 每个 B 类缺口都有独立 contract diff 描述；
- 没有在本阶段直接修改 B/C 类实现；
- 已确认 P3 最小链路所需的 ACIR contract 是否可用。

## 7. P2：ACPy v0.3 语义中间层

### 任务

- [x] `P2.1` 定义 `Program`、`Scope` 和 hierarchy identity。
- [x] `P2.2` 定义 `BlockInstance` 和 named `PortGroup`。
- [x] `P2.3` 定义 `QueueValue`、producer/use 和 source location。
- [x] `P2.4` 定义 `QueueConstraint` 与 unresolved/frozen 状态。
- [x] `P2.5` 定义 payload type、struct、array 和 enum 表达。
- [x] `P2.6` 定义 typed `FieldDescriptor` 与 policy。
- [x] `P2.7` 定义 `VarRegion` 和 canonical Var operations。
- [x] `P2.8` 定义 `DeferredEdge`，但暂不完成 cyclic lowering。
- [x] `P2.9` 建立 BlockSpec 驱动的 primitive call binding 接口。
- [x] `P2.10` 建立 deterministic semantic snapshot/golden 格式。
- [x] `P2.11` 以显式 v0.3 schema/epoch 隔离 epoch 0.1 `AcpyDocument`，不提供静默兼容 shim。

### 完成条件

- AST/elaboration 不直接拼接 ACIR 文本；
- 语义图能表达多组、多输入和多结果 primitive；
- 所有节点和值保留稳定 identity 和 source span；
- 相同输入生成 byte-identical semantic snapshot；
- 旧 epoch artifact 被确定性拒绝或由明确入口隔离。

## 8. P3：最小无状态纵向链路

### 目标用例

```python
@ac.system
def minimal(cfg: ac.const[Config]) -> None:
    source = ac.source(Input)
    result = ac.compute(source, transform)
    ac.observe(result)
```

### 任务

- [x] `P3.1` 支持 `@ac.config`、`@ac.struct`、`@ac.system` capture。
- [x] `P3.2` 支持 closed `ac.const` binding。
- [x] `P3.3` 支持 qualified `ac.source/ac.compute/ac.observe` 调用。
- [x] `P3.4` 支持最小 Queue payload/type propagation。
- [x] `P3.5` 捕获 pure compute helper/lambda。
- [x] `P3.6` lower compute body 为 canonical Var region。
- [x] `P3.7` 发射 source、compute、observe frozen ACIR。
- [x] `P3.8` 增加合法与非法 ACPy fixtures。
- [x] `P3.9` 增加 semantic、ACIR golden 和 native round-trip 测试。
- [x] `P3.10` 增加 repeated-root determinism 测试。

### 完成条件

- 最小 ACPy 能经过完整前端 pipeline；
- 输出 ACIR 被当前 epoch 的 `acir-opt` parser/verifier 接受；
- compute 非纯操作和非法 capture 被前端拒绝；
- 不依赖 ACSim 或 gfsim 修改。

## 9. P4：静态拓扑与多端口

### 目标覆盖

```text
scope
static if/for
static tuple/list
queue
route
fork
merge
```

### 任务

- [x] `P4.1` 实现 `with ac.scope(...)` lexical I/O 推导。
- [x] `P4.2` 实现 const `if` 裁剪和 const `for/range` 静态展开。
- [x] `P4.3` 实现静态 tuple/list canonicalization。
- [x] `P4.4` 实现裸 Queue def-use contract constraints。
- [x] `P4.5` 实现显式 `ac.queue` transport block。
- [x] `P4.6` 实现 `ac.route` 多结果 lowering。
- [x] `P4.7` 实现 `ac.fork` strict atomic fanout lowering。
- [x] `P4.8` 实现 `ac.merge` variadic input 和 policy lowering。
- [x] `P4.9` 实现 Queue single-producer/single-consuming-use verifier。
- [x] `P4.10` 增加 port arity、rate、payload shape 不混用的负测试。

### 完成条件

- route/fork/merge 的 variadic segments 能 native round-trip；
- 多 consuming use 未经过 fork 时确定性失败；
- 多 producer 未经过 merge 时确定性失败；
- scope hierarchy 和静态展开结果 deterministic；
- emitter 不保存重复的 input/output count attribute。

## 10. P5：Deferred 与反馈 Queue

### 任务

- [x] `P5.1` 实现 `ac.queue.deferred(T)` elaboration object。
- [x] `P5.2` 实现 `.output` 的 forward-use constraint。
- [x] `P5.3` 实现 `.bind(queue)` exactly-once 检查。
- [x] `P5.4` 统一 deferred 两端 payload/Queue contract constraints。
- [x] `P5.5` 确保 deferred object 和 bind 不进入 frozen ACIR。
- [x] `P5.6` 发射 graph-region cyclic SSA。
- [x] `P5.7` 检查每个 cycle 至少包含一个 `latency >= 1` edge。
- [x] `P5.8` 增加 unbound、double-bind、type-conflict 和组合环负测试。

### 完成条件

- 最小反馈图可以 native parse/verify；
- deferred 在 frozen artifact 中完全消失；
- 非法循环具有精确 source diagnostic；
- 不用 hidden callback 或运行时 Queue pointer 闭合反馈。

## 11. P6：Reorder、Pool 与 Table

### 任务

- [ ] `P6.1` 实现 `ac.reorder` enqueue/completed 和 admitted/retired groups。
- [ ] `P6.2` 实现 reorder identity/allocate_identity descriptor 检查。
- [ ] `P6.3` 实现 `ac.pool` acquire/release/acquired groups。
- [ ] `P6.4` 实现 pool collection/element descriptor 类型检查。
- [ ] `P6.5` 实现 `ac.table` access/accessed groups。
- [ ] `P6.6` 实现 table update/updated groups。
- [ ] `P6.7` 实现 table query/response groups。
- [ ] `P6.8` 实现 read/write/exchange/query/copy action descriptor 闭集。
- [ ] `P6.9` 实现 SMAP 的 read-before-write transaction 表达。
- [ ] `P6.10` 实现 ReadyTable access/update/query 表达。
- [ ] `P6.11` 增加 action、arity、payload relation 负测试。

### 完成条件

- Rename 可以 lower 为 `pool → table(SMAP)`；
- ReadyTable 可以 lower 为一个通用 `table`；
- 不生成 `ac.rename` 或 `ac.ready_table`；
- table 三组 transaction 的 ACIR signature 与共享 BlockSpec 一致；
- native parser/verifier 和 determinism tests 通过。

## 12. P7：Issue Recheck 与 Engine

### 任务

- [ ] `P7.1` 实现 singleton-lane `ac.issue` enqueue/wakeup/recheck_response groups。
- [ ] `P7.2` 实现 issued/recheck_request result groups。
- [ ] `P7.3` 检查 dependency 和 wakeup field descriptors。
- [ ] `P7.4` 检查 request/response/correlation payload relation。
- [ ] `P7.5` 表达 resident-first admission transaction。
- [ ] `P7.6` 表达 `pending_recheck` 与 `monotonic_or` policy contract。
- [ ] `P7.7` 实现 `ac.engine` latency_by/inflight/initiation_interval/kind。
- [ ] `P7.8` 实现每 lane issue/engine 的 const loop 静态展开。
- [ ] `P7.9` 闭合 issue request → table query → issue response feedback。
- [ ] `P7.10` 闭合 engine completion → table update → fork wakeup feedback。
- [ ] `P7.11` 增加 missed-wakeup 结构 regression fixture。

### 完成条件

- 单 lane recheck 图先通过 native parser/verifier；
- 四 lane 由 Python 静态展开为四个独立 issue/engine ops；
- 每 lane entries 独立，不错误合并为集中式 window；
- frozen ACIR 不包含 callback、动态 Queue pointer 或 Python object；
- recheck 端口与 `acir-v03-davincioo-primitive-contract.md` 一致。

## 13. P8：完整 DavinciOO 前端 Gate

### 任务

- [ ] `P8.1` 编译 `docs/issues/davincioo.py`。
- [ ] `P8.2` 生成并保存 canonical ACPy semantic artifact。
- [ ] `P8.3` 生成并保存 frozen ACIR golden。
- [ ] `P8.4` 运行 ACIR parser/verifier round-trip。
- [ ] `P8.5` 验证完整 Queue single-producer/consuming-use。
- [ ] `P8.6` 验证所有 feedback cycles 的 timing boundary。
- [ ] `P8.7` 验证不同 root/hash seed/process 的 byte determinism。
- [ ] `P8.8` 生成 source map、manifest 和 primitive inventory。
- [ ] `P8.9` 输出 downstream capability/implementation gap，不修改 C 类文件。

### 前端 Gate

```text
DavinciOO ACPy
  -> verified ACPy semantic graph
  -> frozen ACIR
  -> ACIR parser/verifier round-trip
  -> deterministic artifact
```

### 完成条件

- 上述 gate 全部通过；
- ACIR → ACSim 尚未实现的 primitive 被单独列出，不算作前端失败；
- 没有为了通过后端而改变已冻结前端语义；
- `davincioo.py` 中所有 `PROVISIONAL` 拼写已处理为 frozen API 或有明确剩余项。

## 14. P9：`ac.jit` 与 Specialization

### 任务

- [ ] `P9.1` 先提供无缓存、确定性的内部 `compile_system` 接口。
- [ ] `P9.2` 定义 closed const canonicalization。
- [ ] `P9.3` 定义 specialization identity 输入。
- [ ] `P9.4` 对 canonical ACPy/ACIR 计算稳定 hash。
- [ ] `P9.5` 实现 cache hit/miss 和原子 artifact publication。
- [ ] `P9.6` 把 `ac.jit(system, **consts)` 实现为上述流程的薄包装。
- [ ] `P9.7` 拒绝 runtime Queue 参数、open callable 和 mutable const object。
- [ ] `P9.8` 增加跨路径、进程和 Python hash seed 的缓存复用测试。

### 完成条件

- frozen ACIR 后不再依赖 Python；
- 相同 const specialization 命中相同 artifact；
- 不同结构参数不会错误命中缓存；
- 第一阶段不依赖 LLVM ORC、Python bytecode JIT 或 native callback。

## 15. P10：稳定化与后端对接

### 任务

- [ ] `P10.1` 输出最终 primitive/type/attribute inventory。
- [ ] `P10.2` 输出每个 op 的正例、反例和 round-trip evidence。
- [ ] `P10.3` 输出 ACIR → ACSim 所需 Provider/Conversion 清单。
- [ ] `P10.4` 确认 frontend-only、contract 和 downstream commits 可独立审阅。
- [ ] `P10.5` 运行完整 frontend、ACIR 和 determinism gates。
- [ ] `P10.6` 更新 handshake 文档中的实际可用 contract evidence。
- [ ] `P10.7` 清理仅属于设计阶段且不再使用的 provisional fixture；不得删除仍有
  对接价值的 contract 记录。

### 完成条件

- 合作者不需要阅读前端实现即可获得完整 frozen ACIR contract；
- 每个 downstream 缺口都有最小 ACIR fixture；
- 前端修改没有混入 C 类实现；
- 交付报告符合 `acpy-acir-frontend-change-boundary.md` 的格式。

## 16. 每个阶段的统一验证清单

每个阶段按适用性提供：

- [ ] 合法 ACPy fixture；
- [ ] 每个可成功 lower 的正向 `.py` fixture 旁保存同名 `.ac.mlir` 供人工检阅；
- [ ] 非法 ACPy fixture和稳定 diagnostic code；
- [ ] canonical semantic golden；
- [ ] canonical ACIR golden；
- [ ] `acir-opt` parser/verifier round-trip；
- [ ] repeated compile determinism；
- [ ] unrelated-root/hash-seed determinism；
- [ ] `Frontend-only changes` 清单；
- [ ] `Contract changes` 清单，或者明确 `none`；
- [ ] `Downstream impact` 清单，或者明确 `none`；
- [ ] `Unchanged/out of scope` 清单。

## 17. 阻塞与调整规则

### ACIR contract 阻塞

如果阶段需要修改 B 类文件：

1. 保留已经完成的 A 类分析和最小复现；
2. 写出修改前/后的 ACIR 端口结构；
3. 记录 payload、atomicity、timing 和 downstream impact；
4. 请求共享 contract 授权；
5. 未获授权前不修改 B/C 类文件，也不输出私有临时 dialect。

### 计划调整

允许调整任务拆分或阶段先后，但必须满足：

- 不跳过 P1 contract 审计；
- 不在 P3 纵向链路通过前大规模实现全部 Python 语法；
- 不在单 lane recheck 通过前展开完整多 lane DavinciOO；
- 不用计划调整改变 frozen semantics；
- 调整必须写入下方变更记录。

## 18. 当前关注点

```text
当前阶段：P4 静态拓扑与多端口
已完成：P0 基线；P1 能力审计；P2 语义中间层；P3 source→compute→observe 纵向链路
当前验证：78/78 Python 前端测试；v0.3 emitter 逐字 golden、两次 native round-trip、跨 root determinism
当前 contract 状态：B1/B2/B3 P3 patch 已落地；P4 开始前审计 queue/route/fork/merge/scope 的 B4 缺口
当前 downstream blocker：CodeGen/Phase5 E2E 的生成 C++ 链接找不到 `-lLLVM`；不影响前端阶段实施
```

## 19. 变更记录

| 日期 | 变更 | 原因 | 影响阶段 |
| --- | --- | --- | --- |
| 2026-08-25 | 创建初始实施计划 | 建立可跟进、可调整的 ACPy→ACIR 工作路线 | P0–P10 |
| 2026-08-25 | P0 完成，P1 开始 | 前端 56/56 通过；记录完整 CTest 的既有 CodeGen/Phase5 环境失败 | P0–P1 |
| 2026-08-25 | P1 完成，P2 开始 | 确认 graph/record 基础可复用，Queue SSA/types/13 primitives 均需 v0.3 contract | P1–P3 |
| 2026-08-25 | P2 完成，P3 开始 | typed semantic graph、BlockSpec、Var/deferred 与 canonical snapshot 已实现；前端 68/68 通过 | P2–P3 |
| 2026-08-26 | P3 完成，P4 开始 | v0.3 source/compute/observe、Var region、自动 emitter 与 5 类前端 lowering 测试均通过 native gate | P3–P4 |

后续每次改变阶段顺序、完成条件或 contract dependency 时，都在此增加一行；普通
任务状态变化只更新阶段表和 checkbox，不需要增加变更记录。
