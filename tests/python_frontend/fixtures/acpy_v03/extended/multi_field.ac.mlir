builtin.module attributes {ac.contract_epoch = "0.3"} {
  ac.type_scope @types {
    ac.struct @Input fields [{name = "left", type = i8}, {name = "right", type = i32}]
    ac.struct @Output fields [{name = "left", type = i8}, {name = "right", type = i32}]
  } {dlti.dl_spec = #dlti.dl_spec<
    !ac.struct<@types::@Input> = {abi_alignment = 4 : i64, endianness = "little", preferred_alignment = 4 : i64, size = 8 : i64},
    !ac.struct<@types::@Output> = {abi_alignment = 4 : i64, endianness = "little", preferred_alignment = 4 : i64, size = 8 : i64}
  >}
  ac.system @multi_field_system root @multi_field as "multi_field" tick 0 "cycle" seed {kind = "fixed", value = 0 : i64} instrumentation [] results {id = "default", format = "json"} selected true
  ac.module @multi_field() parameters {} graph {
    %q0 = ac.source "b0" : !ac.queue<!ac.struct<@types::@Input>, #ac.queue_contract<depth = 1, latency = 1, rate = 1, domain = @core, ordering = fifo>>
    %q1 = ac.compute %q0 {
    ^bb0(%v0: !ac.var<!ac.struct<@types::@Input>>):
      %v1 = ac.var.get %v0 ["left"] : (!ac.var<!ac.struct<@types::@Input>>) -> !ac.var<i8>
      %v2 = ac.var.constant 1 : i8 as !ac.var<i8>
      %v3 = ac.var.binary "add" %v1, %v2 : (!ac.var<i8>) -> !ac.var<i8> rhs !ac.var<i8>
      %v4 = ac.var.get %v0 ["right"] : (!ac.var<!ac.struct<@types::@Input>>) -> !ac.var<i32>
      %v5 = ac.var.constant 2 : i32 as !ac.var<i32>
      %v6 = ac.var.binary "add" %v4, %v5 : (!ac.var<i32>) -> !ac.var<i32> rhs !ac.var<i32>
      %v7 = ac.var.struct ["left", "right"](%v3, %v6) : (!ac.var<i8>, !ac.var<i32>) -> !ac.var<!ac.struct<@types::@Output>>
      ac.var.yield %v7 : !ac.var<!ac.struct<@types::@Output>>
    } : (!ac.queue<!ac.struct<@types::@Input>, #ac.queue_contract<depth = 1, latency = 1, rate = 1, domain = @core, ordering = fifo>>) -> !ac.queue<!ac.struct<@types::@Output>, #ac.queue_contract<depth = 1, latency = 1, rate = 1, domain = @core, ordering = fifo>>
    ac.observe %q1 as "b2" fields [] : !ac.queue<!ac.struct<@types::@Output>, #ac.queue_contract<depth = 1, latency = 1, rate = 1, domain = @core, ordering = fifo>>
    ac.return
  }
}
