# `router2x2` ACIR example: a 2×2 input-queued crossbar with arbitration

`model.mlir` is a self-contained ACIR model of a 2×2 crossbar: two input FIFOs,
one arbitration process, two output FIFOs, and two self-checking sinks. It is
the first example in this repo to execute **multi-entry native queues**
(`entries > 1`) end-to-end — linked and run against the real `gfsim` runtime —
and the first to show a polling **arbiter that routes on the runtime
destination field** rather than a static wiring.

## What the model does

Two workload producers continuously re-propose an eight-flit burst each
(destination alternating by sequence parity). A single
arbiter control process polls both inputs every tick, drains the
higher-priority `@in0` queue first, and routes each flit to the output named by
its two-bit destination field. Two sinks drain the outputs and self-check every
flit's destination and payload.

### Flit layout (`i32` bit-fields)

| bits | field | meaning |
| --- | --- | --- |
| `[1:0]` | `dst` | destination output (0 or 1) |
| `[3:2]` | `src` | source producer (0 or 1) |
| `[7:4]` | `seq` | injection sequence number (0..7) |
| `[31:8]` | `payload` | `seq*97 + src` (corruption + flit-identity check) |

Producer 0 (src = 0) injects `dst = seq & 1`, `payload = seq*97`. Producer 1
(src = 1) injects `dst = (seq + 1) & 1`, `payload = seq*97 + 1`. The arbiter
extracts `dst` with `arith.andi` and routes; the sinks extract all four fields
with `arith.shrui`/`andi` and re-check `payload == seq*97 + src`, so any
corruption or misroute fails the run at the in-model assert before the runner's
statistic checks are reached.

## Semantics worth knowing

The two behaviors below are consequences of the toolchain, not bugs in this
model — both are documented here because they are not obvious from the source.

### 1. `scf.for` drops proposal ops — producers are manually unrolled

The process-state expansion unrolls static `scf.for` bodies but drops
side-effecting proposal ops (`ac.try_send`) from the unrolled body: the loop
bounds and induction constants survive, the `try_send` and its operand
arithmetic do not. This was verified at `acir-opt` level for the unused-result
form, the used-result form, and the blocking `try_send`/`await_queue` idiom —
in every case the acsim IR contained only the constants and the wake invoke,
never `impl_queue_try_send`. The workaround used here (and in
`examples/chao/noc/acir/router_tree`) is to **manually unroll**: eight explicit
`ac.try_send`s, which do emit eight `impl_queue_try_send` invokes in the acsim
IR (visible in `model.acsim.mlir`). This is a real toolchain gap worth fixing
upstream; the traffic matrix here is static anyway, so the constants are folded
to literals and nothing is lost.

### 2. Every process re-fires every tick — traffic is continuous, not one-shot

A process body must terminate in `ac.yield_sim` (verified in
`lib/Dialect/ACIR/ACIROps.cpp`), and `yield_sim` resumes the process at its
entry on the next tick. So a producer cannot "burst once then stop": it
re-proposes its burst every tick, and a proposal that finds the queue full is
soft-rejected and retried on the next tick. `SimQueue::proposePush` soft-rejects
a full queue, which is exactly the backpressure mechanism this example
demonstrates.

### The resulting steady state: strict-priority starvation

Under continuous saturation the fixed-priority (`in0 > in1`) arbiter keeps
`@in0` drained at one flit per tick while `@in1` — lower priority and never
drained — fills to its 16-entry capacity and stays there:

- `@in1` completes **zero** flits; its occupancy is pinned at 16/16 for the
  whole steady-state window. This is the deterministic, observable signature of
  strict priority: a fair (round-robin) arbiter would not starve it.
- `@in0` saturates at 15/16 (94%) and drains one flit per tick into `@out0` /
  `@out1` by destination parity — a live backpressure + forwarding signal.

## Checked run

The checked run uses a 24-tick cap. Expected statistics:

| object | accepted | completed | occupancy | occupancy peak |
| --- | --- | --- | --- | --- |
| `in0` | 38 | 23 | 15 | 15 |
| `in1` | 16 | 0 | 16 | 16 |
| `out0` | 15 | 14 | 1 | 1 |
| `out1` | 8 | 8 | 0 | 1 |

Expected classification is `Incomplete` at `finalEpoch {24, 0}`, with 187
published observations. The runner additionally enforces the conservation
invariant `accepted == completed + occupancy` on every queue (38 = 23 + 15,
16 = 0 + 16, 15 = 14 + 1, 8 = 8 + 0), `occupancy_peak <= entries` (16), and
`in0.completed == out0.accepted + out1.accepted` (every drained `in0` flit lands
on exactly one output). The values above were captured from a deterministic
run: execute `bin/router2x2-demo` twice and the output is byte-identical.

## Build and run

```sh
examples/chao/noc/acir/router2x2/build-run.sh
```

The script rebuilds `examples/chao/noc/acir/router2x2/build` and keeps the frozen ACIR,
lowered ACSim, generated C++, object files, and `bin/router2x2-demo` there
after the run. `model.frozen.mlir` and `model.acsim.mlir` at the example root
remain checked-in snapshots for inspection (the `acsim.process` blocks for
`@producer0`/`@producer1` show the eight `impl_queue_try_send` invokes).
`build-run.sh` also guards the generated object set: model + 1 module + 5
processes = 7 objects.

## Compilation stages

The stages used to produce them were:

```sh
build/dev-llvm22/bin/acir-opt --verify-each=false \
  --pass-pipeline='builtin.module(ac-freeze-topology)' \
  examples/chao/noc/acir/router2x2/model.mlir \
  -o examples/chao/noc/acir/router2x2/build/model.frozen.mlir

build/dev-llvm22/bin/acir-opt --ac-lower-to-acsim \
  --ac-binding-profile=fast --ac-binding-target=x86_64-linux-gnu \
  examples/chao/noc/acir/router2x2/build/model.frozen.mlir \
  -o examples/chao/noc/acir/router2x2/build/model.acsim.mlir

build/dev-llvm22/bin/acir-cxxgen \
  examples/chao/noc/acir/router2x2/build/model.acsim.mlir \
  --stop-after=link --output-root=examples/chao/noc/acir/router2x2/build/generated \
  --project-name=chao-router2x2 --project-identity=project.chao.router2x2 \
  --system-name=router2x2_demo --system-identity=system.router2x2-demo \
  --profile=fast --compiler=/usr/bin/c++ --standard-library=libstdc++ \
  --abi-mode=default --object-format=elf --contract-flag=-std=c++20 \
  --include-root=/home/lc/AC/agentic-circuit/include \
  --link-input=/home/lc/AC/agentic-circuit/build/dev-llvm22/lib/gfsim/libgfsim.a \
  --link-input=/home/lc/AC/agentic-circuit/build/dev-llvm22/lib/Bindings/libACIRBindings.a \
  --linker-flag=-L/usr/lib/llvm-22/lib --linker-flag=-lLLVM
```

## Runner

`runner.cpp` links against the generated model objects, applies `maxTicks=24`,
prints every statistic, and returns nonzero if any expected value does not
match. The structural checks are conservation and capacity (no loss, no
duplication, no overfill); the exact steady-state values are pinned from the
deterministic run, same discipline as `examples/chao/fu_latency`. The six
`ac.assert` sites in `model.mlir` (arbiter `recv == peek` ×2, sink destination
×2, sink payload ×2) make the data path self-checking: any corruption,
misroute, or field inconsistency fails the run with `Failed` before the
statistic assertions are reached.
