// RUN: %acir_opt_public %s | %FileCheck %s

builtin.module attributes {ac.contract_epoch = "0.2"} {
  ac.module @Top(i32) parameters {} graph {
  ^bb0(%arg0 : i32):
    ac.time_domain @core period 1 phase 0 scale 1
    ac.event_queue @events payload !ac.event<i32> capacity 2
        ordering "time_then_sequence" domain @core id "events" path "events"
    ac.process @producer kind "workload" captures(%arg0 : i32) {
    ^bb0(%value : i32):
      %delay = arith.constant 0 : i64
      %accepted = ac.schedule @events %value after %delay : i32
      ac.yield_sim
    }
    ac.process @consumer kind "control" {
      %value, %ready = ac.try_event @events : i32
      scf.if %ready {
      } else {
        ac.await_event @events
      }
      ac.yield_sim
    }
    ac.return
  }
}

// CHECK: %[[ACCEPTED:.+]] = ac.schedule @events
// CHECK: %[[VALUE:.+]], %[[READY:.+]] = ac.try_event @events : i32
// CHECK: scf.if %[[READY]]
// CHECK: ac.await_event @events
