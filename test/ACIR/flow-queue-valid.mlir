// RUN: %acir_opt_public %s | %FileCheck %s
// RUN: %acir_opt_public %s | %acir_opt_public | %FileCheck %s

builtin.module attributes {ac.contract_epoch = "0.2"} {
  ac.protocol @ready_valid {
    ac.role @sender dual @receiver cardinality "exclusive"
    ac.role @receiver dual @sender cardinality "exclusive"
    ac.state @idle initial true terminal false
    ac.event @transfer from @sender to @receiver payload i32 action "offer"
    ac.guarantee "ordering" = "fifo"
    ac.guarantee "backpressure" = "capacity"
  }

  ac.module @Producer() -> !ac.flow<i32, @ready_valid> parameters {} graph {
    ac.queue @out payload i32 entries 2 ordering "fifo"
        protocol @ready_valid ownership "exclusive" id "out" path "out"
    %flow = ac.flow.export @out : !ac.flow<i32, @ready_valid>
    ac.return %flow : !ac.flow<i32, @ready_valid>
  }

  ac.module @Consumer(!ac.flow<i32, @ready_valid>) parameters {} graph {
  ^bb0(%incoming : !ac.flow<i32, @ready_valid>):
    ac.queue @in payload i32 entries 1 ordering "fifo"
        protocol @ready_valid ownership "exclusive" id "in" path "in"
    ac.flow.import %incoming to @in : !ac.flow<i32, @ready_valid>
    ac.return
  }

  ac.module @Top() parameters {} graph {
    %flow = ac.instance @producer of @Producer() static {} id "producer"
        path "producer" : () -> !ac.flow<i32, @ready_valid>
    ac.instance @consumer of @Consumer(%flow) static {} id "consumer"
        path "consumer" : (!ac.flow<i32, @ready_valid>) -> ()
    ac.return
  }
}

// CHECK: %[[FLOW:.+]] = ac.flow.export @out : !ac.flow<i32, @ready_valid>
// CHECK: ac.flow.import %{{.+}} to @in : !ac.flow<i32, @ready_valid>
// CHECK: %[[TOP_FLOW:.+]] = ac.instance @producer of @Producer
// CHECK: ac.instance @consumer of @Consumer(%[[TOP_FLOW]])
