# Agentic Circuit

Agentic Circuit is a Python and MLIR-based architecture construction system
that generates a structured, pure C++ graph-flow simulator named `gfsim`.
Its public v0.2 contracts use exact global contract epoch `0.2`.

## Development baseline

The repository is locked to LLVM/MLIR 22.1.8. On Apple Silicon, the default
prefix is `/opt/homebrew/opt/llvm`. On another supported host, pass the
equivalent package explicitly with
`-DMLIR_DIR=/path/to/llvm/lib/cmake/mlir`.

```sh
scripts/bootstrap-dev.sh
source .venv/bin/activate
python -m unittest tests.contracts.test_contracts -v
cmake --preset dev-llvm22
cmake --build --preset dev-llvm22
```

Use `release-llvm22` for a release configuration. The exact upstream release,
commit, archive digest, supported host triples, and version policy are recorded
in `toolchains/llvm.lock.json`.

Normative specifications:

- [Interface Evolution v0.2](docs/specs/interface-evolution-v0.2.md)
- [ACIR Core v0.2](docs/specs/acir-core-v0.2.md)
- [Python-to-ACIR Lowering v0.2](docs/specs/python-to-acir-lowering-v0.2.md)
- [Agentic Python and CLI v0.2](docs/specs/agentic-python-cli-v0.2.md)
- [ACIR Standard Library v0.2](docs/specs/acir-stdlib-v0.2.md)
- [ACSim and gfsim Lowering v0.2](docs/specs/acsim-gfsim-lowering-v0.2.md)
- [gfsim Model Library Contract v0.2](docs/specs/gfsim-runtime-abi-v0.2.md)
- [PTO Trace Schema v0.2](docs/specs/pto-trace-schema-v0.2.md)
- [ACIR Process-State Plan v0.2](docs/specs/acir-process-state-plan-v0.2.md)

Canonical machine-readable schemas:

- [ACPy](schemas/acpy.schema.json)
- [Capabilities](schemas/capabilities.schema.json)
- [ComponentSchema](schemas/component.schema.json)
- [PTO trace](schemas/pto-trace.schema.json)
- [Build manifest](schemas/build-manifest.schema.json)
- [Run manifest](schemas/run-manifest.schema.json)
- [Run result](schemas/run-result.schema.json)
- [Diagnostic](schemas/diagnostic.schema.json)
- [ACSim binding](schemas/acsim-binding.schema.json)
- [ACIR process-state plan](schemas/acir-process-state-plan.schema.json)

## NoC MVP

ACPy provides compiler-native, ready-valid single-flit Ring and Mesh networks.
Every input and result is ordered by node ID, every node has one Local injection
and ejection, and the entire `i32` payload is delivered unchanged.

```python
(rx0, rx1, rx2, rx3) = RingNoC(
    inputs=(tx0, tx1, tx2, tx3),
    queue_depth=2,
    route_offset=0,
    routing="clockwise",
    arbitration="greedy_fixed_priority",
    name="ring",
)
```

Ring supports 2--16 nodes and routes clockwise. Its destination occupies
`max(1, ceil(log2(nodes)))` bits starting at `route_offset`. Transit traffic has
priority over Local injection, and every clockwise link is a stateful Queue, so
the wrap-around edge cannot form a zero-delay combinational cycle.

```python
(rx00, rx10, rx01, rx11) = MeshNoC(
    inputs=(tx00, tx10, tx01, tx11),
    width=2,
    height=2,
    queue_depth=2,
    route_offset=0,
    virtual_channels=1,
    flow_control="ready_valid",
    link_latency=1,
    router_pipeline="single_stage_elastic",
    input_speedup=1,
    output_speedup=1,
    routing="xy",
    arbitration="round_robin",
    name="mesh",
)
```

Mesh dimensions are 1--4 in each direction. Node ID is `y * width + x`, with
`(0, 0)` at the southwest and Y increasing northward. Destination X bits begin
at `route_offset`, followed by Y bits; their widths are inferred from the Mesh
dimensions. Routing is deterministic X-then-Y. An out-of-range Ring or Mesh
destination stalls in its ingress Queue and is not popped.

Mesh also exposes a deliberately narrow BookSim-comparison profile: one VC,
ready-valid flow control, one stateful Queue per directed link, a single-stage
elastic router, and input/output speedup one. Only those exact values are
accepted. Arbitration may be `greedy_fixed_priority` or stateful per-egress
`round_robin`; the latter advances its pointer only when a transfer is granted.
A transfer committed by one router is visible to its neighbour on the next
simulation tick.

This profile can be matched by a custom BookSim configuration/model, but it is
not equivalent to BookSim's default input-queued router: AC currently has no
credit-return delay, separate RC/VA/SA/ST stages, multi-flit packets, or multiple
VCs. Consequently, comparison claims must use this fixed elastic profile rather
than merely giving both simulators similarly named parameters.

Connect ejection explicitly with `import_flow(rxN, (sink_queue,))`; a process
then captures a complete message with
`value, arrived = try_recv(sink_queue)`. The runnable examples exercise Local,
multi-hop, Ring wrap-around, XY routing, contention, and FIFO backpressure:

```sh
./examples/chao/acpy_ring_noc/build-run.sh
./examples/chao/acpy_mesh_noc/build-run.sh
```

Both scripts keep generated files under ignored `build-noc` directories and run
the complete ACPy -> ACIR -> frozen ACIR -> ACSim -> C++ executable pipeline.
Their runners require every Queue to satisfy
`accepted_transactions == completed_transactions + queue_occupancy` and
`queue_occupancy_peak <= queue_depth`, and reject traffic at wrong ejections.

This MVP fixes virtual channels to one and supports only one `i32` per complete
message, clockwise Ring routing, and XY Mesh routing. Ring uses greedy
fixed-priority arbitration; Mesh also supports per-egress round-robin. It
intentionally excludes multi-flit packets, adaptive routing,
Torus links, bidirectional shortest-path Ring routing, and escape VCs.

## Project policies

Contributions are accepted under the [Apache License 2.0](LICENSE). See
[Contributing](CONTRIBUTING.md), the [Code of Conduct](CODE_OF_CONDUCT.md),
[Security policy](SECURITY.md), and [Support policy](SUPPORT.md) before opening
a change or report.
