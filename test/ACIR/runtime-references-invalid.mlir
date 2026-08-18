// RUN: %split_file %s %t
// RUN: %not %acir_opt %t/unresolved-send.mlir 2>&1 | %FileCheck %s --check-prefix=UNRESOLVED-SEND
// RUN: %not %acir_opt %t/wrong-send-kind.mlir 2>&1 | %FileCheck %s --check-prefix=SEND-KIND
// RUN: %not %acir_opt %t/unresolved-schedule.mlir 2>&1 | %FileCheck %s --check-prefix=UNRESOLVED-SCHEDULE
// RUN: %not %acir_opt %t/unresolved-wait.mlir 2>&1 | %FileCheck %s --check-prefix=UNRESOLVED-WAIT
// RUN: %not %acir_opt %t/unresolved-event.mlir 2>&1 | %FileCheck %s --check-prefix=UNRESOLVED-EVENT
// RUN: %not %acir_opt %t/unresolved-probe.mlir 2>&1 | %FileCheck %s --check-prefix=UNRESOLVED-PROBE
// RUN: %not %acir_opt %t/unresolved-stat.mlir 2>&1 | %FileCheck %s --check-prefix=UNRESOLVED-STAT
// RUN: %not %acir_opt %t/schedule-type.mlir 2>&1 | %FileCheck %s --check-prefix=SCHEDULE-TYPE
// RUN: %not %acir_opt %t/probe-kind.mlir 2>&1 | %FileCheck %s --check-prefix=PROBE-KIND
// RUN: %not %acir_opt %t/stat-kind.mlir 2>&1 | %FileCheck %s --check-prefix=STAT-KIND

//--- unresolved-send.mlir
builtin.module attributes {ac.contract_epoch = "0.2"} {
  ac.module @M() parameters {} graph {
    ac.process @p kind "control" {
      %v = arith.constant 1 : i32
      %ok = ac.try_send @missing %v : i32
      ac.yield_sim
    }
    ac.return
  }
}
// UNRESOLVED-SEND: unresolved runtime target '@missing'

//--- wrong-send-kind.mlir
builtin.module attributes {ac.contract_epoch = "0.2"} {
  ac.module @M() parameters {} graph {
    ac.stat @not_a_queue kind "counter"
    ac.process @p kind "control" {
      %v = arith.constant 1 : i32
      %ok = ac.try_send @not_a_queue %v : i32
      ac.yield_sim
    }
    ac.return
  }
}
// SEND-KIND: runtime target '@not_a_queue' must resolve to ac.queue

//--- unresolved-schedule.mlir
builtin.module attributes {ac.contract_epoch = "0.2"} {
  ac.module @M() parameters {} graph {
    ac.process @p kind "control" {
      %v = arith.constant 1 : i32
      %delay = arith.constant 1 : i64
      %accepted = ac.schedule @missing %v after %delay : i32
      ac.yield_sim
    }
    ac.return
  }
}
// UNRESOLVED-SCHEDULE: unresolved runtime target '@missing'

//--- unresolved-wait.mlir
builtin.module attributes {ac.contract_epoch = "0.2"} {
  ac.module @M() parameters {} graph {
    ac.process @p kind "control" {
      ac.wait_for @missing
      ac.yield_sim
    }
    ac.return
  }
}
// UNRESOLVED-WAIT: unresolved runtime target '@missing'

//--- unresolved-event.mlir
builtin.module attributes {ac.contract_epoch = "0.2"} {
  ac.module @M() parameters {} graph {
    ac.process @p kind "control" {
      %value, %ready = ac.try_event @missing : i32
      scf.if %ready {
      } else {
        ac.await_event @missing
      }
      ac.yield_sim
    }
    ac.return
  }
}
// UNRESOLVED-EVENT: unresolved runtime target '@missing'

//--- unresolved-probe.mlir
builtin.module attributes {ac.contract_epoch = "0.2"} {
  ac.module @M() parameters {} graph {
    ac.process @p kind "monitor" {
      %v = ac.probe @missing kind "queue" : i64
      ac.yield_sim
    }
    ac.return
  }
}
// UNRESOLVED-PROBE: unresolved runtime target '@missing'

//--- unresolved-stat.mlir
builtin.module attributes {ac.contract_epoch = "0.2"} {
  ac.module @M() parameters {} graph {
    ac.process @p kind "monitor" {
      %v = arith.constant 1 : i64
      ac.stat.add @missing %v : i64
      ac.yield_sim
    }
    ac.return
  }
}
// UNRESOLVED-STAT: unresolved runtime target '@missing'

//--- schedule-type.mlir
builtin.module attributes {ac.contract_epoch = "0.2"} {
  ac.module @M() parameters {} graph {
    ac.time_domain @core period 1 phase 0 scale 1
    ac.event_queue @events payload !ac.event<i64> capacity 2
        ordering "time_then_sequence" domain @core id "events" path "events"
    ac.process @p kind "control" {
      %v = arith.constant 1 : i32
      %delay = arith.constant 1 : i64
      %accepted = ac.schedule @events %v after %delay : i32
      ac.yield_sim
    }
    ac.return
  }
}
// SCHEDULE-TYPE: does not match event queue element type {{.*}}i64

//--- probe-kind.mlir
builtin.module attributes {ac.contract_epoch = "0.2"} {
  ac.module @M() parameters {} graph {
    ac.stat @state kind "counter"
    ac.process @p kind "monitor" {
      %v = ac.probe @state kind "queue" : i64
      ac.yield_sim
    }
    ac.return
  }
}
// PROBE-KIND: runtime target '@state' must resolve to ac.queue

//--- stat-kind.mlir
builtin.module attributes {ac.contract_epoch = "0.2"} {
  ac.module @M() parameters {} graph {
    ac.process @target kind "monitor" { ac.yield_sim }
    ac.process @p kind "monitor" {
      %v = arith.constant 1 : i64
      ac.stat.add @target %v : i64
      ac.yield_sim
    }
    ac.return
  }
}
// STAT-KIND: runtime target '@target' must resolve to ac.stat
