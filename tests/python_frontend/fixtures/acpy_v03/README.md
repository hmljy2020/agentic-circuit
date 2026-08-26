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
| `topology/static_topology.py` | Static `if`/`for`, nested scope, route/merge/fork, and explicit transport |
| `feedback/feedback.py` | Deferred forward reference lowered into a positive-latency cyclic Queue SSA graph |

## Negative examples

Files under `invalid/` each isolate one unsupported or illegal construct. They
must fail during source capture, semantic elaboration, or semantic verification;
they intentionally have no `.ac.mlir` golden because no ACIR may be emitted.
Each file's module docstring states the boundary it exercises.

