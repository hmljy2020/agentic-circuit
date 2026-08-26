builtin.module attributes {ac.contract_epoch = "0.3"} {
  ac.type_scope @types {
    ac.struct @Packet fields [{name = "lane", type = i1}, {name = "payload", type = i32}]
  } {dlti.dl_spec = #dlti.dl_spec<
    !ac.struct<@types::@Packet> = {abi_alignment = 4 : i64, endianness = "little", preferred_alignment = 4 : i64, size = 8 : i64}
  >}
  ac.system @destructuring_system root @destructuring as "destructuring" tick 0 "cycle" seed {kind = "fixed", value = 0 : i64} instrumentation [] results {id = "default", format = "json"} selected true
  ac.module @destructuring() parameters {} graph {
    %q0 = ac.v03.source "b0" : !ac.queue_v03<!ac.struct<@types::@Packet>, #ac.queue_contract<depth = 1, latency = 1, rate = 1, domain = @core, ordering = fifo>>
    %q1, %q2 = ac.v03.route %q0 by (#ac.field<root = !ac.struct<@types::@Packet>, path = ["lane"], leaf = i1>) : (!ac.queue_v03<!ac.struct<@types::@Packet>, #ac.queue_contract<depth = 1, latency = 1, rate = 1, domain = @core, ordering = fifo>>) -> (!ac.queue_v03<!ac.struct<@types::@Packet>, #ac.queue_contract<depth = 1, latency = 1, rate = 1, domain = @core, ordering = fifo>>, !ac.queue_v03<!ac.struct<@types::@Packet>, #ac.queue_contract<depth = 1, latency = 1, rate = 1, domain = @core, ordering = fifo>>)
    %q3 = ac.v03.merge (%q1, %q2) policy (#ac.policy<kind = round_robin>) : (!ac.queue_v03<!ac.struct<@types::@Packet>, #ac.queue_contract<depth = 1, latency = 1, rate = 1, domain = @core, ordering = fifo>>, !ac.queue_v03<!ac.struct<@types::@Packet>, #ac.queue_contract<depth = 1, latency = 1, rate = 1, domain = @core, ordering = fifo>>) -> !ac.queue_v03<!ac.struct<@types::@Packet>, #ac.queue_contract<depth = 1, latency = 1, rate = 1, domain = @core, ordering = fifo>>
    %q4, %q5 = ac.v03.fork %q3 : (!ac.queue_v03<!ac.struct<@types::@Packet>, #ac.queue_contract<depth = 1, latency = 1, rate = 1, domain = @core, ordering = fifo>>) -> (!ac.queue_v03<!ac.struct<@types::@Packet>, #ac.queue_contract<depth = 1, latency = 1, rate = 1, domain = @core, ordering = fifo>>, !ac.queue_v03<!ac.struct<@types::@Packet>, #ac.queue_contract<depth = 1, latency = 1, rate = 1, domain = @core, ordering = fifo>>)
    ac.v03.observe %q4 as "b4" fields [] : !ac.queue_v03<!ac.struct<@types::@Packet>, #ac.queue_contract<depth = 1, latency = 1, rate = 1, domain = @core, ordering = fifo>>
    ac.v03.observe %q5 as "b5" fields [] : !ac.queue_v03<!ac.struct<@types::@Packet>, #ac.queue_contract<depth = 1, latency = 1, rate = 1, domain = @core, ordering = fifo>>
    ac.return
  }
}
