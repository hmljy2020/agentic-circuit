// RUN: %python %S/Inputs/arbitrate-scale.py generate %t.input.mlir --count 256
// RUN: %acir_opt_public --verify-each=false --pass-pipeline='builtin.module(ac-freeze-topology)' %t.input.mlir -o %t.frozen.mlir
// RUN: %acir_opt_public --ac-lower-to-acsim --ac-binding-profile=fast --ac-binding-target=arm64-apple-darwin %t.frozen.mlir -o %t.acsim.mlir
// RUN: %python %S/Inputs/arbitrate-scale.py check %t.acsim.mlir --count 256

// The generated fixture has 256 candidates and 512 resource uses.  Its checker
// enforces a structural linear bound without relying on wall-clock timing.
