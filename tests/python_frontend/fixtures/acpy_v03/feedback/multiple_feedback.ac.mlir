builtin.module attributes {ac.contract_epoch = "0.3"} {
  ac.system @multiple_feedback_system root @multiple_feedback as "multiple_feedback" tick 0 "cycle" seed {kind = "fixed", value = 0 : i64} instrumentation [] results {id = "default", format = "json"} selected true
  ac.module @multiple_feedback() parameters {} graph {
    %q2 = ac.v03.source "b0" : !ac.queue_v03<i16, #ac.queue_contract<depth = 1, latency = 1, rate = 1, domain = @core, ordering = fifo>>
    %q3 = ac.v03.merge (%q2, %q0, %q1) policy (#ac.policy<kind = round_robin>) : (!ac.queue_v03<i16, #ac.queue_contract<depth = 1, latency = 1, rate = 1, domain = @core, ordering = fifo>>, !ac.queue_v03<i16, #ac.queue_contract<depth = 2, latency = 1, rate = 1, domain = @core, ordering = fifo>>, !ac.queue_v03<i16, #ac.queue_contract<depth = 3, latency = 2, rate = 1, domain = @core, ordering = fifo>>) -> !ac.queue_v03<i16, #ac.queue_contract<depth = 1, latency = 1, rate = 1, domain = @core, ordering = fifo>>
    %q4, %q5 = ac.v03.fork %q3 : (!ac.queue_v03<i16, #ac.queue_contract<depth = 1, latency = 1, rate = 1, domain = @core, ordering = fifo>>) -> (!ac.queue_v03<i16, #ac.queue_contract<depth = 1, latency = 1, rate = 1, domain = @core, ordering = fifo>>, !ac.queue_v03<i16, #ac.queue_contract<depth = 1, latency = 1, rate = 1, domain = @core, ordering = fifo>>)
    %q0 = ac.queue %q4 : !ac.queue_v03<i16, #ac.queue_contract<depth = 1, latency = 1, rate = 1, domain = @core, ordering = fifo>> -> !ac.queue_v03<i16, #ac.queue_contract<depth = 2, latency = 1, rate = 1, domain = @core, ordering = fifo>>
    %q1 = ac.queue %q5 : !ac.queue_v03<i16, #ac.queue_contract<depth = 1, latency = 1, rate = 1, domain = @core, ordering = fifo>> -> !ac.queue_v03<i16, #ac.queue_contract<depth = 3, latency = 2, rate = 1, domain = @core, ordering = fifo>>
    ac.v03.observe %q0 as "b5" fields [] : !ac.queue_v03<i16, #ac.queue_contract<depth = 2, latency = 1, rate = 1, domain = @core, ordering = fifo>>
    ac.v03.observe %q1 as "b6" fields [] : !ac.queue_v03<i16, #ac.queue_contract<depth = 3, latency = 2, rate = 1, domain = @core, ordering = fifo>>
    ac.return
  }
}
