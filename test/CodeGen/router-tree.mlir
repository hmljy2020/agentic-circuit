// RUN: rm -rf %t.first %t.second %t.frozen %t.acsim
// RUN: %acir_opt_public --verify-each=false --pass-pipeline='builtin.module(ac-verify-model,ac-canonicalize-model,ac-freeze-topology)' %source_root/examples/chao/noc/acir/router_tree/model.mlir -o %t.frozen
// RUN: %acir_opt_public --ac-lower-to-acsim --ac-binding-profile=fast --ac-binding-target=x86_64-linux-gnu %t.frozen -o %t.acsim
// RUN: for out in %t.first %t.second; do %acir_cxxgen %t.acsim --stop-after=compile --output-root=$out --project-name=router-tree --project-identity=project.router-tree --system-name=router_tree_demo --system-identity=system.router-tree-demo --profile=fast --compiler=%cxx --standard-library=libstdc++ --abi-mode=default --object-format=elf --contract-flag=-std=c++20 --include-root=%source_root/include || exit 1; done
// RUN: diff -r %t.first %t.second
// RUN: test $(find %t.first/src -type f -name '*.cpp' | wc -l) -ge 10
// RUN: test $(find %t.first/obj -type f -name '*.o' | wc -l) -ge 10
// RUN: grep -R "gfsim::Queue<std::int32_t>" %t.first/include
// RUN: grep -R "live00000000" %t.first/include %t.first/src
// RUN: test $(grep -R "\.tryPeek()" %t.first/src/generated/processes | wc -l) -ge 3
// RUN: %not grep -R -E "provider|binding_lock|extern_wrapper" %t.first/include %t.first/src

// The native router tree emits and compiles a model, eight process state
// machines, and their closed queue helpers without provider-side dependencies.
