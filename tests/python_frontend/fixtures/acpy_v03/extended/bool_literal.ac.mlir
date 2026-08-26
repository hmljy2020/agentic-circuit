builtin.module attributes {ac.contract_epoch = "0.3"} {
  ac.type_scope @types {
    ac.struct @Flag fields [{name = "value", type = i1}]
  } {dlti.dl_spec = #dlti.dl_spec<
    !ac.struct<@types::@Flag> = {abi_alignment = 1 : i64, endianness = "little", preferred_alignment = 1 : i64, size = 1 : i64}
  >}
  ac.system @bool_literal_system root @bool_literal as "bool_literal" tick 0 "cycle" seed {kind = "fixed", value = 0 : i64} instrumentation [] results {id = "default", format = "json"} selected true
  ac.module @bool_literal() parameters {} graph {
    %q0 = ac.source "b0" : !ac.queue<!ac.struct<@types::@Flag>, #ac.queue_contract<depth = 1, latency = 1, rate = 1, domain = @core, ordering = fifo>>
    %q1 = ac.compute %q0 {
    ^bb0(%v0: !ac.var<!ac.struct<@types::@Flag>>):
      %v1 = ac.var.constant true as !ac.var<i1>
      %v2 = ac.var.struct ["value"](%v1) : (!ac.var<i1>) -> !ac.var<!ac.struct<@types::@Flag>>
      ac.var.yield %v2 : !ac.var<!ac.struct<@types::@Flag>>
    } : (!ac.queue<!ac.struct<@types::@Flag>, #ac.queue_contract<depth = 1, latency = 1, rate = 1, domain = @core, ordering = fifo>>) -> !ac.queue<!ac.struct<@types::@Flag>, #ac.queue_contract<depth = 1, latency = 1, rate = 1, domain = @core, ordering = fifo>>
    ac.observe %q1 as "b2" fields [] : !ac.queue<!ac.struct<@types::@Flag>, #ac.queue_contract<depth = 1, latency = 1, rate = 1, domain = @core, ordering = fifo>>
    ac.return
  }
}
