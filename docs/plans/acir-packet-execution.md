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
| 0 | DONE | Ledger and clean baseline | `git status --short --branch`: clean `main...chao/main` at `7bb2c6a` | `b710a45` |
| 1 | DONE | Real failing ACIR Packet executable test | Initial focused lit failed because `ac.record.get` was illegal in canonical ACSim; final `--filter=native-packet` passed 3/3 | `f41f5e4` |
| 2 | DONE | Canonical Packet/record layout and metadata | Natural-layout positive test and mismatched size/alignment/serialization-width negative test passed | `f41f5e4` |
| 3 | DONE | Packet descriptor propagation to ACSim/ModelPlan | Focused Conversion test emits typed `acsim.value` and structured helper metadata | `f41f5e4` |
| 4 | DONE | Unique generated C++ Packet values and traits | `PacketTest` static assertion proves equal-size schemas are distinct `AtomicPacket` types | `f41f5e4` |
| 5 | DONE | Record/serialize/process/Queue code generation | Packet CodeGen lit completed freeze, ACSim lowering, C++ compile, link, and executable fingerprint run | `f41f5e4` |
| 6 | DONE | Generic byte Host ingress/egress ABI | ABI v2 generates exact-size `offer_bytes`/`take_bytes`; HostEgress runtime test passed | `f41f5e4` |
| 7 | DONE | Packet executable and negative/runtime tests | `native-packet-queue`, `native-packet-layout-invalid`, and both `PacketTest` cases passed | `f41f5e4` |
| 8 | DONE | Serial related regression, documentation, push | Build passed; lit 116/116; CTest 12/12 in 333.27 s; `git diff --check` passed; pushed with the ledger finalization | `f41f5e4` |

## Final acceptance evidence

```text
ulimit -v 1900000; cmake --build --preset dev-llvm22 --parallel 1
  PASS
ulimit -v 1900000; python3 /usr/lib/llvm-22/bin/lit -j1 build/dev-llvm22/test
  PASS: 116/116
ulimit -v 1900000; ctest --test-dir build/dev-llvm22 -j1 --output-on-failure
  PASS: 12/12 (333.27 s)
git diff --check
  PASS
```

The implemented Packet remains one atomic Queue entry.  Multi-flit transport,
Packetizer/Reassembler components, router VC ownership, and credits remain
explicitly out of scope.

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
