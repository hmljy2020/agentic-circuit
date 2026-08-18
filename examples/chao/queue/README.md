# Native `ac.queue` ACIR example

`queue.ac.mlir` contains a capacity-one native FIFO shared by two processes.
The producer repeatedly proposes the value `10`; the consumer repeatedly pops
the FIFO. Failed sends wait for `writable`, and failed receives wait for
`readable`.

The checked run uses a six-tick cap because this example intentionally models
continuously running processes. Its expected queue statistics are:

- accepted transactions: 2
- completed transactions: 1
- peak occupancy: 1
- final occupancy: 1

Build and run the complete ACIR → ACSim → C++ pipeline with:

```sh
examples/chao/queue/build-run.sh
```

The script rebuilds `examples/chao/queue/build` and keeps the frozen ACIR,
lowered ACSim, generated C++, object files, and binaries there after the run.
`queue.frozen.mlir` and `queue.acsim.mlir` at the example root remain checked-in
snapshots for inspection.

The compilation stages used to produce them were:

```sh
build/dev-llvm22/bin/acir-opt --verify-each=false \
  --pass-pipeline='builtin.module(ac-freeze-topology)' \
  examples/chao/queue/queue.ac.mlir \
  -o examples/chao/queue/build/queue.frozen.mlir

build/dev-llvm22/bin/acir-opt --ac-lower-to-acsim \
  --ac-binding-profile=fast --ac-binding-target=x86_64-linux-gnu \
  examples/chao/queue/build/queue.frozen.mlir \
  -o examples/chao/queue/build/queue.acsim.mlir

build/dev-llvm22/bin/acir-cxxgen \
  examples/chao/queue/build/queue.acsim.mlir \
  --stop-after=link --output-root=examples/chao/queue/build/generated \
  --project-name=chao-queue --project-identity=project.chao.queue \
  --system-name=queue_demo --system-identity=system.queue_demo \
  --profile=fast --compiler=/usr/bin/c++ --standard-library=libstdc++ \
  --abi-mode=default --object-format=elf --contract-flag=-std=c++20 \
  --include-root=/home/lc/AC/agentic-circuit/include \
  --link-input=/home/lc/AC/agentic-circuit/build/dev-llvm22/lib/gfsim/libgfsim.a \
  --link-input=/home/lc/AC/agentic-circuit/build/dev-llvm22/lib/Bindings/libACIRBindings.a \
  --linker-flag=-L/usr/lib/llvm-22/lib --linker-flag=-lLLVM
```

`runner.cpp` links against the generated model objects, applies `maxTicks=6`,
prints the native queue statistics, and returns nonzero if any expected value
does not match.
