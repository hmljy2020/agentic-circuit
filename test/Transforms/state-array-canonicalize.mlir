// RUN: %acir_opt --pass-pipeline='builtin.module(canonicalize)' %s | %FileCheck %s

builtin.module attributes {ac.contract_epoch = "0.2"} {
  ac.system @state_array_canonicalize root @Top as "root" tick 0 "cycle"
      workload @Top::@worker seed {kind = "fixed", value = 7 : i64}
      instrumentation [] results {id = "default", format = "json"} selected true
  ac.module @Top() parameters {} graph {
    ac.state_array @state element i32 entries 1 read_ports 1 write_ports 1
        ownership "exclusive" init "zero" id "state" path "state"
    ac.process @worker kind "workload" {
      %zero = arith.constant 0 : i32
      %false = arith.constant false
      %true = arith.constant true
      %first = ac.state_read @state[%zero] port %zero : i32
      ac.state_write @state[%zero] %zero when %false port %zero : i32
      %second = ac.state_read @state[%zero] port %zero : i32
      %sum = arith.addi %first, %second : i32
      ac.state_write @state[%zero] %sum when %true port %zero : i32
      ac.yield_sim
    }
    ac.return
  }
}

// CHECK-COUNT-1: ac.state_read
// CHECK: arith.addi %[[READ:.+]], %[[READ]]
// CHECK-COUNT-1: ac.state_write
// CHECK: ac.yield_sim
