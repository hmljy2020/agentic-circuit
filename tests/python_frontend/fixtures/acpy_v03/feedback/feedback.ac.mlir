builtin.module attributes {ac.contract_epoch = "0.3"} {
  ac.type_scope @types {
    ac.struct @Token fields [{name = "value", type = i16}]
  } {dlti.dl_spec = #dlti.dl_spec<
    !ac.struct<@types::@Token> = {abi_alignment = 2 : i64, endianness = "little", preferred_alignment = 2 : i64, size = 2 : i64}
  >}
  ac.system @feedback_system root @feedback as "feedback" tick 0 "cycle" seed {kind = "fixed", value = 0 : i64} instrumentation [] results {id = "default", format = "json"} selected true
  ac.module @feedback() parameters {} graph {
    %q1 = ac.v03.source "b0" : !ac.queue_v03<!ac.struct<@types::@Token>, #ac.queue_contract<depth = 1, latency = 1, rate = 1, domain = @core, ordering = fifo>>
    %q2 = ac.v03.merge (%q1, %q0) policy (#ac.policy<kind = round_robin>) : (!ac.queue_v03<!ac.struct<@types::@Token>, #ac.queue_contract<depth = 1, latency = 1, rate = 1, domain = @core, ordering = fifo>>, !ac.queue_v03<!ac.struct<@types::@Token>, #ac.queue_contract<depth = 1, latency = 1, rate = 1, domain = @core, ordering = fifo>>) -> !ac.queue_v03<!ac.struct<@types::@Token>, #ac.queue_contract<depth = 1, latency = 1, rate = 1, domain = @core, ordering = fifo>>
    %q3 = ac.queue %q2 : !ac.queue_v03<!ac.struct<@types::@Token>, #ac.queue_contract<depth = 1, latency = 1, rate = 1, domain = @core, ordering = fifo>> -> !ac.queue_v03<!ac.struct<@types::@Token>, #ac.queue_contract<depth = 2, latency = 1, rate = 1, domain = @core, ordering = fifo>>
    %q0 = ac.compute %q3 {
    ^bb0(%v0: !ac.var<!ac.struct<@types::@Token>>):
      ac.var.yield %v0 : !ac.var<!ac.struct<@types::@Token>>
    } : (!ac.queue_v03<!ac.struct<@types::@Token>, #ac.queue_contract<depth = 2, latency = 1, rate = 1, domain = @core, ordering = fifo>>) -> !ac.queue_v03<!ac.struct<@types::@Token>, #ac.queue_contract<depth = 1, latency = 1, rate = 1, domain = @core, ordering = fifo>>
    ac.v03.observe %q0 as "b4" fields [] : !ac.queue_v03<!ac.struct<@types::@Token>, #ac.queue_contract<depth = 1, latency = 1, rate = 1, domain = @core, ordering = fifo>>
    ac.return
  }
}
