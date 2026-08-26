builtin.module attributes {ac.contract_epoch = "0.3"} {
  ac.system @static_specialization_system root @static_specialization as "static_specialization" tick 0 "cycle" seed {kind = "fixed", value = 0 : i64} instrumentation [] results {id = "default", format = "json"} selected true
  ac.module @static_specialization() parameters {} graph {
    %q0 = ac.v03.source "b0" : !ac.queue_v03<i8, #ac.queue_contract<depth = 1, latency = 1, rate = 1, domain = @core, ordering = fifo>>
    %q1, %q2, %q3 = ac.instance @replication_s1 of @static_specialization__replication(%q0) static {} id "s1" path "replication" : (!ac.queue_v03<i8, #ac.queue_contract<depth = 1, latency = 1, rate = 1, domain = @core, ordering = fifo>>) -> (!ac.queue_v03<i8, #ac.queue_contract<depth = 1, latency = 1, rate = 1, domain = @core, ordering = fifo>>, !ac.queue_v03<i8, #ac.queue_contract<depth = 1, latency = 1, rate = 1, domain = @core, ordering = fifo>>, !ac.queue_v03<i8, #ac.queue_contract<depth = 1, latency = 1, rate = 1, domain = @core, ordering = fifo>>)
    ac.v03.observe %q1 as "b2" fields [] : !ac.queue_v03<i8, #ac.queue_contract<depth = 1, latency = 1, rate = 1, domain = @core, ordering = fifo>>
    ac.v03.observe %q2 as "b3" fields [] : !ac.queue_v03<i8, #ac.queue_contract<depth = 1, latency = 1, rate = 1, domain = @core, ordering = fifo>>
    ac.v03.observe %q3 as "b4" fields [] : !ac.queue_v03<i8, #ac.queue_contract<depth = 1, latency = 1, rate = 1, domain = @core, ordering = fifo>>
    ac.return
  }
  ac.module @static_specialization__replication(!ac.queue_v03<i8, #ac.queue_contract<depth = 1, latency = 1, rate = 1, domain = @core, ordering = fifo>>) -> (!ac.queue_v03<i8, #ac.queue_contract<depth = 1, latency = 1, rate = 1, domain = @core, ordering = fifo>>, !ac.queue_v03<i8, #ac.queue_contract<depth = 1, latency = 1, rate = 1, domain = @core, ordering = fifo>>, !ac.queue_v03<i8, #ac.queue_contract<depth = 1, latency = 1, rate = 1, domain = @core, ordering = fifo>>) parameters {} graph {
  ^bb0(%q0 : !ac.queue_v03<i8, #ac.queue_contract<depth = 1, latency = 1, rate = 1, domain = @core, ordering = fifo>>):
    %q1, %q2, %q3 = ac.v03.fork %q0 : (!ac.queue_v03<i8, #ac.queue_contract<depth = 1, latency = 1, rate = 1, domain = @core, ordering = fifo>>) -> (!ac.queue_v03<i8, #ac.queue_contract<depth = 1, latency = 1, rate = 1, domain = @core, ordering = fifo>>, !ac.queue_v03<i8, #ac.queue_contract<depth = 1, latency = 1, rate = 1, domain = @core, ordering = fifo>>, !ac.queue_v03<i8, #ac.queue_contract<depth = 1, latency = 1, rate = 1, domain = @core, ordering = fifo>>)
    ac.return %q1, %q2, %q3 : !ac.queue_v03<i8, #ac.queue_contract<depth = 1, latency = 1, rate = 1, domain = @core, ordering = fifo>>, !ac.queue_v03<i8, #ac.queue_contract<depth = 1, latency = 1, rate = 1, domain = @core, ordering = fifo>>, !ac.queue_v03<i8, #ac.queue_contract<depth = 1, latency = 1, rate = 1, domain = @core, ordering = fifo>>
  }
}
