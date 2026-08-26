# Agentic Circuit DMA and memory v0.3 prototype

| Field | Value |
| --- | --- |
| Contract epoch | `0.3` |
| Status | Frontend and native ACIR prototype |
| Scope | One blocking read-then-write DMA transaction |
| Backend support | Not provided by this prototype |

## Purpose

This prototype lets an engine describe a memory interaction as serial-looking
code instead of manually constructing memory request and response Queues:

```python
dram = ac.memory(
    kind="dram",
    capacity_bytes=1 << 30,
    read_latency=40,
    write_latency=20,
    bytes_per_cycle=32,
)
sram = ac.memory(
    kind="sram",
    capacity_bytes=1 << 20,
    read_latency=2,
    write_latency=2,
    bytes_per_cycle=64,
)

with ac.scope("tma_engine"):
    def execute(op):
        data = dram.read(op.src, size=op.size)
        sram.write(op.dst, data)
        return op

    completed = requests.process(execute, inflight=1, depth=1)
```

The helper is declarative syntax captured from the Python AST. It is not an
ordinary Python function and does not need `await`: statement order and the
opaque `data` dependency establish read-before-write ordering.

## Memory contract

`ac.memory` declares a named component with five required static properties:

- `kind` is `"sram"` or `"dram"`;
- `capacity_bytes` and `bytes_per_cycle` are positive integers; and
- `read_latency` and `write_latency` are non-negative integer base latencies.

An access of `size` bytes has timing

```text
read_cycles  = read_latency  + ceil(size / bytes_per_cycle)
write_cycles = write_latency + ceil(size / bytes_per_cycle)
```

The process is blocking and serial, so the write begins only after the read
finishes. The process completes after both access durations. Its output Queue
latency is a separate positive Queue-edge latency.

This prototype permits one process client per declared memory and
`inflight=1`. That restriction avoids defining arbitration before memory ports
and concurrent outstanding transactions have a complete contract. While the
process is busy or its completion cannot advance, it backpressures its input
Queue.

## Transfer semantics

The value returned by `memory.read` lowers to `!ac.memory_transfer`. It is a
linear, opaque timing token, not a byte array:

- exactly one `ac.memory.write` consumes it;
- the write size is inherited from the read;
- read and write addresses and size are integer Vars no wider than 64 bits;
- a statically known zero size or out-of-capacity access is rejected; and
- the Queue payload returned by the helper must preserve its input payload
  type.

Consequently the model expresses DMA latency, sequencing, completion, and
backpressure. It does not model memory contents or validate copied values.

## ACIR contract

The frontend emits contract epoch `0.3` and these native ACIR additions:

- `ac.memory.resource` for named component timing contracts;
- `ac.queue.process` and `ac.queue.process.yield` for the blocking engine body;
- `ac.memory.read` and `ac.memory.write` for the ordered accesses; and
- `!ac.memory_transfer` for their linear dependency.

The native parser and verifier accept epoch `0.3`; every new operation rejects
use under epoch `0.2`. Existing epoch `0.2` syntax and behavior are unchanged.

The C++, PYC, Verilog, ACSim, and gfsim lowerings do not implement these v0.3
operations. Connecting those backends requires a later memory-port,
arbitration, and runtime timing design.
