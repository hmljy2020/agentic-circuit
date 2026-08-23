// RUN: rm -rf %t.first %t.second %t.frozen %t.acsim
// RUN: %acir_opt_public --verify-each=false --pass-pipeline='builtin.module(ac-freeze-topology)' %source_root/test/Conversion/native-state-array.mlir -o %t.frozen
// RUN: %acir_opt_public --ac-lower-to-acsim --ac-binding-profile=fast --ac-binding-target=x86_64-linux-gnu %t.frozen -o %t.acsim
// RUN: for out in %t.first %t.second; do %acir_cxxgen %t.acsim --frozen-acir=%t.frozen --stop-after=compile --output-root=$out --project-name=native-state-array --project-identity=project.native-state-array --system-name=native_state_array --system-identity=system.native-state-array --profile=fast --compiler=%cxx --standard-library=libstdc++ --abi-mode=default --object-format=elf --contract-flag=-std=c++20 --include-root=%source_root/include || exit 1; done
// RUN: diff -r %t.first %t.second
// RUN: grep -R "gfsim::StateArray<std::int32_t>" %t.first/include/generated/modules
// RUN: grep -R "\.read(v0, v1)" %t.first/src/generated/processes
// RUN: grep -R "\.proposeWrite(v0, v4, v5, v1)" %t.first/src/generated/processes
// RUN: %not grep -R -E "provider|extern_wrapper" %t.first/include %t.first/src
