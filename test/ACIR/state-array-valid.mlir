// RUN: %acir_opt %s | %FileCheck %s

builtin.module attributes {ac.contract_epoch = "0.2"} {
  ac.system @state_array_valid root @Top as "root" tick 0 "cycle"
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

// CHECK: ac.state_array @state element i32 entries 4 read_ports 1 write_ports 1
// CHECK: %{{.+}} = ac.state_read @state[%{{.+}}] port %{{.+}} : i32
// CHECK: ac.state_write @state[%{{.+}}] %{{.+}} when %{{.+}} port %{{.+}} : i32
