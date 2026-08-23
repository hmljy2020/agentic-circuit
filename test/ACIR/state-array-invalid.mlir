// RUN: %split_file %s %t
// RUN: %not %acir_opt_public %t/zero-entries.mlir 2>&1 | %FileCheck %s --check-prefix=ENTRIES
// RUN: %not %acir_opt_public %t/wrong-target.mlir 2>&1 | %FileCheck %s --check-prefix=TARGET
// RUN: %not %acir_opt_public %t/wrong-type.mlir 2>&1 | %FileCheck %s --check-prefix=TYPE
// RUN: %not %acir_opt_public %t/bad-port.mlir 2>&1 | %FileCheck %s --check-prefix=PORT
// RUN: %not %acir_opt_public %t/dynamic-port.mlir 2>&1 | %FileCheck %s --check-prefix=DYNAMIC
// RUN: %not %acir_opt_public %t/monitor-write.mlir 2>&1 | %FileCheck %s --check-prefix=MONITOR

//--- zero-entries.mlir
builtin.module attributes {ac.contract_epoch = "0.2"} {
  ac.module @M() parameters {} graph {
    ac.state_array @s element i32 entries 0 read_ports 1 write_ports 1 ownership "exclusive" init "zero" id "s" path "s"
    ac.return
  }
}
// ENTRIES: entry count must be positive

//--- wrong-target.mlir
builtin.module attributes {ac.contract_epoch = "0.2"} {
  ac.module @M() parameters {} graph {
    ac.process @s kind "control" { ac.yield_sim }
    ac.process @p kind "control" {
      %i = arith.constant 0 : i32
      %v = ac.state_read @s[%i] port %i : i32
      ac.yield_sim
    }
    ac.return
  }
}
// TARGET: runtime target '@s' must resolve to ac.state_array

//--- wrong-type.mlir
builtin.module attributes {ac.contract_epoch = "0.2"} {
  ac.module @M() parameters {} graph {
    ac.state_array @s element i32 entries 1 read_ports 1 write_ports 1 ownership "exclusive" init "zero" id "s" path "s"
    ac.process @p kind "control" {
      %i = arith.constant 0 : i32
      %v = ac.state_read @s[%i] port %i : i64
      ac.yield_sim
    }
    ac.return
  }
}
// TYPE: result type 'i64' does not match state array element type 'i32'

//--- bad-port.mlir
builtin.module attributes {ac.contract_epoch = "0.2"} {
  ac.module @M() parameters {} graph {
    ac.state_array @s element i32 entries 1 read_ports 1 write_ports 1 ownership "exclusive" init "zero" id "s" path "s"
    ac.process @p kind "control" {
      %i = arith.constant 0 : i32
      %port = arith.constant 1 : i32
      %v = ac.state_read @s[%i] port %port : i32
      ac.yield_sim
    }
    ac.return
  }
}
// PORT: port must be a constant in declared read port range

//--- dynamic-port.mlir
builtin.module attributes {ac.contract_epoch = "0.2"} {
  ac.module @M() parameters {} graph {
    ac.state_array @s element i32 entries 1 read_ports 1 write_ports 1 ownership "exclusive" init "zero" id "s" path "s"
    ac.process @p kind "control" {
      %i = arith.constant 0 : i32
      %v = ac.state_read @s[%i] port %i : i32
      %one = arith.constant 1 : i32
      %dynamic = arith.addi %v, %one : i32
      %v2 = ac.state_read @s[%i] port %dynamic : i32
      ac.yield_sim
    }
    ac.return
  }
}
// DYNAMIC: port must be a constant in declared read port range

//--- monitor-write.mlir
builtin.module attributes {ac.contract_epoch = "0.2"} {
  ac.module @M() parameters {} graph {
    ac.state_array @s element i32 entries 1 read_ports 1 write_ports 1 ownership "exclusive" init "zero" id "s" path "s"
    ac.process @p kind "monitor" {
      %i = arith.constant 0 : i32
      %enable = arith.constant true
      ac.state_write @s[%i] %i when %enable port %i : i32
      ac.yield_sim
    }
    ac.return
  }
}
// MONITOR: monitor process cannot perform functional state effects
