// RUN: %split_file %s %t
// RUN: %not %acir_opt %t/outside.mlir 2>&1 | %FileCheck %s --check-prefix=OUTSIDE
// RUN: %not %acir_opt %t/mode.mlir 2>&1 | %FileCheck %s --check-prefix=MODE
// RUN: %not %acir_opt %t/wrong-queue.mlir 2>&1 | %FileCheck %s --check-prefix=QUEUE
// RUN: %not %acir_opt %t/success-branch.mlir 2>&1 | %FileCheck %s --check-prefix=BRANCH

//--- outside.mlir
builtin.module attributes {ac.contract_epoch = "0.2"} {
  ac.module @M() parameters {} graph {
    "ac.await_queue"() <{queue = @q, until = "readable"}> : () -> ()
    ac.return
  }
}
// OUTSIDE: operation is not legal in an ac.module structural Graph region

//--- mode.mlir
builtin.module attributes {ac.contract_epoch = "0.2"} {
  ac.module @M() parameters {} graph {
    ac.process @p kind "control" {
      "ac.await_queue"() <{queue = @q, until = "empty"}> : () -> ()
      ac.yield_sim
    }
    ac.return
  }
}
// MODE: until must be exactly 'readable' or 'writable'

//--- wrong-queue.mlir
builtin.module attributes {ac.contract_epoch = "0.2"} {
  ac.protocol @p {
    ac.role @s dual @r cardinality "exclusive"
    ac.role @r dual @s cardinality "exclusive"
    ac.state @idle initial true terminal false
    ac.state @done initial false terminal true
    ac.event @push from @s to @r payload i32 action "offer"
    ac.transition from @idle to @done on @push transfer true retain false guard {}
  }
  ac.module @M(i32) parameters {} graph {
  ^bb0(%value : i32):
    "ac.queue"() <{sym_name = "q0", stable_id = "q0", path = "q0", payload = i32, entry_capacity = 1 : i64, ordering = "fifo", protocol = @p, ownership = "exclusive", delay_ticks = 1 : i64}> : () -> ()
    "ac.queue"() <{sym_name = "q1", stable_id = "q1", path = "q1", payload = i32, entry_capacity = 1 : i64, ordering = "fifo", protocol = @p, ownership = "exclusive", delay_ticks = 1 : i64}> : () -> ()
    ac.process @worker kind "control" captures(%value : i32) {
    ^bb0(%captured : i32):
      %accepted = ac.try_send @q0 %captured : i32
      scf.if %accepted {
      } else {
        ac.await_queue @q1 until "writable"
      }
      ac.yield_sim
    }
    ac.return
  }
}
// QUEUE: must be in the false branch of the matching ac.try_send for queue '@q1'

//--- success-branch.mlir
builtin.module attributes {ac.contract_epoch = "0.2"} {
  ac.protocol @p {
    ac.role @s dual @r cardinality "exclusive"
    ac.role @r dual @s cardinality "exclusive"
    ac.state @idle initial true terminal false
    ac.state @done initial false terminal true
    ac.event @push from @s to @r payload i32 action "offer"
    ac.transition from @idle to @done on @push transfer true retain false guard {}
  }
  ac.module @M() parameters {} graph {
    "ac.queue"() <{sym_name = "q", stable_id = "q", path = "q", payload = i32, entry_capacity = 1 : i64, ordering = "fifo", protocol = @p, ownership = "exclusive", delay_ticks = 1 : i64}> : () -> ()
    ac.process @worker kind "control" {
      %value, %received = ac.try_recv @q : i32
      scf.if %received {
        ac.await_queue @q until "readable"
      }
      ac.yield_sim
    }
    ac.return
  }
}
// BRANCH: must be in the false branch of the matching ac.try_recv for queue '@q'
