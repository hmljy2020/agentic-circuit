// RUN: %split_file %s %t
// RUN: %not %acir_opt_public %t/wrong-target.mlir 2>&1 | %FileCheck %s --check-prefix=TARGET
// RUN: %not %acir_opt_public %t/wrong-branch.mlir 2>&1 | %FileCheck %s --check-prefix=BRANCH
// RUN: %not %acir_opt_public %t/multi-consumer.mlir 2>&1 | %FileCheck %s --check-prefix=CONSUMER
// RUN: %not %acir_opt_public %t/negative-delay.mlir 2>&1 | %FileCheck %s --check-prefix=NEGATIVE
// RUN: %not %acir_opt_public %t/try-type.mlir 2>&1 | %FileCheck %s --check-prefix=TYPE
// RUN: %not %acir_opt_public %t/wrong-queue.mlir 2>&1 | %FileCheck %s --check-prefix=QUEUE
// RUN: %not %acir_opt_public %t/monitor.mlir 2>&1 | %FileCheck %s --check-prefix=MONITOR

//--- wrong-target.mlir
builtin.module attributes {ac.contract_epoch = "0.2"} {
  ac.module @M() parameters {} graph {
    ac.process @target kind "workload" { ac.yield_sim }
    ac.process @p kind "control" {
      %v = arith.constant 1 : i32
      %d = arith.constant 1 : i64
      %accepted = ac.schedule @target %v after %d : i32
      ac.yield_sim
    }
    ac.return
  }
}
// TARGET: runtime target '@target' must resolve to ac.event_queue

//--- wrong-branch.mlir
builtin.module attributes {ac.contract_epoch = "0.2"} {
  ac.module @M() parameters {} graph {
    ac.time_domain @core period 1 phase 0 scale 1
    ac.event_queue @events payload !ac.event<i32> capacity 2 ordering "time_then_sequence" domain @core id "events" path "events"
    ac.process @p kind "control" {
      %v, %ready = ac.try_event @events : i32
      ac.await_event @events
      ac.yield_sim
    }
    ac.return
  }
}
// BRANCH: must be in the false branch of the matching ac.try_event

//--- multi-consumer.mlir
builtin.module attributes {ac.contract_epoch = "0.2"} {
  ac.module @M() parameters {} graph {
    ac.time_domain @core period 1 phase 0 scale 1
    ac.event_queue @events payload !ac.event<i32> capacity 2 ordering "time_then_sequence" domain @core id "events" path "events"
    ac.process @p0 kind "control" {
      %v0, %r0 = ac.try_event @events : i32
      ac.yield_sim
    }
    ac.process @p1 kind "control" {
      %v1, %r1 = ac.try_event @events : i32
      ac.yield_sim
    }
    ac.return
  }
}
// CONSUMER: may be consumed by only one process

//--- negative-delay.mlir
builtin.module attributes {ac.contract_epoch = "0.2"} {
  ac.module @M() parameters {} graph {
    ac.time_domain @core period 1 phase 0 scale 1
    ac.event_queue @events payload !ac.event<i32> capacity 2 ordering "time_then_sequence" domain @core id "events" path "events"
    ac.process @p kind "control" {
      %v = arith.constant 1 : i32
      %d = arith.constant -1 : i64
      %accepted = ac.schedule @events %v after %d : i32
      ac.yield_sim
    }
    ac.return
  }
}
// NEGATIVE: schedule delay must be non-negative

//--- try-type.mlir
builtin.module attributes {ac.contract_epoch = "0.2"} {
  ac.module @M() parameters {} graph {
    ac.time_domain @core period 1 phase 0 scale 1
    ac.event_queue @events payload !ac.event<i64> capacity 2 ordering "time_then_sequence" domain @core id "events" path "events"
    ac.process @p kind "control" {
      %v, %ready = ac.try_event @events : i32
      ac.yield_sim
    }
    ac.return
  }
}
// TYPE: result type 'i32' does not match event queue element type 'i64'

//--- wrong-queue.mlir
builtin.module attributes {ac.contract_epoch = "0.2"} {
  ac.module @M() parameters {} graph {
    ac.time_domain @core period 1 phase 0 scale 1
    ac.event_queue @first payload !ac.event<i32> capacity 2 ordering "time_then_sequence" domain @core id "first" path "first"
    ac.event_queue @second payload !ac.event<i32> capacity 2 ordering "time_then_sequence" domain @core id "second" path "second"
    ac.process @p kind "control" {
      %v, %ready = ac.try_event @first : i32
      scf.if %ready {
      } else {
        ac.await_event @second
      }
      ac.yield_sim
    }
    ac.return
  }
}
// QUEUE: must be in the false branch of the matching ac.try_event for event queue '@second'

//--- monitor.mlir
builtin.module attributes {ac.contract_epoch = "0.2"} {
  ac.module @M() parameters {} graph {
    ac.time_domain @core period 1 phase 0 scale 1
    ac.event_queue @events payload !ac.event<i32> capacity 2 ordering "time_then_sequence" domain @core id "events" path "events"
    ac.process @p kind "monitor" {
      %v, %ready = ac.try_event @events : i32
      ac.yield_sim
    }
    ac.return
  }
}
// MONITOR: monitor process cannot perform functional state effects
