builtin.module attributes {ac.contract_epoch = "0.3"} {
  ac.type_scope @types {
    ac.struct @Operands fields [{name = "left", type = i16}, {name = "right", type = i16}, {name = "mask", type = i16}]
    ac.struct @Results fields [{name = "added", type = i16}, {name = "subtracted", type = i16}, {name = "multiplied", type = i16}, {name = "conjunction", type = i16}, {name = "disjunction", type = i16}, {name = "exclusive", type = i16}]
  } {dlti.dl_spec = #dlti.dl_spec<
    !ac.struct<@types::@Operands> = {abi_alignment = 2 : i64, endianness = "little", preferred_alignment = 2 : i64, size = 6 : i64},
    !ac.struct<@types::@Results> = {abi_alignment = 2 : i64, endianness = "little", preferred_alignment = 2 : i64, size = 12 : i64}
  >}
  ac.system @arithmetic_family_system root @arithmetic_family as "arithmetic_family" tick 0 "cycle" seed {kind = "fixed", value = 0 : i64} instrumentation [] results {id = "default", format = "json"} selected true
  ac.module @arithmetic_family() parameters {} graph {
    %q0 = ac.v03.source "b0" : !ac.queue_v03<!ac.struct<@types::@Operands>, #ac.queue_contract<depth = 1, latency = 1, rate = 1, domain = @core, ordering = fifo>>
    %q1 = ac.compute %q0 {
    ^bb0(%v0: !ac.var<!ac.struct<@types::@Operands>>):
      %v1 = ac.var.get %v0 field "left" : !ac.var<!ac.struct<@types::@Operands>> -> !ac.var<i16>
      %v2 = ac.var.get %v0 field "right" : !ac.var<!ac.struct<@types::@Operands>> -> !ac.var<i16>
      %v3 = ac.var.binary "add" %v1, %v2 : (!ac.var<i16>) -> !ac.var<i16> rhs !ac.var<i16>
      %v4 = ac.var.get %v0 field "left" : !ac.var<!ac.struct<@types::@Operands>> -> !ac.var<i16>
      %v5 = ac.var.get %v0 field "right" : !ac.var<!ac.struct<@types::@Operands>> -> !ac.var<i16>
      %v6 = ac.var.binary "sub" %v4, %v5 : (!ac.var<i16>) -> !ac.var<i16> rhs !ac.var<i16>
      %v7 = ac.var.get %v0 field "left" : !ac.var<!ac.struct<@types::@Operands>> -> !ac.var<i16>
      %v8 = ac.var.get %v0 field "right" : !ac.var<!ac.struct<@types::@Operands>> -> !ac.var<i16>
      %v9 = ac.var.binary "mul" %v7, %v8 : (!ac.var<i16>) -> !ac.var<i16> rhs !ac.var<i16>
      %v10 = ac.var.get %v0 field "left" : !ac.var<!ac.struct<@types::@Operands>> -> !ac.var<i16>
      %v11 = ac.var.get %v0 field "mask" : !ac.var<!ac.struct<@types::@Operands>> -> !ac.var<i16>
      %v12 = ac.var.binary "and" %v10, %v11 : (!ac.var<i16>) -> !ac.var<i16> rhs !ac.var<i16>
      %v13 = ac.var.get %v0 field "left" : !ac.var<!ac.struct<@types::@Operands>> -> !ac.var<i16>
      %v14 = ac.var.get %v0 field "mask" : !ac.var<!ac.struct<@types::@Operands>> -> !ac.var<i16>
      %v15 = ac.var.binary "or" %v13, %v14 : (!ac.var<i16>) -> !ac.var<i16> rhs !ac.var<i16>
      %v16 = ac.var.get %v0 field "left" : !ac.var<!ac.struct<@types::@Operands>> -> !ac.var<i16>
      %v17 = ac.var.get %v0 field "mask" : !ac.var<!ac.struct<@types::@Operands>> -> !ac.var<i16>
      %v18 = ac.var.binary "xor" %v16, %v17 : (!ac.var<i16>) -> !ac.var<i16> rhs !ac.var<i16>
      %v19 = ac.var.struct ["added", "subtracted", "multiplied", "conjunction", "disjunction", "exclusive"](%v3, %v6, %v9, %v12, %v15, %v18) : (!ac.var<i16>, !ac.var<i16>, !ac.var<i16>, !ac.var<i16>, !ac.var<i16>, !ac.var<i16>) -> !ac.var<!ac.struct<@types::@Results>>
      ac.var.yield %v19 : !ac.var<!ac.struct<@types::@Results>>
    } : (!ac.queue_v03<!ac.struct<@types::@Operands>, #ac.queue_contract<depth = 1, latency = 1, rate = 1, domain = @core, ordering = fifo>>) -> !ac.queue_v03<!ac.struct<@types::@Results>, #ac.queue_contract<depth = 1, latency = 1, rate = 1, domain = @core, ordering = fifo>>
    ac.v03.observe %q1 as "b2" fields [] : !ac.queue_v03<!ac.struct<@types::@Results>, #ac.queue_contract<depth = 1, latency = 1, rate = 1, domain = @core, ordering = fifo>>
    ac.return
  }
}
