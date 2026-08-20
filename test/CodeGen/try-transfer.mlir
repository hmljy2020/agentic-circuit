// RUN: rm -rf %t.out %t.frozen %t.acsim
// RUN: %acir_opt_public --verify-each=false --pass-pipeline='builtin.module(ac-freeze-topology)' %source_root/test/Conversion/try-transfer.mlir -o %t.frozen
// RUN: %acir_opt_public --ac-lower-to-acsim --ac-binding-profile=fast --ac-binding-target=x86_64-linux-gnu %t.frozen -o %t.acsim
// RUN: %acir_cxxgen %t.acsim --stop-after=model-plan | %FileCheck %s --check-prefix=PLAN
// RUN: %acir_cxxgen %t.acsim --stop-after=compile --output-root=%t.out --project-name=try-transfer --project-identity=project.try-transfer --system-name=soc --system-identity=system.soc --profile=fast --compiler=%cxx --standard-library=libstdc++ --abi-mode=default --object-format=elf --contract-flag=-std=c++20 --include-root=%source_root/include | %FileCheck %s --check-prefix=COMPILE
// RUN: grep -R "\.tryTransferTo(" %t.out/src/generated/processes
// RUN: %not grep -R -E "extern_wrapper|provider_wrapper|bindStatic" %t.out/include %t.out/src

// PLAN: stage=model-plan status=passed
// COMPILE: stage=compile status=passed
