builtin.module attributes {ac.contract_epoch = "0.3"} {
  ac.system @scalar_chain_system root @scalar_chain as "scalar_chain" tick 0 "cycle" seed {kind = "fixed", value = 0 : i64} instrumentation [] results {id = "default", format = "json"} selected true
  ac.module @scalar_chain() parameters {} graph {
    %q0 = ac.v03.source "b0" : !ac.queue_v03<i16, #ac.queue_contract<depth = 1, latency = 1, rate = 1, domain = @core, ordering = fifo>>
    %q1 = ac.compute %q0 {
    ^bb0(%v0: !ac.var<i16>):
      %v1 = ac.var.constant 1 : i16 as !ac.var<i16>
      %v2 = ac.var.binary "add" %v0, %v1 : (!ac.var<i16>) -> !ac.var<i16> rhs !ac.var<i16>
      ac.var.yield %v2 : !ac.var<i16>
    } : (!ac.queue_v03<i16, #ac.queue_contract<depth = 1, latency = 1, rate = 1, domain = @core, ordering = fifo>>) -> !ac.queue_v03<i16, #ac.queue_contract<depth = 1, latency = 1, rate = 1, domain = @core, ordering = fifo>>
    %q2 = ac.compute %q1 {
    ^bb0(%v0: !ac.var<i16>):
      %v1 = ac.var.constant 1 : i16 as !ac.var<i16>
      %v2 = ac.var.binary "add" %v0, %v1 : (!ac.var<i16>) -> !ac.var<i16> rhs !ac.var<i16>
      ac.var.yield %v2 : !ac.var<i16>
    } : (!ac.queue_v03<i16, #ac.queue_contract<depth = 1, latency = 1, rate = 1, domain = @core, ordering = fifo>>) -> !ac.queue_v03<i16, #ac.queue_contract<depth = 1, latency = 1, rate = 1, domain = @core, ordering = fifo>>
    ac.v03.observe %q2 as "b3" fields [] : !ac.queue_v03<i16, #ac.queue_contract<depth = 1, latency = 1, rate = 1, domain = @core, ordering = fifo>>
    ac.v03.observe %q2 as "b4" fields [] : !ac.queue_v03<i16, #ac.queue_contract<depth = 1, latency = 1, rate = 1, domain = @core, ordering = fifo>>
    ac.return
  }
}
