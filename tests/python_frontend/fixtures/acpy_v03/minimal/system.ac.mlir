builtin.module attributes {ac.contract_epoch = "0.3"} {
  ac.type_scope @types {
    ac.struct @Input fields [{name = "value", type = i16}]
    ac.struct @Output fields [{name = "value", type = i16}]
  } {dlti.dl_spec = #dlti.dl_spec<
    !ac.struct<@types::@Input> = {abi_alignment = 2 : i64, endianness = "little", preferred_alignment = 2 : i64, size = 2 : i64},
    !ac.struct<@types::@Output> = {abi_alignment = 2 : i64, endianness = "little", preferred_alignment = 2 : i64, size = 2 : i64}
  >}
  ac.system @minimal_system root @minimal as "minimal" tick 0 "cycle" seed {kind = "fixed", value = 0 : i64} instrumentation [] results {id = "default", format = "json"} selected true
  ac.module @minimal() parameters {} graph {
    %q0 = ac.v03.source "b0" : !ac.queue_v03<!ac.struct<@types::@Input>, #ac.queue_contract<depth = 1, latency = 1, rate = 1, domain = @core, ordering = fifo>>
    %q1 = ac.compute %q0 {
    ^bb0(%v0: !ac.var<!ac.struct<@types::@Input>>):
      %v1 = ac.var.get %v0 field "value" : !ac.var<!ac.struct<@types::@Input>> -> !ac.var<i16>
      %v2 = ac.var.constant 1 : i16 as !ac.var<i16>
      %v3 = ac.var.binary "add" %v1, %v2 : (!ac.var<i16>) -> !ac.var<i16> rhs !ac.var<i16>
      %v4 = ac.var.struct ["value"](%v3) : (!ac.var<i16>) -> !ac.var<!ac.struct<@types::@Output>>
      ac.var.yield %v4 : !ac.var<!ac.struct<@types::@Output>>
    } : (!ac.queue_v03<!ac.struct<@types::@Input>, #ac.queue_contract<depth = 1, latency = 1, rate = 1, domain = @core, ordering = fifo>>) -> !ac.queue_v03<!ac.struct<@types::@Output>, #ac.queue_contract<depth = 1, latency = 1, rate = 1, domain = @core, ordering = fifo>>
    ac.v03.observe %q1 as "b2" fields [] : !ac.queue_v03<!ac.struct<@types::@Output>, #ac.queue_contract<depth = 1, latency = 1, rate = 1, domain = @core, ordering = fifo>>
    ac.return
  }
}
