# `crossbar_vc` ACIR example: 2×2 input-queued crossbar with per-channel virtual channels

`model.mlir` is a self-contained ACIR v0.2 model of a **2×2 input-queued
crossbar with two virtual channels (VC `A`, VC `B`) per physical channel**:
eight logical queues (`in0.A/B`, `in1.A/B`, `out0.A/B`, `out1.A/B`). A single
centralized scheduler process computes a matching every cycle and commits up to
two transfers **atomically in the same simulation epoch**.

Two scheduler variants are provided. `model.mlir` preserves the original
send/receive feasibility model. `model.rtl-ideal.mlir` is the preferred
compiler-native variant: it uses `ac.arbitrate greedy_fixed_priority` and
atomic `ac.try_transfer`, and is supported through ACSim and generated C++.
The RTL backend, capacity greater than one, and fair/round-robin arbitration
remain future work.

## What the model does

Two workload producers continuously re-propose flits into the four input VCs
(one `A` and one `B` per physical input); the scheduler moves them to the four
output VCs; two self-checking sinks drain the outputs and verify every flit.

| source | flit | value | route |
| --- | --- | --- | --- |
| `@producer0` | `A` (dst 0, vc A, src 0, seq 0) | `0` | `in0_A → out0_A` |
| `@producer0` | `B` (dst 1, vc B, src 0, seq 1) | `28949` | `in0_B → out1_B` |
| `@producer1` | `A` (dst 1, vc A, src 1, seq 2) | `49961` | `in1_A → out1_A` |
| `@producer1` | `B` (dst 0, vc B, src 1, seq 3) | `78908` | `in1_B → out0_B` |

The traffic crosses every physical input/output combination and both VCs every
cycle, so the matching is exercised at its fullest (two independent transfers
per cycle).

### Flit layout (`i32` bit-fields)

| bits | field | meaning |
| --- | --- | --- |
| `[1:0]` | `dst` | destination output (0 or 1) |
| `[2]` | `vc` | virtual channel (0 = `A`, 1 = `B`) |
| `[3]` | `src` | source input (0 or 1) |
| `[7:4]` | `seq` | injection sequence |
| `[31:8]` | `payload` | `seq*97 + src + vc*16` (corruption + identity + VC check) |

Every sink decodes all four fields and asserts `dst == output index`,
`vc == expected VC of this output queue`, `src == expected source`, and
`payload == seq*97 + src + vc*16`. A cross-VC misroute is impossible by
construction (a flit in `in_x.A` always routes to `out_{dst}.A`), and any
corruption or misroute fails the run at the in-model assert.

## The atomic-transfer idiom

The v0.2 executable op inventory has no transfer op, so the scheduler issues a
grant as two ordered proposals:

```mlir
%h, %v = ac.peek @in_src : i32             // non-destructive read (constant this epoch)
...
scf.if %eligible {
  %sent = ac.try_send @out_dst %h : i32    // 1. propose the PUSH first
  scf.if %sent {
    %val, %got = ac.try_recv @in_src : i32 // 2. pop only after grant confirmed
    ac.assert %got, "granted source must remain receivable"
  }
}
```

All proposals observe the committed snapshot at epoch start and commit at the
**same Xfer barrier**, so a granted pair dequeues the source and enqueues the
destination atomically. A full destination rejects the push (`%sent = 0`),
nothing is proposed, and the flit stays in the source — it is **never dequeued
before its output grant is confirmed**. No process-local holding slot is used.
The scheduler is the sole pop proposer to each input VC and peeked the head
valid, so `%got` always holds; the assert makes any regression fail loudly.

The scheduler body is straight-line and terminates in `ac.yield_sim` — a single
PC with zero suspension points — so every grant commits in the same epoch.
`ac.await_queue` and `scf.for` are deliberately avoided (see *Semantics* below).

## Scheduler matching policy

The scheduler snapshots all eight queues, decodes each valid input head, and
runs the lexicographic matching — one epoch, one Xfer:

1. **A phase — maximize A grants** (higher priority): for output 0 then 1, for
   input 0 then 1, grant `in_x.A → out_dst.A` if the input and output are still
   free.
2. **B phase — fill remaining bandwidth** (lower priority): for input 0 then 1,
   grant `in_x.B → out_dst.B` if the input, its destination output, and that
   output VC are free. A same-destination B/B conflict is resolved by lower
   input (the `%gB1_ok` gate blocks `in1_B` only if `in0_B` won the same
   output).

The four **physical-channel rules** (≤1 flit per physical input, ≤1 per
physical output, per cycle) are **model rules, not runtime rules**: the four
output VCs are independent `SimQueue`s, so nothing at runtime enforces a
"physical output" limit. The `used_in`/`used_out` flags encode the rules in the
matching, and the scheduler re-asserts them in-model before `ac.yield_sim`
(test 6) so any matching regression fails the model itself.

## Semantics worth knowing

The behaviors below are consequences of the toolchain and of the v0.2 proposal
model, not bugs in this example. They are documented here because they are not
obvious from the source.

### 1. `scf.for` drops proposal ops — bodies are manually unrolled

The process-state expansion unrolls static `scf.for` bodies but drops
side-effecting proposal ops (`ac.try_send`) from the unrolled body. The
scheduler and the scenario producers therefore use **explicit straight-line
code and `scf.if` guards only** (see `examples/chao/router2x2/README.md` §1 for
the toolchain investigation). Unrolling also keeps the grant's send-then-recv
pair inside one epoch, preserving atomicity.

### 2. Every process re-fires every tick — traffic is continuous, not one-shot

A process body must terminate in `ac.yield_sim`, which resumes the process at
its entry on the next tick. A producer cannot "burst once then stop": it
re-proposes its constant every tick, and a proposal that finds the queue full is
soft-rejected and retried the next tick (`SimQueue::proposePush`). Scenarios
that need a true one-shot burst gate the producer behind a capacity-1 latch
(`sc09`'s `@gate`).

### 3. Depth-2 output VCs + `ac.space`: A dominates, B starves

A grant pushes into a depth-2 output at the epoch's Xfer; the sink drains it a
later epoch. Because the sink keeps the output mostly drained, the scheduler's
`ac.space @outX_Y` (free-slot count on the committed state) reads `free > 0`
at the start of essentially every epoch, so the A-phase grants both A
transfers **every tick** and the B-phase never finds a free output VC. B is
therefore fully starved: `in*_B` fill to depth 2 and never drain, `out*_B`
stay empty. This is the price of strict `A > B` priority once the depth-1
throttle is removed — exactly test 10, now the primary observable behavior.

### 4. Writability comes from `ac.space`, not from `ac.peek`'s valid flag

`ac.peek` returns `(head, valid)` where `valid = occupancy ≥ 1` — it tells you
*non-empty*, not "full". There is no capacity-aware peek: `writable = !valid`
would only be correct for depth-1 queues, where empty ⟺ writable. The scheduler
therefore reads the free-slot count directly with `ac.space @outX_Y` and tests
`free > 0` (`arith.cmpi sgt` against an i32 zero). This is exactly the gap
`ac.space` (epoch 0.2) was added to close, and it is what lets the output VCs
be depth 2.

## The ten tests and where each is proven

| # | test | where | proof |
| --- | --- | --- | --- |
| 1 | two simultaneous transfers | primary `runner.cpp` | aggregate `inCompletions == 22 > maxTicks (12)`; input completions per epoch are structurally ≤ 2 (one scheduler, ≤ 1 recv per input VC), so some epoch has 2; the in-model per-input assert forces them onto distinct inputs → 2 independent transfers in one cycle |
| 2 | two inputs contend for one output | `scenarios/sc02_contend_out0` | `in0_A` (lower input) granted, `in1_A` blocked; epoch 1 has exactly one `completed` |
| 3 | A beats B on the same input + destination | `scenarios/sc03_a_over_b` | epoch 1 (both eligible, same dest) commits exactly one transfer and it is A's — the sink self-checks `out0_A` only ever carries A flits, and A's first arrival is epoch 1; A dominates the run 3:1 (B's single move is the §3 reuse window) |
| 4 | B moves when no A is eligible | `scenarios/sc04_b_without_a` | B granted to `out0_B` on epoch 1; `in0_A` stays empty |
| 5 | A blocked by a full destination → B uses the bandwidth | `scenarios/sc05_a_blocked_b_moves` | `A0 → out0_A` fills it; epoch 2 `B → out1_B` (different physical output), A seq 1 stays stuck |
| 6 | per-input ≤ 1, per-output ≤ 1 per cycle | primary in-model `ac.assert` ×4 + `scenarios/sc06_same_input_two_vc` | the scheduler re-asserts both rules before `yield_sim`; sc06 shows one input, two ready VCs, different (free) dests → exactly one grant per epoch |
| 7 | backpressure / no loss / no dup | primary + every scenario `runner.cpp` | `accepted == completed + occupancy` and `occupancy_peak ≤ entries` on all queues |
| 8 | determinism | `run.sh` | binary executed twice, output byte-identical (`diff -u` empty) |
| 9 | FIFO within a VC | `scenarios/sc09_fifo_order` | one-shot burst of seq 0..3; the sink's in-model `@prev` register asserts every adjacent pair arrives strictly increasing (`seq == prev + 1`) |
| 10 | B starvation | primary checked run | with depth-2 outputs the A-phase grants every tick, so B never drains: `in*_B` accepted=2/completed=0, `out*_B` all zero (strict `A > B` priority) |

## Scenario suite

`scenarios/` holds six minimal models (only the queues and processes each test
needs), each with a ~50-line `_runner.cpp` and a shared `run_all.sh`:

```
sc02_contend_out0       two inputs, one output  -> lower input wins, 1 grant/epoch
sc03_a_over_b           same input+dest, A and B -> A wins the contention
sc04_b_without_a        B only, no A            -> B granted
sc05_a_blocked_b_moves  A's dest held full      -> B uses other output
sc06_same_input_two_vc  one input, two VCs      -> exactly 1 grant/epoch
sc09_fifo_order         ordered burst seq 0..3  -> sink asserts strict FIFO
```

`run_all.sh` freezes, lowers, generates, links, and runs each scenario, asserts
its generated-object count, and fails on any nonzero runner exit. The object
counts (model + 1 module + processes) are: sc02 5 (2 producers + scheduler),
sc03 5 (producer + scheduler + sink), sc04/05/06 4 (producer + scheduler),
sc09 5 (producer + scheduler + sink).

## Checked run (primary)

The checked run uses a 12-tick cap. Expected statistics (pinned from the
deterministic run; `occupancy` is implied by conservation):

| object | accepted | completed | occupancy | peak |
| --- | --- | --- | --- | --- |
| `in0_A` | 12 | 11 | 1 | 1 |
| `in0_B` | 2 | 0 | 2 | 2 |
| `in1_A` | 12 | 11 | 1 | 1 |
| `in1_B` | 2 | 0 | 2 | 2 |
| `out0_A` | 11 | 10 | 1 | 1 |
| `out0_B` | 0 | 0 | 0 | 0 |
| `out1_A` | 11 | 10 | 1 | 1 |
| `out1_B` | 0 | 0 | 0 | 0 |

Expected classification is `Incomplete` at `finalEpoch {12, 0}`, with 142
published observations. `inCompletions == 22` (test 1) and `maxCompletedPerEpoch
>= 4` (two transfers + two sink drains in the same cycle, confirming test 1 from
the observation stream as well). The A-phase grants every tick: epochs 1..11
each complete the two input transfers (11 + 11), and epochs 2..11 also complete
the two sink drains (10 + 10). The B-phase never grants — test 10.

## Build and run

```sh
bash examples/chao/crossbar_vc/run.sh       # primary model (runs twice, diffs)
bash examples/chao/crossbar_vc/run.sh --rtl-ideal # arbiter + atomic transfer
bash examples/chao/crossbar_vc/scenarios/run_all.sh   # all six scenarios
```

Both scripts set `ulimit -v 1900000` (this machine's DRAM budget), guard their
build directories against symlink tricks, and rebuild from scratch. `run.sh`
keeps the frozen ACIR, lowered ACSim, generated C++, and object files under
`examples/chao/crossbar_vc/build-model/` (or `build-rtl-ideal/`), then links
`bin/crossbar-demo` and executes it twice, diffing the two runs byte-for-byte
(test 8). It also guards the
generated object set: model + 1 module + 5 processes = 7 objects.

## Compilation stages

```sh
build/dev-llvm22/bin/acir-opt --verify-each=false \
  --pass-pipeline='builtin.module(ac-freeze-topology)' \
  examples/chao/crossbar_vc/model.mlir \
  -o examples/chao/crossbar_vc/build/model.frozen.mlir

build/dev-llvm22/bin/acir-opt --ac-lower-to-acsim \
  --ac-binding-profile=fast --ac-binding-target=x86_64-linux-gnu \
  examples/chao/crossbar_vc/build/model.frozen.mlir \
  -o examples/chao/crossbar_vc/build/model.acsim.mlir

build/dev-llvm22/bin/acir-cxxgen \
  examples/chao/crossbar_vc/build/model.acsim.mlir \
  --stop-after=link --output-root=examples/chao/crossbar_vc/build/generated \
  --project-name=chao-crossbar-vc --project-identity=project.chao.crossbar_vc \
  --system-name=crossbar_vc_demo --system-identity=system.crossbar_vc_demo \
  --profile=fast --compiler=/usr/bin/c++ --standard-library=libstdc++ \
  --abi-mode=default --object-format=elf --contract-flag=-std=c++20 \
  --include-root=/home/lc/AC/agentic-circuit/include \
  --link-input=/home/lc/AC/agentic-circuit/build/dev-llvm22/lib/gfsim/libgfsim.a \
  --link-input=/home/lc/AC/agentic-circuit/build/dev-llvm22/lib/Bindings/libACIRBindings.a \
  --linker-flag=-L/usr/lib/llvm-22/lib --linker-flag=-lLLVM
```

## Runner

`runner.cpp` links against the generated model objects, applies `maxTicks = 12`,
prints every statistic and the per-epoch `completed` counts, and returns nonzero
if any expected value does not match. Structural checks are conservation and
capacity on all 8 queues (test 7); the exact steady-state values are pinned from
the deterministic run (test 8), same discipline as `examples/chao/fu_latency`.
The `ac.assert` sites in `model.mlir` — the scheduler's grant send/recv/match
asserts and its four per-input/per-output rule asserts, plus every sink's
four-field self-check — make the whole data path self-checking: any corruption,
misroute, or matching violation fails the run with `Failed` before the runner's
statistic assertions are reached.
