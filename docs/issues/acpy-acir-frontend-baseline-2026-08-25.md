# ACPy → ACIR 前端基线（2026-08-25）

## 1. 范围

本文记录实施计划 P0 的初始工作区、工具链、构建和测试状态。它用于区分后续
前端修改引入的回归与当前已经存在的环境/后端失败。

本阶段没有修改源码、ACIR dialect、ACIR → ACSim、gfsim、codegen 或构建配置。

## 2. 工作区

```text
repository: /home/lc/agentic-circuit
branch: main
HEAD: b9cccf2 merge: add DavinciOO gfsim reference model
```

开始 P0 时已有以下非本阶段修改：

```text
M  CMakePresets.json
?? AGENTS.md
?? docs/acpy-acir-handshake.md
?? docs/issues/
```

这些内容均按用户/合作者已有工作保护。本阶段不覆盖或回退
`CMakePresets.json`，也不把未明确属于本阶段的未跟踪文件纳入提交。

仓库根 `AGENTS.md` 的约束为：不得伪造测试通过。本基线保留所有真实失败。

## 3. 持久化工具链

```text
LLVM:       22.1.8
LLVM root:  /home/lc/opt/llvm-22.1.8
CMake:      3.31.10
Python:     3.11.16
Python env: /home/lc/opt/agentic-circuit-toolchain/python-env
Build dir:  /home/lc/agentic-circuit/build/dev-llvm22
```

系统默认 `/usr/bin/python3` 是 Python 3.9.9，不满足项目
`requires-python >= 3.11`，不能用于前端测试。

P0 将仓库 `requirements-dev.lock` 中锁定的开发依赖安装到上述持久化 Python
3.11 环境。该操作只修改 `/home/lc/opt/agentic-circuit-toolchain/python-env`，不
修改系统 Python 或仓库文件。

## 4. 构建基线

命令：

```text
cmake --build build/dev-llvm22 -j2
```

结果：通过。

```text
[1/1] Synchronizing gfsim runtime headers
```

## 5. ACPy 前端测试基线

命令：

```text
PYTHONPATH=src \
  /home/lc/opt/agentic-circuit-toolchain/python-env/bin/python \
  -m unittest discover -s tests/python_frontend -t . -v
```

结果：通过。

```text
Ran 56 tests
OK
```

使用系统 Python 3.9 时会因为 `typing.Never`、`dataclass(slots=True)` 和缺失的
`jsonschema` 失败；这属于错误解释器/环境，不是前端源码回归。

## 6. ACIR parser/verifier smoke

命令：

```text
build/dev-llvm22/bin/acir-opt \
  tests/python_frontend/fixtures/lowering/process.ac.mlir \
  -o /dev/null
```

结果：通过。

`test/ACIR/dialect-smoke.mlir` 不是适合直接整文件运行的 smoke fixture，因为它
包含 lit 驱动下故意拒绝 generic ACIR operation spelling 的负测试段。

## 7. 完整 CTest 基线

命令：

```text
ctest --test-dir build/dev-llvm22 --output-on-failure -j2
```

结果：12/14 个 CTest targets 通过，以下两个 target 失败：

### `CodeGenTests`

62 个内部测试中 58 个通过、4 个失败：

- 3 个 build/cache tests 在测试内编译链接时使用 `-lLLVM`，但当前 LLVM 安装只
  提供 component static archives，没有 `libLLVM.so`/`libLLVM.a` aggregate；
- 1 个 generated-model compile test 落到系统 GCC 10 `libstdc++` headers，导致
  `TimeDomainRuntime` 对 `constexpr std::array` 不满足 literal-type 要求。

### `Phase5E2ETests`

DavinciOO source reproduction 等检查通过；六个 public pipeline build subcases
均在生成 C++ 的链接阶段失败，错误相同：

```text
/usr/bin/ld: cannot find -lLLVM
```

## 8. 对前端计划的影响

```text
P1 ACIR 只读审计：              不阻塞
P2 ACPy semantic graph：         不阻塞
P3–P8 ACPy→ACIR parser gate：    不阻塞
完整 ACIR→ACSim/CodeGen gate：   存在已知环境阻塞
```

后续前端阶段至少维持以下无回归 gate：

```text
cmake build
56 个现有 python_frontend tests
合法 ACIR fixture 的 acir-opt parse/verify
```

完整 CTest 中上述两个已知失败必须继续如实报告；未经 D/C 类授权，不通过修改
构建配置、CodeGen 或后端源码处理它们。
