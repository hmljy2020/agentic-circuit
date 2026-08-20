// RUN: %acir_opt_public --ac-verify-model %s | %FileCheck %s
// RUN: %acir_opt_public --verify-each=false --pass-pipeline='builtin.module(ac-freeze-topology)' %s -o %t.frozen
// RUN: %acir_opt_public --ac-lower-to-acsim --ac-binding-profile=fast --ac-binding-target=x86_64-linux-gnu %t.frozen -o %t.first
// RUN: %acir_opt_public --ac-lower-to-acsim --ac-binding-profile=fast --ac-binding-target=x86_64-linux-gnu %t.frozen -o %t.second
// RUN: diff %t.first %t.second
// RUN: %FileCheck %s --check-prefix=LOWER < %t.first

builtin.module attributes {ac.contract_epoch = "0.2"} {
  ac.protocol @ready_valid {
    ac.role @sender dual @receiver cardinality "exclusive"
    ac.role @receiver dual @sender cardinality "exclusive"
    ac.state @idle initial true terminal false
    ac.event @transfer from @sender to @receiver payload i32 action "offer"
    ac.guarantee "ordering" = "fifo"
    ac.guarantee "backpressure" = "capacity"
  }
  ac.system @system root @Top as "root" tick 0 "cycle"
      workload @Top::@control seed {kind = "fixed", value = 0 : i64} instrumentation []
      results {id = "default", format = "json"} selected true
  ac.module @Producer() -> !ac.flow<i32, @ready_valid> parameters {} graph {
    ac.queue @out payload i32 entries 2 ordering "fifo" protocol @ready_valid
        ownership "exclusive" id "out" path "out"
    %flow = ac.flow.export @out : !ac.flow<i32, @ready_valid>
    ac.process @produce kind "control" {
      %payload = arith.constant 7 : i32
      %accepted = ac.try_send @out %payload : i32
      scf.if %accepted {
      } else {
        ac.await_queue @out until "writable"
      }
      ac.yield_sim
    }
    ac.return %flow : !ac.flow<i32, @ready_valid>
  }
  ac.module @Relay(!ac.flow<i32, @ready_valid>) -> !ac.flow<i32, @ready_valid>
      parameters {} graph {
  ^bb0(%flow : !ac.flow<i32, @ready_valid>):
    ac.return %flow : !ac.flow<i32, @ready_valid>
  }
  ac.module @Consumer(!ac.flow<i32, @ready_valid>) parameters {} graph {
  ^bb0(%flow : !ac.flow<i32, @ready_valid>):
    ac.queue @in payload i32 entries 1 ordering "fifo" protocol @ready_valid
        ownership "exclusive" id "in" path "in"
    ac.flow.import %flow to @in : !ac.flow<i32, @ready_valid>
    ac.process @consume kind "control" {
      %payload, %received = ac.try_recv @in : i32
      scf.if %received {
      } else {
        ac.await_queue @in until "readable"
      }
      ac.yield_sim
    }
    ac.return
  }
  ac.module @Top() parameters {} graph {
    %produced = ac.instance @producer of @Producer() static {} id "producer"
        path "producer" : () -> !ac.flow<i32, @ready_valid>
    %relayed = ac.instance @relay of @Relay(%produced) static {} id "relay"
        path "relay" : (!ac.flow<i32, @ready_valid>) -> !ac.flow<i32, @ready_valid>
    ac.instance @consumer of @Consumer(%relayed) static {} id "consumer"
        path "consumer" : (!ac.flow<i32, @ready_valid>) -> ()
    ac.process @control kind "workload" {
      ac.yield_sim
    }
    ac.return
  }
}

// CHECK: ac.flow.export @out
// CHECK: ac.flow.import %{{.+}} to @in
// LOWER-COUNT-1: cpp "gfsim::QueueLink<std::int32_t>" kind "runtime_object"
// LOWER: acsim.port %{{.+}} accessor @acir_flow_sink_accessor_Consumer_in
// LOWER: acsim.port %{{.+}} accessor @acir_flow_source_accessor_Producer_out
// LOWER-COUNT-1: acsim.instance @zz_flow_link_00000000
// LOWER-COUNT-1: acsim.bind %{{.+}} to %{{.+}} kind "flow"
// LOWER-COUNT-1: acsim.dispatch @Top::@zz_flow_link_00000000
