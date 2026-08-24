// RUN: rm -rf %t.generated %t.frozen %t.acsim
// RUN: %acir_opt --verify-each=false --pass-pipeline='builtin.module(ac-freeze-topology)' %s -o %t.frozen
// RUN: %acir_opt --ac-lower-to-acsim --ac-binding-profile=fast --ac-binding-target=x86_64-linux-gnu %t.frozen -o %t.acsim
// RUN: %FileCheck %s < %t.acsim
// RUN: %acir_cxxgen %t.acsim --frozen-acir=%t.frozen --stop-after=compile --output-root=%t.generated --project-name=compact-loop-iter-args --project-identity=project.compact-loop-iter-args --system-name=compact_loop_iter_args --system-identity=system.compact-loop-iter-args --profile=fast --compiler=%cxx --standard-library=libstdc++ --abi-mode=default --object-format=elf --contract-flag=-std=c++20 --include-root=%source_root/include
// RUN: grep -R -F 'goto block_entry_b' %t.generated/src/generated/processes

builtin.module attributes {ac.contract_epoch = "0.2"} {
  func.func private @add(%lhs: i32, %rhs: i32) -> i32 {
    %sum = arith.addi %lhs, %rhs : i32
    return %sum : i32
  }
  func.func private @accumulate(%lhs: i32, %rhs: i32) -> i32 {
    %sum = func.call @add(%lhs, %rhs) : (i32, i32) -> i32
    return %sum : i32
  }
  ac.system @compact_loop_iter_args root @Top as "root" tick 0 "cycle"
      workload @Top::@worker seed {kind = "fixed", value = 7 : i64}
      instrumentation [] results {id = "default", format = "json"} selected true
  ac.module @Top() parameters {} graph {
    ac.state_array @state element i32 entries 1 read_ports 1 write_ports 1
        ownership "exclusive" init "zero" id "state" path "state"
    ac.process @worker kind "workload" {
      %lb = arith.constant 0 : index
      %ub = arith.constant 4 : index
      %step = arith.constant 1 : index
      %zero = arith.constant 0 : i32
      %enable = arith.constant true
      %sum = scf.for %i = %lb to %ub step %step
          iter_args(%acc = %zero) -> (i32) {
        %i32 = arith.index_cast %i : index to i32
        %next = func.call @accumulate(%acc, %i32) : (i32, i32) -> i32
        scf.yield %next : i32
      }
      %positive = arith.cmpi sgt, %sum, %zero : i32
      scf.if %positive {
        ac.state_write @state[%zero] %sum when %enable port %zero : i32
      }
      ac.yield_sim
    }
    ac.return
  }
}

// CHECK: attributes {bounded_local_backedges = array<i64:
// CHECK-COUNT-1: arith.addi
// CHECK: cf.br
// CHECK-COUNT-1: acsim.invoke @acir_impl_state_write_
