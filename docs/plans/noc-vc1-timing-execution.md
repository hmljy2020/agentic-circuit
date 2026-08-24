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
| 2 | DONE | Topology-neutral NoC descriptors | synthetic transit/forward descriptor has no Mesh directions; frontend 9/9 | owner commit |
| 3 | DONE | VC state and reverse credit channels | ordinary credit Queue + countdown; verify/freeze/lower pass | owner commit |
| 4 | DONE | Single-stage credit VC runtime | delivery ticks 6,8; backpressure 4/4; conservation/capacity and independent traffic pass | owner commit |
| 5 | DONE | Owner-only saturation curve | rate 1.0 mean 0.567625; repeated CSV/summary/PNG SHA-256 identical | owner commit |
| 6 | DONE | Input-queued ingress state machine | ACIR verify; VA/SA constants 101/201; runtime delivery ticks exactly 10,15 | `3eeae5a` |
| 7 | DONE | IQ runtime and contention | backpressure 4/4; RR order 300,400,...; reset and all Queue invariants pass | `3eeae5a` |
| 8 | DONE | IQ/BookSim comparison | two 30-point runs byte-identical; IQ mean at rate 1.0 = 0.228291667 | `3eeae5a` |
| 9 | DONE | Genericity/Ring reuse proof | synthetic transit/inject/capture/forward IQ emitter contains no cardinal directions | `3eeae5a` |
| 10 | DONE | Final serial regression and documentation | catalog 36; contracts 21/21; frontend 14/14; CTest 12/12; four executable profiles and both comparison scripts pass; diff check clean | final ledger commit |

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
examples/chao/noc/acpy_mesh_noc/build-run.sh
examples/chao/noc/acpy_mesh_packet_noc/build-run.sh
examples/chao/noc/acpy_mesh_packet_noc/run-booksim-comparison.sh
git diff --check
```

## Final acceptance evidence

- `python scripts/generate-stdlib-catalog.py --check`: 36 schemas, passed.
- contracts command above: 21 tests passed.
- NoC/Packet frontend command above: 14 tests passed, including ACIR verification.
- constrained single-thread build: passed; CTest: 12/12 in 254.91 seconds.
- `acpy_mesh_noc/build-run.sh`: full chain and runtime passed in 36.98 seconds.
- Packet default: 4/4 delivered; owner-only: ticks 6,8 and backpressure
  4/4; IQ: ticks 10,15, backpressure 4/4, deterministic alternating
  contention, reset, conservation, and capacity checks passed.
- Both BookSim comparison scripts passed. Two full IQ comparisons produced
  identical hashes recorded in `benchmark-results/vc1-iq/README.md`.
- `git diff --check`: passed. The eight protected user modifications remain
  present and were not staged or committed.
