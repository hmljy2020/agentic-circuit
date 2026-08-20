// RUN: %acir_opt_public --verify-each=false --pass-pipeline='builtin.module(ac-freeze-topology)' %s -o %t.frozen
// RUN: %acir_opt_public --ac-lower-to-acsim --ac-binding-profile=fast --ac-binding-target=x86_64-linux-gnu %t.frozen -o %t.acsim
// RUN: %FileCheck %s < %t.acsim

// Native Flow projections are rank-2 module construction operations.  All
// projections must precede rank-6 exports, including when a module has more
// than one Flow boundary.

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
      workload @Top::@control seed {kind = "fixed", value = 0 : i64}
      instrumentation [] results {id = "default", format = "json"} selected true

  ac.module @Source() -> (!ac.flow<i32, @ready_valid>,
                          !ac.flow<i32, @ready_valid>) parameters {} graph {
    ac.queue @out0 payload i32 entries 1 ordering "fifo"
        protocol @ready_valid ownership "exclusive" id "out0" path "out0"
    ac.queue @out1 payload i32 entries 1 ordering "fifo"
        protocol @ready_valid ownership "exclusive" id "out1" path "out1"
    %flow0 = ac.flow.export @out0 : !ac.flow<i32, @ready_valid>
    %flow1 = ac.flow.export @out1 : !ac.flow<i32, @ready_valid>
    ac.return %flow0, %flow1 : !ac.flow<i32, @ready_valid>,
                              !ac.flow<i32, @ready_valid>
  }

  ac.module @Sink(!ac.flow<i32, @ready_valid>,
                  !ac.flow<i32, @ready_valid>) parameters {} graph {
  ^bb0(%flow0 : !ac.flow<i32, @ready_valid>,
       %flow1 : !ac.flow<i32, @ready_valid>):
    ac.queue @in0 payload i32 entries 1 ordering "fifo"
        protocol @ready_valid ownership "exclusive" id "in0" path "in0"
    ac.queue @in1 payload i32 entries 1 ordering "fifo"
        protocol @ready_valid ownership "exclusive" id "in1" path "in1"
    ac.flow.import %flow0 to @in0 : !ac.flow<i32, @ready_valid>
    ac.flow.import %flow1 to @in1 : !ac.flow<i32, @ready_valid>
    ac.return
  }

  ac.module @Top() parameters {} graph {
    %flow0, %flow1 = ac.instance @source of @Source() static {} id "source"
        path "source" : () -> (!ac.flow<i32, @ready_valid>,
                               !ac.flow<i32, @ready_valid>)
    ac.instance @sink of @Sink(%flow0, %flow1) static {} id "sink" path "sink"
        : (!ac.flow<i32, @ready_valid>, !ac.flow<i32, @ready_valid>) -> ()
    ac.process @control kind "workload" {
      ac.yield_sim
    }
    ac.return
  }
}

// CHECK-LABEL: acsim.module @Sink
// CHECK:       %{{[0-9]+}} = acsim.port
// CHECK-NEXT:  %{{[0-9]+}} = acsim.port
// CHECK:       acsim.export
// CHECK:       acsim.export
// CHECK-LABEL: acsim.module @Source
// CHECK:       %{{[0-9]+}} = acsim.port
// CHECK-NEXT:  %{{[0-9]+}} = acsim.port
// CHECK:       acsim.export
// CHECK:       acsim.export
