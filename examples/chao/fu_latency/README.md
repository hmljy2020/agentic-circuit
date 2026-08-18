# `ac.event_queue` ACIR example: dispatch and latency completion

`model.mlir` is a self-contained ACIR model of a simple functional unit driven
by two native event queues. A workload producer schedules one work item
(payload `7`) into the `dispatch` event queue every tick with a two-tick delay.
A functional-unit control process pops it, adds one, asserts the result is `8`,
and re-schedules it into the `complete` event queue with a one-tick latency. A
retire control process forwards completed events into a capacity-one native
`results` FIFO, and a sink control process consumes and re-checks them. All four
processes stream continuously, so the run is capped by `maxTicks` (see
`runner.cpp`).

Event queues are single-consumer: each `ac.try_event`/`ac.await_event` pair
must live in one process and name the same queue. `ac.schedule` is a soft
proposal committed at the next transfer barrier; a full queue simply rejects it
(`accepted == false`). An event becomes visible to `ac.try_event` exactly at
its ready tick (schedule tick plus delay), ordered by
`time_then_sequence` (ready time first, then insertion order).

The capacity-one `results` FIFO throttles the retire stage: when `results` is
full, retire parks the completed value in a live slot and retries the send
instead of popping another completion, so the `complete` queue carries the
corresponding backlog.

## Checked run

The checked run uses a twelve-tick cap. Expected statistics:

| object | accepted | completed | occupancy | occupancy peak |
| --- | --- | --- | --- | --- |
| `dispatch` (event queue) | 12 | 10 | 2 | 2 |
| `complete` (event queue) | 10 | 5 | 5 | 5 |
| `results` (native queue) | 5 | 4 | 1 | 1 |

Expected classification is `Incomplete` at `finalEpoch {12, 0}`, with 18
published observations. The values above were captured from a deterministic
run: execute `bin/fu-demo` twice and the output is byte-identical.

## Build and run

```sh
examples/chao/fu_latency/build-run.sh
```

The script rebuilds `examples/chao/fu_latency/build` and keeps the frozen ACIR,
lowered ACSim, generated C++, object files, and `bin/fu-demo` there after the
run. `model.frozen.mlir` and `model.acsim.mlir` at the example root remain
checked-in snapshots for inspection.

## Compilation stages

The stages used to produce them were:

```sh
build/dev-llvm22/bin/acir-opt --verify-each=false \
  --pass-pipeline='builtin.module(ac-freeze-topology)' \
  examples/chao/fu_latency/model.mlir \
  -o examples/chao/fu_latency/build/model.frozen.mlir

build/dev-llvm22/bin/acir-opt --ac-lower-to-acsim \
  --ac-binding-profile=fast --ac-binding-target=x86_64-linux-gnu \
  examples/chao/fu_latency/build/model.frozen.mlir \
  -o examples/chao/fu_latency/build/model.acsim.mlir

build/dev-llvm22/bin/acir-cxxgen \
  examples/chao/fu_latency/build/model.acsim.mlir \
  --stop-after=link --output-root=examples/chao/fu_latency/build/generated \
  --project-name=chao-fu-latency --project-identity=project.chao.fu_latency \
  --system-name=fu_demo --system-identity=system.fu_demo \
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
match. The two `ac.assert` sites in `model.mlir` (functional unit and sink)
make the data path self-checking: any corruption of the payload pipeline fails
the run with `Failed` before the statistic assertions are reached.
