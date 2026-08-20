# NoC MVP execution ledger

Baseline: `ea248987f57062b85c8d5e8e2dc91ffae0677594`

Resource policy: every native build uses `ulimit -v 1900000`, `--parallel 1`, and
lit/CTest uses `-j1`. Parallel C++ compilation is prohibited.

Known baseline issue: `ModuleInstantiationCycleHasOwnershipDiagnostic` can recurse
before ownership-cycle detection and exhaust memory. Step 21 owns the fix and must
record a bounded reproducer and its final diagnostic.

Statuses are limited to `TODO`, `IN_PROGRESS`, `DONE`, and `BLOCKED`; at most one
row may be `IN_PROGRESS`. A `DONE` row records its acceptance command, result, and
commit. Ring, Mesh, and final-regression milestones are pushed to `chao/main`.

| ID | Day | Status | Work item | Acceptance evidence | Commit |
|---:|:---:|:---:|---|---|---|
| 0 | 1 | DONE | Execution ledger and baseline | `git status --short --branch`; clean `ea24898`, ledger present | `docs: add NoC MVP execution ledger` (this commit) |
| 1 | 1 | IN_PROGRESS | Public RingNoC/MeshNoC schemas, catalog, fingerprints | Pending | Pending |
| 2 | 1 | TODO | Canonical generator dispatch | Pending | Pending |
| 3 | 1 | TODO | NoC assignment/input validation | Pending | Pending |
| 4 | 1 | TODO | Specialization and ACPy grouping | Pending | Pending |
| 5 | 1 | TODO | Shared deterministic NoC lowering utilities | Pending | Pending |
| 6 | 1 | TODO | RingNoC ACIR generation | Pending | Pending |
| 7 | 1 | TODO | Ring backend smoke tests (2/4/8 nodes) | Pending | Pending |
| 8 | 1 | TODO | Ring milestone commit and push | Pending | Pending |
| 9 | 2 | TODO | Ring ACPy executable example | Pending | Pending |
| 10 | 2 | TODO | Ring deterministic runtime runner | Pending | Pending |
| 11 | 2 | TODO | MeshNoC ACIR generation | Pending | Pending |
| 12 | 2 | TODO | Deterministic XY routing | Pending | Pending |
| 13 | 2 | TODO | Mesh ACPy executable example | Pending | Pending |
| 14 | 2 | TODO | Mesh deterministic runtime runner | Pending | Pending |
| 15 | 2 | TODO | Mesh milestone commit and push | Pending | Pending |
| 16 | 3 | TODO | Contention and backpressure tests | Pending | Pending |
| 17 | 3 | TODO | Invalid destination tests | Pending | Pending |
| 18 | 3 | TODO | Scale and complexity guards | Pending | Pending |
| 19 | 3 | TODO | Local capture API acceptance | Pending | Pending |
| 20 | 3 | TODO | Static route-emitter registry | Pending | Pending |
| 21 | 3 | TODO | Module-cycle OOM baseline fix | Pending | Pending |
| 22 | 3 | TODO | README and usage documentation | Pending | Pending |
| 23 | 3 | TODO | Final related regression | Pending | Pending |
| 24 | 3 | TODO | Final commit, ledger, and push | Pending | Pending |

## Target acceptance commands

Exact paths/targets are refined as the implementation discovers repository-native
commands. All commands remain serial and under the memory cap.

```sh
python -m pytest tests/contracts tests/python_frontend -q
ulimit -v 1900000; cmake --build --preset release-llvm22 --parallel 1
ulimit -v 1900000; ctest --test-dir build/release-llvm22 -j1 --output-on-failure
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
