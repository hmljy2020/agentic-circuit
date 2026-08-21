# ACPy Packet to NoC execution ledger

Baseline: `62ccde94e39a74278f9812978b78fa796e7ddfe9`

Pre-existing worktree changes: fixes for runnable `examples/chao` scripts and
strict generated-model ABI 2 checking.  They are user-owned and must be
preserved; this work intentionally advances the generated ABI to 3.

Resource policy: native builds use `ulimit -v 1900000`, `--parallel 1`, and
lit/CTest use `-j1`.  Real failures are recorded and assertions are never
weakened to manufacture a pass.

| ID | Status | Work item | Acceptance evidence |
|---:|:---:|---|---|
| 0 | DONE | Ledger and RED tests | Public `acir-opt` exposed missing canonical record assembly; executable exposed duplicate Packet helpers. Both failures reproduced before fixes. `232ce4d`. |
| 1 | DONE | Packet/Struct ACPy types and natural layout | `PYTHONPATH=src python -m unittest tests.python_frontend.test_packet -v`: 5/5 pass, including public verifier. `232ce4d`. |
| 2 | DONE | Typed process Packet operations and Queue/Flow | Constructor/get/with/serialize/deserialize/typed Queue test passes in the Packet suite. `232ce4d`. |
| 3 | DONE | Packet-capable RingNoC/MeshNoC route field | Packet Ring and Mesh route through a named top-level i32 field; invalid field rejected; frontend 77/77 passes; catalog check passes. `232ce4d`. |
| 4 | DONE | Strict ABI 3 byte host ingress/egress | Exact input/output size APIs and strict Python ABI 3 exercised by the executable; `CodeGenTests` 1/1 passes in 97.84 s. `232ce4d`. |
| 5 | DONE | 2x2 Packet Mesh executable example and docs | `examples/chao/acpy_mesh_packet_noc/build-run.sh` passes every stage; `ticks=8 delivered=4 packet_bytes=8`. `232ce4d`. |
| 6 | DONE | Serial directed and full regression | contracts 21/21; frontend 77/77; lit 116/116; CTest 12/12; targeted native Packet lit 1/1; `git diff --cached --check` passes. `232ce4d`. |

## Fixed boundary

- Packet is one immutable atomic Queue entry.
- Packet size does not imply flits, link cycles, virtual channels, ownership,
  credits, packetization, or reassembly.
- Packet NoC routing reads one top-level `i32` field named by `route_field` and
  applies the existing `route_offset` encoding.
- Host Packet values use exact-width bytes.
