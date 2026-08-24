// RUN: rm -rf %t.generated %t.frozen %t.acsim
// RUN: %acir_opt --verify-each=false --pass-pipeline='builtin.module(ac-freeze-topology)' %s -o %t.frozen
// RUN: %acir_opt --ac-lower-to-acsim --ac-binding-profile=fast --ac-binding-target=x86_64-linux-gnu %t.frozen -o %t.acsim
// RUN: %FileCheck %s < %t.acsim
// RUN: %acir_cxxgen %t.acsim --frozen-acir=%t.frozen --stop-after=compile --output-root=%t.generated --project-name=native-state-array-loop --project-identity=project.native-state-array-loop --system-name=native_state_array_loop --system-identity=system.native-state-array-loop --profile=fast --compiler=%cxx --standard-library=libstdc++ --abi-mode=default --object-format=elf --contract-flag=-std=c++20 --include-root=%source_root/include
// RUN: test "$(grep -R -E '\.read\(|\.proposeWrite\(' %t.generated/src/generated/processes | wc -l)" -eq 2
// RUN: grep -R -F 'goto block_entry_b' %t.generated/src/generated/processes

builtin.module attributes {ac.contract_epoch = "0.2"} {
  ac.system @native_state_array_loop root @Top as "root" tick 0 "cycle"
      workload @Top::@worker seed {kind = "fixed", value = 7 : i64}
      instrumentation [] results {id = "default", format = "json"} selected true
  ac.module @Top() parameters {} graph {
    ac.state_array @state element i32 entries 4 read_ports 4 write_ports 4
        ownership "exclusive" init "zero" id "state" path "state"
    ac.process @worker kind "workload" {
      %lb = arith.constant 0 : index
      %ub = arith.constant 4 : index
      %step = arith.constant 1 : index
      %one = arith.constant 1 : i32
      %enable = arith.constant true
      scf.for %i = %lb to %ub step %step {
        %i32 = arith.index_cast %i : index to i32
        %old = ac.state_read @state[%i32] port %i32 : i32
        %next = arith.addi %old, %one : i32
        ac.state_write @state[%i32] %next when %enable port %i32 : i32
      }
      ac.yield_sim
    }
    ac.return
  }
}

// A static loop remains one same-tick CFG cycle.  Its two StateArray helper
// call sites must not be copied once per trip-count iteration.
// CHECK: attributes {bounded_local_backedges = array<i64:
// CHECK-COUNT-2: acsim.invoke @acir_impl_state_
// CHECK: cf.br
