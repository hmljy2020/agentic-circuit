# `adder` ACIR example: a streaming adder with a register pipeline

`model.mlir` is a self-contained ACIR model of a streaming adder that is
correct even when its two operands arrive **one tick apart**. It demonstrates
the ACIR v0.2 idiom for process-local storage: since the executable op
inventory has no register primitive, a **capacity-1 self-loop queue** acts as a
register the owning process both writes and reads.

## The bug this model fixes

The previous three-queue version read both operands destructively:

```mlir
%lhs, %received_a = ac.try_recv @op_a : i32
%rhs, %received_b = ac.try_recv @op_b : i32
%both = arith.andi %received_a, %received_b : i1
scf.if %both { ... }
```

`ac.try_recv` consumes even when the *other* operand is absent, so if `@op_a`
and `@op_b` ever arrive in different ticks, the earlier-arrived operand is
silently dropped and the guard only hides the loss. `model.mlir.xkp` is the
v0.1 sketch this design descends from.

## The register pipeline

Six capacity-1 queues, four processes:

| queue | producer → consumer | role |
| --- | --- | --- |
| `@op_a` | `@source` → `@alu` | operand A input |
| `@op_b_delay` | `@source` → `@delay` | operand B delay line input |
| `@op_b` | `@delay` → `@alu` | operand B (delayed one tick) input |
| `@reg_a` | `@alu` self-loop | **register A** |
| `@reg_b` | `@alu` self-loop | **register B** |
| `@result` | `@alu` → `@sink` | result output |

`@source` injects `2` and `3` every tick (continuous; `yield_sim` re-fires it).
`@delay` moves `@op_b_delay → @op_b` with a **peek-gated move**: it only
transfers when `@op_b` is empty, so a value the ALU has not yet loaded is never
overwritten and the pipe never drops a flit. That is why `@op_b` is skewed one
tick behind `@op_a` — the situation that used to lose an operand.

`@alu` is a two-stage pipeline that runs from entry every tick:

1. **Load** — `@op_a → @reg_a` and `@op_b → @reg_b`, but only into an
   *empty* register (peeked, not consumed). A full register holds an operand
   whose partner has not arrived; overwriting it would drop it.
2. **Compute** — `peek` both registers; only when both are full, `try_recv`
   both (guaranteed to succeed), `add`, and `ac.assert sum == 5` before
   `try_send @result`.

A `try_send` is pending until Xfer, so a value loaded this tick is not visible
to compute until the next tick — the registers have one real tick of latency,
and `@op_a` genuinely sits in `@reg_a` waiting for the delayed `@op_b`. Both
`try_recv`s in the compute stage are performed only after both `peek`s confirm
the pair is complete, so nothing is ever dropped.

## A simpler alternative: peek, don't read

The register pipeline above fixes the destructive load with genuine
process-local storage. It is not the *only* fix, and it is not the shortest
one. Because `ac.peek` is a non-destructive look — it returns the committed
head and a valid flag without consuming, reserving, or registering a commit
participant — the ALU can peek both inputs and only read them once *both* are
valid:

```mlir
ac.process @alu kind "control" {
  %a, %v_a = ac.peek @op_a : i32
  %b, %v_b = ac.peek @op_b : i32
  %both = arith.andi %v_a, %v_b : i1
  scf.if %both {
    %lhs, %ga = ac.try_recv @op_a : i32
    %rhs, %gb = ac.try_recv @op_b : i32
    %sum = arith.addi %lhs, %rhs : i32
    %correct = arith.cmpi eq, %sum, %five : i32
    ac.assert %correct, "adder result must equal 5"
    %sent = ac.try_send @result %sum : i32
  }
  ac.yield_sim
}
```

This is correct under skew for the same reason the registers are: when `@op_a`
arrives before `@op_b`, the peek on `@op_b` returns `false`, no `try_recv` runs,
and the early operand simply stays in `@op_a` — the input queue itself is the
buffer. It needs **no registers and no delay process**: three queues and three
processes (`@source`, `@alu`, `@sink`), object count back to 5. The one
hardware trade-off is narrative: `@op_a` waits in its *input* queue rather than
in an ALU-local register.

Both forms share one honest limitation: the two `try_recv`s are destructive and
happen before the result send, so a `try_send @result` that fails would drop
the consumed pair. In this model `@result` never stays full — `@sink` drains it
every tick and the ALU computes at most once per tick — so neither version
triggers the loss; making the send truly lossless under output backpressure
needs the `try_send` → `await_queue` park idiom from `examples/chao/router2x2`.

The register version is kept here because it is the only one that demonstrates
cross-tick, process-local storage in ACIR v0.2; the peek-both form is the
minimal correctness fix.

## Checked run

12-tick cap, classification `Incomplete` at `finalEpoch {12, 0}`, 126 published
observations. Statistics (pinned from the deterministic run — run the binary
twice and the output is byte-identical):

| object | accepted | completed | occupancy | peak |
| --- | --- | --- | --- | --- |
| `op_a` | 6 | 5 | 1 | 1 |
| `op_b` | 6 | 5 | 1 | 1 |
| `op_b_delay` | 6 | 6 | 0 | 1 |
| `reg_a` | 5 | 5 | 0 | 1 |
| `reg_b` | 5 | 5 | 0 | 1 |
| `result` | 5 | 4 | 1 | 1 |

Five complete add cycles in 12 ticks. The runner additionally enforces, per
queue, conservation (`accepted == completed + occupancy`) and `peak <= 1`, plus
the pipeline chain: `op_a.completed == reg_a.accepted`, `op_b.completed ==
reg_b.accepted`, and `reg_a.completed == reg_b.completed == result.accepted`.
The `sum == 5` correctness is enforced in-model, so any wrong sum fails the run
before the runner's counts are reached.

## Build and run

```sh
examples/chao/adder/run.sh
```

The script rebuilds `examples/chao/adder/build`, keeps the frozen ACIR, lowered
ACSim, generated C++, object files, and `bin/adder-demo` there, then runs it.
`run.sh` guards the generated object set: model + 1 module + 4 processes
(source, delay, alu, sink) = 6 objects.

## Compilation stages

```sh
build/dev-llvm22/bin/acir-opt --verify-each=false \
  --pass-pipeline='builtin.module(ac-freeze-topology)' \
  examples/chao/adder/model.mlir -o examples/chao/adder/build/model.frozen.mlir

build/dev-llvm22/bin/acir-opt --ac-lower-to-acsim \
  --ac-binding-profile=fast --ac-binding-target=x86_64-linux-gnu \
  examples/chao/adder/build/model.frozen.mlir \
  -o examples/chao/adder/build/model.acsim.mlir

build/dev-llvm22/bin/acir-cxxgen \
  examples/chao/adder/build/model.acsim.mlir --stop-after=link \
  --output-root=examples/chao/adder/build/generated \
  --project-name=chao-adder --project-identity=project.chao.adder \
  --system-name=adder_demo --system-identity=system.adder_demo \
  --profile=fast --compiler=/usr/bin/c++ --standard-library=libstdc++ \
  --abi-mode=default --object-format=elf --contract-flag=-std=c++20 \
  --include-root=/home/lc/AC/agentic-circuit/include \
  --link-input=/home/lc/AC/agentic-circuit/build/dev-llvm22/lib/gfsim/libgfsim.a \
  --link-input=/home/lc/AC/agentic-circuit/build/dev-llvm22/lib/Bindings/libACIRBindings.a \
  --linker-flag=-L/usr/lib/llvm-22/lib --linker-flag=-lLLVM
```

## Runner

`runner.cpp` links against the generated model objects, applies `maxTicks=12`,
prints every statistic, and returns nonzero if any expected value does not
match. Same discipline as `examples/chao/router2x2` and `fu_latency`: exact
values pinned from a deterministic run.
