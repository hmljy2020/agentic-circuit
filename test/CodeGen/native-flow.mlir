// RUN: rm -rf %t.native-flow-out
// RUN: %acir_opt_public --verify-each=false --pass-pipeline='builtin.module(ac-freeze-topology)' %source_root/test/Transforms/flow-connections.mlir -o %t.frozen
// RUN: %acir_opt_public --ac-lower-to-acsim --ac-binding-profile=fast --ac-binding-target=x86_64-linux-gnu %t.frozen -o %t.acsim
// RUN: %acir_cxxgen %t.acsim --frozen-acir=%t.frozen --stop-after=compile --output-root=%t.native-flow-out --project-name=native-flow --project-identity=project.native-flow --system-name=soc --system-identity=system.soc --profile=fast --compiler=%cxx --standard-library=libstdc++ --abi-mode=default --object-format=elf --contract-flag=-std=c++20 --include-root=%source_root/include | %FileCheck %s
// RUN: grep -R "gfsim::QueueLink<std::int32_t>" %t.native-flow-out/include/generated/modules
// RUN: grep -R "producer_\.flow_output_00000000(), consumer_\.flow_input_00000000()" %t.native-flow-out/src/generated/modules
// RUN: grep -R "\.proposePush(" %t.native-flow-out/src/generated/processes
// RUN: grep -R "\.tryRecv()" %t.native-flow-out/src/generated/processes
// RUN: %not grep -R "bindStatic" %t.native-flow-out/src/generated/modules/Top_*.cpp
// RUN: %not grep -R -E "extern_wrapper|flow_provider" %t.native-flow-out/include %t.native-flow-out/src

// CHECK: stage=compile status=passed

// This test intentionally consumes the canonical scalar Flow fixture above:
// ACIR -> ACSim -> ModelPlan -> generated C++ -> one-file-at-a-time compile.
