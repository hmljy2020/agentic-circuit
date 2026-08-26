builtin.module attributes {ac.contract_epoch = "0.3"} {
  ac.system @multiple_feedback_system root @multiple_feedback as "multiple_feedback" tick 0 "cycle" seed {kind = "fixed", value = 0 : i64} instrumentation [] results {id = "default", format = "json"} selected true
  ac.module @multiple_feedback() parameters {} graph {
    %q2 = ac.source "b0" : !ac.queue<i16, #ac.queue_contract<depth = 1, latency = 1, rate = 1, domain = @core, ordering = fifo>>
    %q3 = ac.merge (%q2, %q0, %q1) policy (#ac.policy<kind = round_robin>) : (!ac.queue<i16, #ac.queue_contract<depth = 1, latency = 1, rate = 1, domain = @core, ordering = fifo>>, !ac.queue<i16, #ac.queue_contract<depth = 2, latency = 1, rate = 1, domain = @core, ordering = fifo>>, !ac.queue<i16, #ac.queue_contract<depth = 3, latency = 2, rate = 1, domain = @core, ordering = fifo>>) -> !ac.queue<i16, #ac.queue_contract<depth = 1, latency = 1, rate = 1, domain = @core, ordering = fifo>>
    %q4, %q5 = ac.fork %q3 : (!ac.queue<i16, #ac.queue_contract<depth = 1, latency = 1, rate = 1, domain = @core, ordering = fifo>>) -> (!ac.queue<i16, #ac.queue_contract<depth = 1, latency = 1, rate = 1, domain = @core, ordering = fifo>>, !ac.queue<i16, #ac.queue_contract<depth = 1, latency = 1, rate = 1, domain = @core, ordering = fifo>>)
    %q0 = ac.queue %q4 : !ac.queue<i16, #ac.queue_contract<depth = 1, latency = 1, rate = 1, domain = @core, ordering = fifo>> -> !ac.queue<i16, #ac.queue_contract<depth = 2, latency = 1, rate = 1, domain = @core, ordering = fifo>>
    %q1 = ac.queue %q5 : !ac.queue<i16, #ac.queue_contract<depth = 1, latency = 1, rate = 1, domain = @core, ordering = fifo>> -> !ac.queue<i16, #ac.queue_contract<depth = 3, latency = 2, rate = 1, domain = @core, ordering = fifo>>
    ac.observe %q0 as "b5" fields [] : !ac.queue<i16, #ac.queue_contract<depth = 2, latency = 1, rate = 1, domain = @core, ordering = fifo>>
    ac.observe %q1 as "b6" fields [] : !ac.queue<i16, #ac.queue_contract<depth = 3, latency = 2, rate = 1, domain = @core, ordering = fifo>>
    ac.return
  }
}
