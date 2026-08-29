# Agentic Circuit memory examples

This directory contains the two canonical memory examples for contract epoch
`0.4`. Generated ACIR, QueueGraph JSON, C++, PYC, and RTL are build artifacts;
write them under `/tmp` rather than checking them in.

## Dynamically selected two-dimensional memory array

`memory_array.py` uses `ac.array((2, 2), ac.memory(...))`. One tuple-valued
`requests.apply(decode)` keeps row, column, address, ID, write flag, and data
coupled in one Queue token. `banks[row, col].request(...)` lowers to one
ownership-only `ac.array` and one `ac.array.invoke`; only the selected bank is
accessed, different banks can overlap, and completion-order responses carry ID.

From the repository root:

```bash
PYTHONPATH=src \
  .venv/bin/python \
  tools/ac-queue-cxxgen.py examples/memory/memory_array.py \
  --system memory_array \
  --acir-output /tmp/memory_array.mlir \
  --plan-output /tmp/memory_array.plan.json \
  --acir-opt build/dev-llvm22/bin/acir-opt \
  --queue-plan-tool build/dev-llvm22/bin/acir-queue-plan \
  --queue-cxxgen-tool build/dev-llvm22/bin/acir-queue-cxxgen \
  --output /tmp/memory_array.generated.cpp

c++ -std=c++20 -Iinclude -I/tmp -Iexamples/memory \
  examples/memory/memory_array_harness.cpp \
  -o /tmp/memory_array_sim

/tmp/memory_array_sim
```

Expected output:

```text
responses=6 bank00=41 bank01=52 bank10=63
```

## DMA-style DRAM-to-SRAM copy

`dma.py` declares root-owned DRAM and SRAM instances. Inside
`with ac.scope("dma")`, the DRAM response Queue directly drives an SRAM write
endpoint. The harness first seeds `DRAM[5]` with `0x1234`, runs one DMA copy to
`SRAM[3]`, then reads SRAM back to verify the transferred value.

```bash
PYTHONPATH=src \
  .venv/bin/python \
  tools/ac-queue-cxxgen.py examples/memory/dma.py \
  --system dma \
  --acir-output /tmp/dma.mlir \
  --plan-output /tmp/dma.plan.json \
  --acir-opt build/dev-llvm22/bin/acir-opt \
  --queue-plan-tool build/dev-llvm22/bin/acir-queue-plan \
  --queue-cxxgen-tool build/dev-llvm22/bin/acir-queue-cxxgen \
  --output /tmp/dma.generated.cpp

c++ -std=c++20 -Iinclude -I/tmp -Iexamples/memory \
  examples/memory/dma_harness.cpp \
  -o /tmp/dma_sim

/tmp/dma_sim
```

Expected output:

```text
seed_tick=5 copy_tick=14 verify_tick=19 dram_value=0x1234 copy_old_sram=0
```

## Current boundary

The `0.4` contract supports one physical port and one outstanding request per
memory instance. It does not provide true multi-port access, round-robin
fairness, byte enables, or non-zero initialization. A continuously valid
higher-priority endpoint can starve lower ordinals. Different banks in a
dynamic array operate independently, so their responses may complete out of
order and must be matched by ID.
