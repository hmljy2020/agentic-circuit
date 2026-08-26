builtin.module attributes {ac.contract_epoch = "0.3"} {
  ac.system @queue_contracts_system root @queue_contracts as "queue_contracts" tick 0 "cycle" seed {kind = "fixed", value = 0 : i64} instrumentation [] results {id = "default", format = "json"} selected true
  ac.module @queue_contracts() parameters {} graph {
    %q0 = ac.v03.source "b0" : !ac.queue_v03<i32, #ac.queue_contract<depth = 3, latency = 2, rate = 4, domain = @ingress, ordering = fifo>>
    %q1 = ac.queue %q0 : !ac.queue_v03<i32, #ac.queue_contract<depth = 3, latency = 2, rate = 4, domain = @ingress, ordering = fifo>> -> !ac.queue_v03<i32, #ac.queue_contract<depth = 8, latency = 3, rate = 2, domain = @execute, ordering = fifo>>
    ac.v03.observe %q1 as "b2" fields [] : !ac.queue_v03<i32, #ac.queue_contract<depth = 8, latency = 3, rate = 2, domain = @execute, ordering = fifo>>
    ac.return
  }
}
