# ACIR atomic Packet execution ledger

Baseline: `7bb2c6a0d180c16abd510aba3d42fdf988c530ec`

Scope: implement fixed-layout, atomic `ac.packet` values from hand-written ACIR
through freeze, ACSim, C++ code generation, Queue/process execution, and a
versioned byte-oriented host ABI.  ACPy, NoC packet payloads, packetization,
multi-flit routing, VCs, and credits are out of scope.

Resource policy: every native build uses `ulimit -v 1900000`, `--parallel 1`,
and lit/CTest uses `-j1`.  Test failures are reported honestly; assertions are
never weakened to manufacture a pass.

Statuses are limited to `TODO`, `IN_PROGRESS`, `DONE`, and `BLOCKED`; at most
one row is `IN_PROGRESS`.  A `DONE` row records its real acceptance command,
result, and commit.

| ID | Status | Work item | Acceptance evidence | Commit |
|---:|:---:|---|---|---|
| 0 | IN_PROGRESS | Ledger and clean baseline | `git status --short --branch`: clean `main...chao/main` at `7bb2c6a` | pending |
| 1 | TODO | Real failing ACIR Packet executable test | pending | pending |
| 2 | TODO | Canonical Packet/record layout and metadata | pending | pending |
| 3 | TODO | Packet descriptor propagation to ACSim/ModelPlan | pending | pending |
| 4 | TODO | Unique generated C++ Packet values and traits | pending | pending |
| 5 | TODO | Record/serialize/process/Queue code generation | pending | pending |
| 6 | TODO | Generic byte Host ingress/egress ABI | pending | pending |
| 7 | TODO | Packet executable and negative/runtime tests | pending | pending |
| 8 | TODO | Serial related regression, documentation, push | pending | pending |

## Fixed semantics

- A Packet is one immutable, atomic Queue entry regardless of serialized byte
  width.  Multi-flit behavior is not inferred from Packet size.
- Supported fields are fixed-width signless integers, `f32`/`f64`, fixed ACIR
  vectors, and non-recursive nested structs.
- Layout uses declaration order and natural alignment.  DLTI layout must match
  the derived size, alignment, endianness, and Packet serialization width.
- Equal-sized Packet schemas remain distinct runtime and C++ types.
- Existing scalar Queue and `i32` host ABI behavior remains compatible.

## Target acceptance commands

```sh
ulimit -v 1900000; cmake --build --preset dev-llvm22 --parallel 1
ulimit -v 1900000; ctest --test-dir build/dev-llvm22 -j1 --output-on-failure
ulimit -v 1900000; build/dev-llvm22/bin/llvm-lit -j1 test/ACIR test/Conversion test/CodeGen
git diff --check
```
