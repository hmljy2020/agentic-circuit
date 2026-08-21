# NoC MVP execution ledger

Baseline: `ea248987f57062b85c8d5e8e2dc91ffae0677594`

Resource policy: every native build uses `ulimit -v 1900000`, `--parallel 1`, and
lit/CTest uses `-j1`. Parallel C++ compilation is prohibited.

Resolved baseline issue: `ModuleInstantiationCycleHasOwnershipDiagnostic` used to
recurse before ownership-cycle detection and exhaust memory. Step 21 now runs the
bounded graph verifier first; the focused regression completes in 1 ms.

Statuses are limited to `TODO`, `IN_PROGRESS`, `DONE`, and `BLOCKED`; at most one
row may be `IN_PROGRESS`. A `DONE` row records its acceptance command, result, and
commit. Ring, Mesh, and final-regression milestones are pushed to `chao/main`.

| ID | Day | Status | Work item | Acceptance evidence | Commit |
|---:|:---:|:---:|---|---|---|
| 0 | 1 | DONE | Execution ledger and baseline | `git status --short --branch`; clean `ea24898`, ledger present | `af0420d` |
| 1 | 1 | DONE | Public RingNoC/MeshNoC schemas, catalog, fingerprints | `generate-stdlib-catalog.py --check`: 36 schemas; contracts pass; repeat-load fingerprints equal | `15585fc` |
| 2 | 1 | DONE | Canonical generator dispatch | Crossbar 4/4; explicit unknown-generator unit test | `7a3f332` |
| 3 | 1 | DONE | NoC assignment/input validation | invalid arity/depth/dimensions/routes produce located `ACPY-NOC-001` | `7a3f332` |
| 4 | 1 | DONE | Specialization and ACPy grouping | rename shares fingerprint; depth/shape differ; results carry `node_id` | `7a3f332` |
| 5 | 1 | DONE | Shared deterministic NoC lowering utilities | repeat ACIR/ACSim byte comparison; stable queue/resource naming | `7a3f332` |
| 6 | 1 | DONE | RingNoC ACIR generation | 4 links, 4 schedulers, `link_n3_to_n0_cw`; verifier/freeze OK | `7a3f332` |
| 7 | 1 | DONE | Ring backend smoke tests (2/4/8 nodes) | all three freeze and ACIR-to-ACSim commands exit 0 | `7a3f332` |
| 8 | 1 | DONE | Ring milestone commit and push | Core tests passed; `7a3f332` pushed to `chao/main` | `7a3f332` |
| 9 | 2 | DONE | Ring ACPy executable example | ACPy -> freeze -> ACSim -> C++ compile/link exits 0 | `c70b1c8` |
| 10 | 2 | DONE | Ring deterministic runtime runner | wrap, Local, wrong-ejection, conservation and peak assertions pass; repeated stdout hashes match | `c70b1c8` |
| 11 | 2 | DONE | MeshNoC ACIR generation | 1x1/2x2/4x4 verify+freeze; 2x2 has 8 directed links | `7a3f332` |
| 12 | 2 | DONE | Deterministic XY routing | emitted X-first E/W then Y N/S and Local; verifier passes | `7a3f332` |
| 13 | 2 | DONE | Mesh ACPy executable example | ACPy -> freeze -> ACSim -> C++ compile/link exits 0 | `c70b1c8` |
| 14 | 2 | DONE | Mesh deterministic runtime runner | bidirectional diagonal and Local delivery, wrong-ejection, conservation and peak assertions pass | `c70b1c8` |
| 15 | 2 | DONE | Mesh milestone commit and push | both executable milestones passed; `c70b1c8` pushed to `chao/main` | `c70b1c8` |
| 16 | 3 | DONE | Contention and backpressure tests | Ring/Mesh contend for one output; runner requires the same FlowLink to report both `stalled_full > 0` and `transferred > 0`; all Queue bounds/conservation pass | final commit |
| 17 | 3 | DONE | Invalid destination tests | executable Ring3 dst=3 and Mesh3x1 x=3 retain occupancy=2/completion=0 while independent legal traffic completes | final commit |
| 18 | 3 | DONE | Scale and complexity guards | Ring16 (87,858-byte ACIR) and Mesh4x4 (248,712-byte ACIR) freeze/lower/C++ link under 1.9 GB; 4x4 candidates <=25/router | `7a3f332`, acceptance at final commit |
| 19 | 3 | DONE | Local capture API acceptance | examples use `import_flow` plus `(value, arrived)=try_recv`; generated ACIR and ejection statistics verified | `c70b1c8` |
| 20 | 3 | DONE | Static route-emitter registry | registry contains only Crossbar, ring.clockwise, mesh.xy emitters; unknown identity diagnostic tested | `7a3f332` |
| 21 | 3 | DONE | Module-cycle OOM baseline fix | focused test passes in 1 ms; full `ACIRToACSimTests` passes | `c70b1c8` |
| 22 | 3 | DONE | README and usage documentation | API, numbering, route layout, capture, commands, statistics and limitations documented | final commit |
| 23 | 3 | DONE | Final related regression | CTest 6/6; frontend 69/69; contracts 21/21; catalog 36; both runners pass twice with byte-identical stdout; `git diff --check` clean | final commit |
| 24 | 3 | DONE | Final commit, ledger, and push | ignored build products excluded; final tree and remote verified after push | final commit |

## BookSim saturation extension

This post-MVP extension applies only to `MeshNoC`.  It defines a common,
single-stage elastic microarchitecture profile suitable for comparison with a
matching BookSim model; it does not claim equivalence with BookSim's default IQ
router or delayed-credit pipeline.

| ID | Day | Status | Work item | Acceptance evidence | Commit |
|---:|:---:|:---:|---|---|---|
| 25 | Ext | DONE | Public fixed Mesh microarchitecture profile | Catalog 36 check passes; frontend rejects non-unit VC/latency/speedup and unsupported flow-control/pipeline values | `11d5529` |
| 26 | Ext | DONE | Stateful round-robin arbitration | Pointer next-state is grant-selected; 2x2 sustained runtime contention completes West/Local 11/11 with gap 0 | `72704d5` |
| 27 | Ext | DONE | Mesh round-robin lowering | 2x2 and 4x4 ACIR verify; 4x4 owns 64 independent egress pointers and <=25 candidates/router; fixed mode emits no RR state | `72704d5` |
| 28 | Ext | DONE | Fixed profile timing contract | README fixes next-tick link visibility and explicitly excludes hidden RC/VA/SA/ST and credit-return delay | `7ff4dcb` |
| 29 | Ext | DONE | Contention, fairness, scale, and determinism acceptance | 2x2 sustained runtime fairness plus conservation/capacity pass; 4x4 structure verifies; repeated runtime stdout SHA-256 is identical | `72704d5` |
| 30 | Ext | DONE | BookSim mapping, regression, milestone push | Catalog 36, contracts 21/21, frontend 70/70, CTest 12/12, Ring and Mesh executable pipelines pass; milestone `7ff4dcb` pushed to `chao/main` | final ledger commit |

Deferred difficulty assessment:

- A deterministic Bernoulli `NoCTrafficSource` is medium-high effort: the
  catalog entry is currently only a declarative placeholder and there is no
  runtime injection-rate/seed channel or implemented uniform/transpose source.
- A measurement-window `NoCThroughputExperiment` is medium effort: Queue
  counters are cumulative and the generated Model lacks a warmup checkpoint,
  counter snapshot/reset, or measurement-gated ejection counter.

## Target acceptance commands

Exact paths/targets are refined as the implementation discovers repository-native
commands. All commands remain serial and under the memory cap.

```sh
PYTHONPATH=src:build/dev-llvm22/python python -m unittest discover -s tests/python_frontend -p 'test_*.py' -q
PYTHONPATH=src:build/dev-llvm22/python python -m unittest tests.contracts.test_contracts -q
python scripts/generate-stdlib-catalog.py --check
ulimit -v 1900000; cmake --build --preset dev-llvm22 --parallel 1
ulimit -v 1900000; ctest --test-dir build/dev-llvm22 -j1 --output-on-failure
./examples/chao/acpy_ring_noc/build-run.sh
./examples/chao/acpy_mesh_noc/build-run.sh
git diff --check
```

## Fixed MVP scope

- `RingNoC`: 2--16 nodes, unidirectional clockwise routing.
- `MeshNoC`: at most 4x4, node ID `y * width + x`, deterministic XY routing.
- One `i32` is one complete single-flit message; route bits remain in the payload.
- One ready-valid VC, FIFO backpressure, greedy fixed priority.
- Every node has local injection/ejection; invalid destinations remain in ingress.
- No multi-flit, adaptive routing, torus, shortest bidirectional ring, escape VC, or
  general routing DSL.
