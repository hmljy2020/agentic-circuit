# NoC VC1 credit/IQ timing execution ledger

Baseline: `7fb9ce7` (`main` is one commit ahead of `chao/main`).

Resource policy: every native build uses `ulimit -v 1900000`, `--parallel 1`,
and lit/CTest uses `-j1`.  Test failures are reported honestly; assertions are
not weakened to manufacture a pass.

The eight pre-existing modifications under `examples/chao/{adder,crossbar_vc,
crossbar_vc_rtl_ideal,fu_latency,queue,router2x2}` are user-owned and excluded
from all commits for this work.

Statuses are limited to `TODO`, `IN_PROGRESS`, `DONE`, and `BLOCKED`; at most
one item is `IN_PROGRESS`.

| ID | Status | Work item | Acceptance evidence | Commit |
|---:|:---:|---|---|---|
| 0 | DONE | Ledger and baseline | `git status --short --branch`: `main` ahead 1; eight protected edits recorded | ledger commit |
| 1 | DONE | Mesh schema, validation, specialization | catalog 36; contracts 21/21; NoC frontend 8/8 | schema commit |
| 2 | IN_PROGRESS | Topology-neutral NoC descriptors | synthetic non-Mesh descriptor test | pending |
| 3 | TODO | VC state and reverse credit events | ACIR verify/freeze/lower | pending |
| 4 | TODO | Single-stage credit VC runtime | owner, credit, backpressure and invalid-route tests | pending |
| 5 | TODO | Owner-only saturation curve | two byte-identical benchmark runs | pending |
| 6 | TODO | Input-queued ingress state machine | exact VA/SA timing tests | pending |
| 7 | TODO | IQ runtime and contention | owner retention, fairness, reset and conservation | pending |
| 8 | TODO | IQ/BookSim comparison | durable raw data, summary, plot and hashes | pending |
| 9 | TODO | Genericity/Ring reuse proof | common emitter contains no topology decisions | pending |
| 10 | TODO | Final serial regression and documentation | catalog, contracts, frontend, CTest, examples, diff check | pending |

## Fixed interface

`MeshNoC` retains `ready_valid + single_stage_elastic` as its default.  The
extension adds `flow_control="credit"`,
`router_pipeline="single_stage_elastic|input_queued"`, `credit_delay`,
`vc_alloc_delay`, `sw_alloc_delay`, and `wait_for_tail_credit`.  VC count,
link latency, and speedups remain fixed at one.  Packet payloads remain atomic
single-flit values.

## Target acceptance commands

```sh
python scripts/generate-stdlib-catalog.py --check
PYTHONPATH=src:build/dev-llvm22/python python -m unittest tests.contracts.test_contracts -q
PYTHONPATH=src:build/dev-llvm22/python python -m unittest tests.python_frontend.test_noc tests.python_frontend.test_packet -q
ulimit -v 1900000; cmake --build --preset dev-llvm22 --parallel 1
ulimit -v 1900000; ctest --test-dir build/dev-llvm22 -j1 --output-on-failure
examples/chao/acpy_mesh_noc/build-run.sh
examples/chao/acpy_mesh_packet_noc/build-run.sh
examples/chao/acpy_mesh_packet_noc/run-booksim-comparison.sh
git diff --check
```
