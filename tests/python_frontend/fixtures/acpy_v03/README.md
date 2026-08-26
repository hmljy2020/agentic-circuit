# ACPy v0.3 executable examples

This directory is both a frontend test corpus and a set of small, reviewable
examples of the currently implemented ACPy programming surface.

For every successful example, the adjacent files have distinct roles:

- `name.py` is the ACPy source a user writes;
- `name.ac.mlir` is the exact frozen ACIR emitted by the frontend;
- `minimal/*.semantic.json` additionally exposes the frontend semantic graph.

The unit tests elaborate every source from its AST, compare successful output
byte-for-byte with the adjacent golden, and pass that output through the native
`acir-opt` parser and model verifier when the tool is available. The checked-in
ACIR is review material, not an input substituted for frontend execution.

## Positive examples

| Source | Purpose |
| --- | --- |
| `minimal/system.py` | Smallest `source -> compute -> observe` vertical slice |
| `extended/scalar_chain.py` | Scalar payloads, repeated compute, and non-consuming observation |
| `extended/multi_field.py` | Struct field reads, typed literals, arithmetic, layout, and construction |
| `extended/bool_literal.py` | Boolean literal inference in a struct field |
| `extended/arithmetic_family.py` | Complete currently supported pure binary-operator family |
| `extended/queue_contracts.py` | Explicit boundary and transport Queue contracts |
| `topology/static_topology.py` | Static `if`/`for`, nested scope, route/merge/fork, and explicit transport |
| `topology/destructuring.py` | Flat tuple/list result binding and Queue collections |
| `topology/static_specialization.py` | Config-pruned branches and statically expanded observations |
| `feedback/feedback.py` | Deferred forward reference lowered into a positive-latency cyclic Queue SSA graph |
| `feedback/multiple_feedback.py` | Multiple deferred aliases closed through one topology |

Files under `boundary/` are accepted by semantic elaboration but intentionally
prove a later ACPy-to-ACIR limitation. For example, `merge_priority.py` records
that the semantic graph can hold the policy while the current emitter cannot
yet encode it.

## Negative examples

Files under `invalid/` each isolate one unsupported or illegal construct. They
must fail during source capture, semantic elaboration, or semantic verification;
they intentionally have no `.ac.mlir` golden because no ACIR may be emitted.
Each file's module docstring states the boundary it exercises.

## Current tested boundary

The corpus deliberately distinguishes three kinds of Python:

| Area | Accepted now | Rejected now |
| --- | --- | --- |
| Compute helper | One typed return expression; field reads; ordered struct construction; integer/bool literals; `+`, `-`, `*`, `&`, `|`, `^` | Local statements, open captures, conditional expressions, division, arbitrary calls |
| Topology statements | Primitive assignment, `observe`, deferred `bind`, static `if`, bounded static `for`, lexical `scope` | Runtime `while`, dynamic Queue contracts, Queue-name rebinding |
| Multi-port values | Named collection, flat tuple/list destructuring, static indexing, tuple/list merge input | Nested destructuring, dynamic or out-of-range indexing, zero outputs |
| Merge policy | `round_robin` completes ACPy -> ACIR | `priority`/`oldest` reach the semantic graph but stop at the current emitter; unknown names fail earlier |
| Feedback | Typed deferred output, exactly-once bind, multiple forward edges, positive-latency cycle | Unbound/double/self bind, payload mismatch, zero-latency cycle |

This table describes tested implementation behavior through P5. It does not
claim support for the P6 state primitives (`table`, `pool`, or `reorder`).
