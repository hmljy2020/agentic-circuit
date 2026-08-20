module attributes {ac.contract_epoch = "0.2"} {
  ac.system @main root @pipeline as "root" tick 0 "cycle" seed {kind = "fixed", value = 0 : i64} instrumentation [] results {id = "default", format = "json"} selected true
  ac.protocol @ready_valid {
    ac.role @sender dual @receiver cardinality "exclusive"
    ac.role @receiver dual @sender cardinality "exclusive"
    ac.state @idle initial true terminal false
    ac.event @transfer_0 from @sender to @receiver payload i32 action "offer"
    ac.guarantee "ordering" = "fifo"
    ac.guarantee "backpressure" = "capacity"
  }
  ac.module @Refine(%input : !ac.flow<i32, @ready_valid>) -> !ac.flow<i32, @ready_valid> parameters {} graph {
    ac.return %input : !ac.flow<i32, @ready_valid>
  }
  ac.module @pipeline(%request : !ac.flow<i32, @ready_valid>) -> !ac.flow<i32, @ready_valid> parameters {} graph {
    %refined_0 = ac.instance @refined of @Refine(%request) static {} id "refined" path "refined" : (!ac.flow<i32, @ready_valid>) -> !ac.flow<i32, @ready_valid>
    ac.return %refined_0 : !ac.flow<i32, @ready_valid>
  }
}
