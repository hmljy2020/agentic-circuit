// RUN: %acir_opt --verify-each=false --pass-pipeline='builtin.module(ac-freeze-topology)' %s -o %t.frozen
// RUN: %acir_opt --ac-lower-to-acsim --ac-binding-profile=fast --ac-binding-target=x86_64-linux-gnu %t.frozen | %FileCheck %s

builtin.module attributes {ac.contract_epoch = "0.2"} {
  ac.system @native_state_array root @Top as "root" tick 0 "cycle"
      workload @Top::@worker seed {kind = "fixed", value = 7 : i64}
      instrumentation [] results {id = "default", format = "json"} selected true
  ac.module @Top() parameters {} graph {
    ac.state_array @state element i32 entries 4 read_ports 1 write_ports 1
        ownership "exclusive" init "zero" id "state" path "state"
    ac.process @worker kind "workload" {
      %index = arith.constant 0 : i32
      %port = arith.constant 0 : i32
      %value = ac.state_read @state[%index] port %port : i32
      %one = arith.constant 1 : i32
      %next = arith.addi %value, %one : i32
      %enable = arith.constant true
      ac.state_write @state[%index] %next when %enable port %port : i32
      ac.yield_sim
    }
    ac.return
  }
}

// CHECK: acsim.type @acir_impl_state_read_{{[0-9a-f]+}}
// CHECK: acsim.type @acir_impl_state_write_{{[0-9a-f]+}}
// CHECK: acsim.type @acir_state_array_{{[0-9a-f]+}} cpp "gfsim::StateArray<std::int32_t>" kind "runtime_object"
// CHECK: acsim.instance @state target @acir_state_array_{{[0-9a-f]+}} args [4, 1, 1]
// CHECK: acsim.invoke @acir_impl_state_read_{{[0-9a-f]+}}
// CHECK: acsim.invoke @acir_impl_state_write_{{[0-9a-f]+}}
