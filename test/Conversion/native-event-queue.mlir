// RUN: %acir_opt_public --verify-each=false --pass-pipeline='builtin.module(ac-freeze-topology)' %s -o %t.frozen
// RUN: %acir_opt_public --ac-lower-to-acsim --ac-binding-profile=fast --ac-binding-target=x86_64-linux-gnu %t.frozen | %FileCheck %s

builtin.module attributes {ac.contract_epoch = "0.2"} {
  ac.system @soc root @Top as "root" tick 0 "cycle"
      workload @Top::@producer seed {kind = "fixed", value = 7 : i64}
      instrumentation [] results {id = "default", format = "json"} selected true
  ac.module @Top() parameters {} graph {
    ac.time_domain @core period 1 phase 0 scale 1
    ac.event_queue @events payload !ac.event<i32> capacity 2
        ordering "time_then_sequence" domain @core id "events" path "events"
    ac.process @producer kind "workload" {
      %value = arith.constant 7 : i32
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

// CHECK: acsim.type @acir_event_queue_{{[0-9a-f]+}} cpp "gfsim::TimedEventQueue<std::int32_t>" kind "runtime_object"
// CHECK-NOT: acsim.binding
// CHECK: %[[EVENTS:.+]] = acsim.instance @events target @acir_event_queue_{{[0-9a-f]+}} args [2]
// CHECK: acsim.process @consumer captures(%[[EVENTS]]
// CHECK: acsim.invoke @acir_impl_event_try_recv_{{[0-9a-f]+}}
// CHECK: acsim.invoke @acir_impl_wake_event_queue_{{[0-9a-f]+}}
// CHECK: acsim.process @producer captures(%[[EVENTS]]
// CHECK: acsim.invoke @acir_impl_event_schedule_{{[0-9a-f]+}}
// CHECK: %[[EVENT_OBJECT:.+]], %[[EVENT_ACTIVATION:.+]] = acsim.dispatch @Top::@events path "root.events"
// CHECK: %[[CONSUMER_OBJECT:.+]], %[[CONSUMER_ACTIVATION:.+]] = acsim.dispatch @Top::@consumer path "root.consumer"
// CHECK: %[[PRODUCER_OBJECT:.+]], %[[PRODUCER_ACTIVATION:.+]] = acsim.dispatch @Top::@producer path "root.producer"
// CHECK: acsim.activate %[[EVENT_ACTIVATION]] to %[[CONSUMER_OBJECT]]
// CHECK-NEXT: acsim.activate %[[CONSUMER_ACTIVATION]] to %[[CONSUMER_OBJECT]]
// CHECK-NEXT: acsim.activate %[[PRODUCER_ACTIVATION]] to %[[PRODUCER_OBJECT]]
