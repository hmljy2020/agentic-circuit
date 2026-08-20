// RUN: rm -rf %t.out %t.frozen %t.acsim
// RUN: %acir_opt_public --verify-each=false --pass-pipeline='builtin.module(ac-freeze-topology)' %source_root/test/Conversion/arbitrate.mlir -o %t.frozen
// RUN: %acir_opt_public --ac-lower-to-acsim --ac-binding-profile=fast --ac-binding-target=x86_64-linux-gnu %t.frozen -o %t.acsim
// RUN: %acir_cxxgen %t.acsim --stop-after=compile --output-root=%t.out --project-name=arbitrate --project-identity=project.arbitrate --system-name=soc --system-identity=system.soc --profile=fast --compiler=%cxx --standard-library=libstdc++ --abi-mode=default --object-format=elf --contract-flag=-std=c++20 --include-root=%source_root/include | %FileCheck %s
// RUN: grep -R "tryTransferTo(" %t.out/src/generated/processes
// RUN: grep -R -E "auto .* = \(.* (\&|\||\^) .*\);" %t.out/src/generated/processes
// RUN: %not grep -R -E "arbiter|arbitrate|unordered_map|std::vector|for \(|while \(|malloc|operator new" %t.out/src/generated/processes

// CHECK: stage=compile status=passed
