// RUN: %split_file %s %t
// RUN: %not %acir_opt %t/outside.mlir 2>&1 | %FileCheck %s --check-prefix=OUTSIDE
// RUN: %not %acir_opt --pass-pipeline='builtin.module(ac-verify-model)' %t/missing.mlir 2>&1 | %FileCheck %s --check-prefix=MISSING
// RUN: %not %acir_opt --pass-pipeline='builtin.module(ac-verify-model)' %t/not-queue.mlir 2>&1 | %FileCheck %s --check-prefix=NOT-QUEUE
// RUN: %not %acir_opt --pass-pipeline='builtin.module(ac-verify-model)' %t/event-queue.mlir 2>&1 | %FileCheck %s --check-prefix=EVENT-QUEUE

//--- outside.mlir
builtin.module attributes {ac.contract_epoch = "0.2"} {
  ac.module @M() parameters {} graph {
    "ac.space"() <{queue = @q}> : () -> (i32)
    ac.return
  }
}
// OUTSIDE: operation is not legal in an ac.module structural Graph region

//--- missing.mlir
builtin.module attributes {ac.contract_epoch = "0.2"} {
  ac.module @M() parameters {} graph {
    ac.process @p kind "monitor" {
      %space = ac.space @missing
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
      %space = ac.space @target
      ac.yield_sim
    }
    ac.return
  }
}
// NOT-QUEUE: runtime target '@target' must resolve to ac.queue

//--- event-queue.mlir
builtin.module attributes {ac.contract_epoch = "0.2"} {
  ac.module @M() parameters {} graph {
    ac.time_domain @core period 1 phase 0 scale 1
    ac.event_queue @done payload !ac.event<i32> capacity 8
        ordering "time_then_sequence" domain @core id "done" path "done"
    ac.process @p kind "monitor" {
      %space = ac.space @done
      ac.yield_sim
    }
    ac.return
  }
}
// EVENT-QUEUE: runtime target '@done' must resolve to ac.queue
