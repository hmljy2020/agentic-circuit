# CLAUDE.md

You are a helpful software engineer assistant.when you thought, thought in ENGLISH, start with "We need..."

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project

Agentic Circuit is a Python + MLIR architecture construction system: an agent-facing Python DSL (ACPy) lowers to the `ac` MLIR dialect (ACIR), which lowers to the `acsim` construction IR, from which `acir-cxxgen` generates a statically specialized pure C++ graph-flow simulator built against the `gfsim` runtime library. All public contracts use exact global contract epoch `0.2`, locked to LLVM/MLIR 22.1.8 (see `toolchains/llvm.lock.json`).

## Local resource constraint (from AGENTS.md)

Keep builds/runs under ~3.2 GB DRAM or this machine crashes. Build with low parallelism, e.g. `cmake --build --preset dev-llvm22 -- -j2`.

## Build

```sh
scripts/bootstrap-dev.sh          # create .venv with locked dev requirements
source .venv/bin/activate
cmake --preset dev-llvm22         # or release-llvm22 / asan-llvm22 / ubsan-llvm22
cmake --build --preset dev-llvm22
```

Presets use `LLVM_PREFIX=/usr/lib/llvm-22` (this host; macOS uses Homebrew). Ninja generator, C++20. `lib/CMakeLists.txt` documents a critical build fact: MLIR-facing libraries compile `-fno-rtti` (upstream LLVM is built without RTTI), while `gfsim` keeps RTTI (uses `dynamic_cast`) — add `gfsim` subdirectory order matters.

## Test commands

Four independent test layers, run from the repo root with `.venv` active:

```sh
# 1. Contract gate (epoch, LLVM lock, governance files) — run first after any contract change
python -m unittest tests.contracts.test_contracts -v

# 2. lit/FileCheck suite over test/**/*.mlir (needs built binaries)
lit -v build/dev-llvm22/test
lit -v build/dev-llvm22/test/ACIR/contracts-valid.mlir   # single file

# 3. GTest unittests (binaries land in build/dev-llvm22/bin/)
ctest --test-dir build/dev-llvm22 --output-on-failure
build/dev-llvm22/bin/ACIRProcessStatePlanTests --gtest_filter='ProcessStatePlanTest.*'

# 4. Python suites — need PYTHONPATH=src:build/dev-llvm22/python (native _native extension)
PYTHONPATH=src:build/dev-llvm22/python python -m unittest discover -s tests/python_frontend -v
PYTHONPATH=src:build/dev-llvm22/python python -m unittest discover -s tests/cli -v
PYTHONPATH=src:build/dev-llvm22/python python -m unittest tests.e2e.test_phase5_examples tests.e2e.test_phase5_npu -v
PYTHONHASHSEED=1 python -m unittest tests.python_frontend.test_determinism -v   # also with 99
```

e2e tests default to `build/dev-llvm22`; override with `AGENTIC_CIRCUIT_TEST_BUILD_DIR`.

Quality gates (CI runs all of these):

```sh
git ls-files "*.cpp" "*.h" | xargs clang-format --dry-run --Werror
git ls-files "lib/*.cpp" "tools/*.cpp" "unittests/*.cpp" | xargs -P 4 -I {} \
  clang-tidy -p build/dev-llvm22 --config-file=.clang-tidy \
  --header-filter='.*agentic-circuit/(include|lib|tools|unittests)/.*' {}
python -m unittest tests.contracts.test_ir_coverage -v && python scripts/check-ir-coverage.py
```

## Architecture

The lowering pipeline is the spine of the repo:

```
src/agentic_circuit (ACPy Python DSL + CLI)
  → ACIR dialect (lib/Dialect/ACIR, ops in include/acir/Dialect/ACIR/ACIROps.td)
  → pass pipeline (lib/Transforms, lib/Bindings, lib/Analysis)
  → ACSim construction IR (lib/Dialect/ACSim) via lib/Conversion/ACIRToACSim
  → generated C++20 (lib/CodeGen) → gfsim runtime (include/gfsim + lib/gfsim)
```

- **Python frontend** (`src/agentic_circuit/`): pure Python; entry point `_cli.py` with subcommands in `_commands/`, lowering in `_lower_acir.py`. Machine-readable JSON behavior is normative over human-readable output. `_native_api.py` loads the CMake-built `_native` CPython extension (`python/native/NativeModule.cpp`, wraps `lib/Compiler`) if it's on the path, so full tests need both `src` and `build/<preset>/python`.
- **Dialects**: ACIR (`ac` namespace, 59 ops: hierarchy, collections, protocols, processes, queues/event queues, trace, statistics) and ACSim (`acsim`, thin construction IR: C++ type specializations, construction order, bindings, process-state enums). Op spellings are normative contract — specs list exact syntax; tests verify positive and negative coverage per op/type.
- **Passes** (`lib/Transforms/`): `VerifyACIRFile` → `NormalizeACIRFile` → `ResolveBindings` → `FreezeTopology` → `VerifyModel` → `CanonicalizeModel` → `LowerProcessState`. `FreezeTopology` establishes the static-topology boundary — nothing may change topology after it.
- **Process-state analysis** (`lib/Analysis/ProcessState*`): computes identity, continuation, liveness, wake/cost, expansion, and the process-state plan consumed by codegen (`acir-process-state-plan` schema).
- **CodeGen** (`lib/CodeGen/`): `Generator`/`ProcessGenerator`/`Emitter` emit C++20 source; `Build`/`Manifest`/`Staging` publish artifacts. `tools/acir-cxxgen` compiles the generated model against the runtime headers. CMake copies `include/gfsim` into the build tree so generated code and the Python bridge never depend on source-tree paths.
- **gfsim** (`include/gfsim/`, `lib/gfsim/`): the pure C++ runtime model library (queue, packet, process, dispatch, harness, npu, trace, statistics, observation) that generated code statically specializes.
- **Test tools**: `tools/acir-opt` is the public CLI; `acir-opt-internal` is the test-only variant (extra flags). lit tests use `%acir_opt` (internal), `%acir_opt_public`, `%acir_cxxgen`, `%split_file`, `%not`, `%source_root`, `%binary_root`, `%python`.

## Contract discipline

- `docs/specs/*-v0.2.md` are the normative specifications; `schemas/*.json` are the canonical machine-readable contracts. Changing any public contract (op/type spelling, schema, manifest, pipeline artifact) requires updating the affected spec(s), schema(s), and tests in the same change (see `CONTRIBUTING.md`).
- `docs/implementation/spec-coverage.md` is generated by `scripts/check-ir-coverage.py --write-ledger` — never hand-edit it.
- Development history is organized in phases (plans/audits in `docs/superpowers/` and `docs/implementation/`); `examples/phase5/` holds end-to-end example architectures exercised by `tests/e2e/`.
