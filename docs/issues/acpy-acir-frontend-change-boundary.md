# ACPy → ACIR 前端工程修改边界

## 1. 目的

本文规定 ACPy → ACIR 前端开发期间允许修改的项目范围，以及前端与
ACIR → ACSim 合作者共同维护 ACIR contract 时的变更流程。

目标是：

- 前端可以独立推进 Python capture、语义分析和 lowering；
- ACIR primitive/type 的变化必须显式对齐；
- 前端不通过顺手修改后端实现来掩盖接口问题；
- 前后端可以通过清晰的文件 ownership 和 contract diff 最终对接；
- Agent 在工作前能够直接判断可修改范围，避免无意扩大任务边界。

本文约束后续 ACPy → ACIR 前端工作。用户在具体任务中给出的显式授权优先于
本文；没有显式授权时必须遵循本文。

## 2. A 类：前端可自主修改

### 2.1 默认路径

```text
src/agentic_circuit/
  _source.py
  _validate.py
  _static_eval.py
  _frontend.py
  _normalize.py
  _acpy.py
  _lower_acir.py
  以及为 ACPy 前端新增的 semantic/type/inference 模块

tests/python_frontend/
schemas/acpy.schema.json
docs/issues/ 中的 ACPy/ACIR 前端设计与记录文档
```

### 2.2 自主修改内容

前端可以在上述范围内实现：

- Python source/AST capture；
- supported-Python validation；
- `ac.const` 静态求值和 elaboration；
- ACPy 语义图；
- Queue SSA def-use；
- scope I/O 推导；
- static collection canonicalization 和展开；
- deferred Queue bind；
- payload、端口形状和 Queue contract 推导；
- primitive call binding；
- pure compute lambda → canonical Var region；
- ACPy → frozen ACIR emission；
- 前端 diagnostics、source map、determinism 和 golden tests。

### 2.3 A 类限制

即使文件位于 A 类路径，前端也不能：

- 私自创造未进入 frozen catalog 的 ACIR primitive；
- 用 Python-only hidden state 代替正式 ACIR operand/result；
- 因后端尚不支持某个 contract 而静默改变前端语义；
- 在 emitter 中输出与共享 ACIR contract 不一致的临时方言。

## 3. B 类：共享 ACIR contract

### 3.1 默认路径

```text
include/acir/Dialect/ACIR/
lib/Dialect/ACIR/
test/ACIR/

contracts/
schemas/stdlib/
schemas/component.schema.json
schemas/capabilities.schema.json
```

### 3.2 共享内容

这些文件共同决定：

- `!ac.queue`、`!ac.var` 和 payload 类型；
- ACIR primitive ODS 声明；
- named operand/result segments；
- variadic segment 规则；
- field descriptor 和 policy attribute；
- parser/printer；
- ACIR verifier；
- BlockSpec schema；
- official opcode catalog；
- primitive 的 state/effect、timing、backpressure 和 transaction contract。

### 3.3 修改规则

B 类文件不属于前端单方实现细节。修改前必须先形成可审阅的 contract change，
至少说明：

```text
1. 当前 ACIR 无法表达的前端语义；
2. 最小 ACPy 或 ACIR 复现；
3. 目标 primitive 名称；
4. 修改前后的 operand/result groups；
5. payload type relation；
6. static parameter/attribute；
7. atomicity、state 和 backpressure 语义；
8. 对 ACIR → ACSim 的可见影响。
```

形成上述说明后，只能采用以下一种方式继续：

1. 由共享 contract 的约定负责人修改；
2. 用户或合作者明确授权前端修改；
3. 前端提交独立、可单独审阅的 contract patch，不与普通前端实现混合。

如果没有明确授权，Agent 必须停止 B 类写入，保留前端范围内可以完成的工作，
并向用户汇报缺失 contract 和所需变更。

### 3.4 典型 B 类变更

以下属于共享 contract 变更：

```text
ac.issue 新增 recheck_response operand group；
ac.issue 新增 recheck_request result group；
ac.table 新增 query operand 和 response result groups；
!ac.queue 增加或修改 depth/latency/rate/domain contract；
primitive 从单结果变为多结果；
修改 field descriptor 的类型或编码；
修改 fork、merge、table、issue 的 atomic transaction 语义。
```

不能只修改 `_lower_acir.py` 输出上述新结构，而不更新和对齐共享 ACIR contract。

## 4. C 类：前端默认不修改

### 4.1 默认路径

```text
include/acir/Dialect/ACSim/
lib/Dialect/ACSim/

include/acir/Conversion/
lib/Conversion/ACIRToACSim/

include/gfsim/
lib/gfsim/

include/acir/CodeGen/
lib/CodeGen/

test/ACSim/
test/Conversion/
test/CodeGen/
unittests/gfsim/
```

### 4.2 允许行为

前端工作可以对 C 类内容执行：

- 只读检查；
- 运行已有测试；
- 对照端口和语义；
- 提供最小失败 ACIR；
- 报告 downstream compatibility impact。

### 4.3 禁止行为

没有用户或合作者的显式授权，前端和 Agent 不得：

- 修改 ACIR → ACSim conversion；
- 修改 ACSim dialect 来接受错误或临时 ACIR；
- 修改 gfsim/provider 行为来迁就前端输出；
- 修改 codegen 以绕过缺失的 ACIR contract；
- 放宽下游 verifier 或删除失败测试。

遇到这些需求时，应把问题报告为共享 contract 或 downstream implementation
gap，而不是跨边界直接修复。

## 5. D 类：工程与仓库配置默认保持不动

### 5.1 默认路径

```text
CMakeLists.txt
CMakePresets.json
cmake/
toolchains/
.github/
Python package/build/install 配置
```

### 5.2 例外规则

只有在以下情形才能考虑修改：

- 新增前端源文件必须注册到构建系统；
- 新增测试无法被现有 test discovery 发现；
- 安装包缺少新增的前端模块或 schema；
- 构建/测试无法在已约定环境中运行，且没有前端范围内的替代方案。

修改前必须说明：

```text
需要修改的确切文件；
不修改时的具体失败；
计划进行的最小修改；
是否会影响合作者的构建或工具链。
```

工程配置修改必须与功能修改在汇报中分开列出。不得顺带格式化、升级依赖或
清理无关配置。

当前已有的 `CMakePresets.json` LLVM 路径变更不属于 ACPy 前端功能，后续前端
工作不得覆盖、回退或混入该变更。

## 6. 变更规模判断

### 6.1 Frontend-only change

示例：

```text
支持 ac.const for-loop 静态展开；
增加 deferred bind 检查；
改善 Python source diagnostic；
把 with_fields lower 为已有 ac.var.update；
按已有 BlockSpec 发射 ac.route。
```

这类工作可以在 A 类范围内自主完成。

### 6.2 Contract change

示例：

```text
attribute `capacity` 政名为 `entries`；
ac.table 增加新的 named port group；
ac.issue 从一个 result 变为两个 results；
修改 Queue payload relation；
增加新的 official primitive。
```

这类工作必须按 B 类流程处理。

### 6.3 Downstream change

示例：

```text
ACSim Issue Provider 消费新的 recheck_response Queue；
gfsim Table Provider 实现 query linearization；
ACIRToACSim conversion 映射新的 result segment。
```

这类工作由后端负责，或等待用户显式授权联合修改。

## 7. 每次任务的 Agent 操作规则

Agent 开始 ACPy → ACIR 工作时必须：

1. 先检查 `git status --short`，识别并保护用户和合作者已有修改；
2. 列出任务预计触及的文件，并按 A/B/C/D 分类；
3. A 类文件可以在任务范围内直接修改；
4. B 类文件必须先给出 contract diff 并获得授权；
5. C 类文件默认只读；
6. D 类文件只有满足例外条件并汇报后才能修改；
7. 不回退、不覆盖、不格式化与当前任务无关的已有修改；
8. 完成后再次检查 diff，按类别汇报实际修改文件；
9. 如果测试失败来自未实现的 B/C 类内容，应明确报告边界，不通过扩大修改范围
   静默修复。

## 8. 对接输出格式

前端提交或阶段汇报至少使用以下结构：

```text
Frontend-only changes:
  - 文件和行为

Contract changes:
  - primitive/type
  - 修改前端口
  - 修改后端口
  - 语义原因

Downstream impact:
  - ACIR → ACSim 需要消费或实现的内容

Unchanged/out of scope:
  - 明确未修改的后端和工程文件

Validation:
  - 前端测试
  - ACIR parser/verifier
  - determinism/golden evidence
```

如果没有 contract change 或 downstream impact，也必须明确写 `none`，避免合作者
需要从普通代码 diff 中猜测接口是否变化。

## 9. Ownership 总结

```text
ACPy → ACIR 前端
  ├── 自主：Python capture / ACPy semantic graph / inference / lowering
  ├── 联合：ACIR types / primitive ODS / BlockSpec / ACIR verifier
  └── 默认不改：ACIR → ACSim / gfsim / provider / codegen

ACIR → ACSim 后端
  ├── 消费：frozen ACIR contract
  ├── 联合：ACIR types / primitive ODS / BlockSpec / ACIR verifier
  └── 自主：conversion / ACSim / provider / runtime / codegen
```

文件边界不能代替语义 contract。任何改变 frozen ACIR 可观察结构的修改，即使
发生在 A 类文件中，仍然必须按 B 类 contract change 汇报和对齐。
