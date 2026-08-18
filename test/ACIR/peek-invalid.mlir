// RUN: %split_file %s %t
// RUN: %not %acir_opt %t/outside.mlir 2>&1 | %FileCheck %s --check-prefix=OUTSIDE
// RUN: %not %acir_opt --pass-pipeline='builtin.module(ac-verify-model)' %t/missing.mlir 2>&1 | %FileCheck %s --check-prefix=MISSING
// RUN: %not %acir_opt --pass-pipeline='builtin.module(ac-verify-model)' %t/not-queue.mlir 2>&1 | %FileCheck %s --check-prefix=NOT-QUEUE
// RUN: %not %acir_opt --pass-pipeline='builtin.module(ac-verify-model)' %t/type.mlir 2>&1 | %FileCheck %s --check-prefix=TYPE
// RUN: %not %acir_opt %t/writable.mlir 2>&1 | %FileCheck %s --check-prefix=WRITABLE
// RUN: %not %acir_opt %t/wrong-queue.mlir 2>&1 | %FileCheck %s --check-prefix=QUEUE
// RUN: %not %acir_opt %t/true-branch.mlir 2>&1 | %FileCheck %s --check-prefix=BRANCH

//--- outside.mlir
builtin.module attributes {ac.contract_epoch = "0.2"} {
  ac.module @M() parameters {} graph {
    "ac.peek"() <{queue = @q}> : () -> (i32, i1)
    ac.return
  }
}
// OUTSIDE: operation is not legal in an ac.module structural Graph region

//--- missing.mlir
builtin.module attributes {ac.contract_epoch = "0.2"} {
  ac.module @M() parameters {} graph {
    ac.process @p kind "monitor" {
      %value, %valid = ac.peek @missing : i32
      ac.yield_sim
    }
    ac.return
  }
}
// MISSING: unresolved runtime target '@missing'

//--- not-queue.mlir
builtin.module attributes {ac.contract_epoch = "0.2"} {
  ac.module @M() parameters {} graph {
    ac.stat @target kind "counter"
    ac.process @p kind "monitor" {
      %value, %valid = ac.peek @target : i32
      ac.yield_sim
    }
    ac.return
  }
}
// NOT-QUEUE: runtime target '@target' must resolve to ac.queue

//--- type.mlir
builtin.module attributes {ac.contract_epoch = "0.2"} {
  ac.protocol @fifo {
    ac.role @sender dual @receiver cardinality "exclusive"
    ac.role @receiver dual @sender cardinality "exclusive"
    ac.state @idle initial true terminal false
    ac.event @push from @sender to @receiver payload i32 action "offer"
    ac.transition from @idle to @idle on @push transfer true retain false guard {}
  }
  ac.module @M() parameters {} graph {
    ac.queue @q payload i32 entries 1 ordering "fifo" protocol @fifo
        ownership "exclusive" id "q" path "q"
    ac.process @p kind "monitor" {
      %value, %valid = ac.peek @q : i64
      ac.yield_sim
    }
    ac.return
  }
}
// TYPE: result type 'i64' does not match queue payload type 'i32'

//--- writable.mlir
builtin.module attributes {ac.contract_epoch = "0.2"} {
  ac.module @M() parameters {} graph {
    ac.process @p kind "control" {
      %value, %valid = ac.peek @q : i32
      scf.if %valid {
      } else {
        ac.await_queue @q until "writable"
      }
      ac.yield_sim
    }
    ac.return
  }
}
// WRITABLE: must be in the false branch of the matching ac.try_send

//--- wrong-queue.mlir
builtin.module attributes {ac.contract_epoch = "0.2"} {
  ac.module @M() parameters {} graph {
    ac.process @p kind "control" {
      %value, %valid = ac.peek @q0 : i32
      scf.if %valid {
      } else {
        ac.await_queue @q1 until "readable"
      }
      ac.yield_sim
    }
    ac.return
  }
}
// QUEUE: must be in the false branch of the matching ac.try_recv or ac.peek for queue '@q1'

//--- true-branch.mlir
builtin.module attributes {ac.contract_epoch = "0.2"} {
  ac.module @M() parameters {} graph {
    ac.process @p kind "control" {
      %value, %valid = ac.peek @q : i32
      scf.if %valid {
        ac.await_queue @q until "readable"
      }
      ac.yield_sim
    }
    ac.return
  }
}
// BRANCH: must be in the false branch of the matching ac.try_recv or ac.peek for queue '@q'
