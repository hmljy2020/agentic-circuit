// RUN: %acir_opt %s | %FileCheck %s
// RUN: %acir_opt %s | %acir_opt | %FileCheck %s

builtin.module attributes {ac.contract_epoch = "0.4"} {
  ac.type_scope @types {
    ac.struct @Decoded fields [
      {name = "row", type = i1},
      {name = "col", type = i1},
      {name = "address", type = i4},
      {name = "id", type = i8},
      {name = "write", type = i1},
      {name = "data", type = i16}
    ]
    ac.struct @Command fields [
      {name = "address", type = i4},
      {name = "write", type = i1},
      {name = "data", type = i16}
    ]
    ac.struct @Response fields [
      {name = "id", type = i8},
      {name = "data", type = i16}
    ]
  } {dlti.dl_spec = #dlti.dl_spec<
      !ac.struct<@types::@Decoded> = {abi_alignment = 2 : i64, endianness = "little", preferred_alignment = 2 : i64, size = 8 : i64},
      !ac.struct<@types::@Command> = {abi_alignment = 2 : i64, endianness = "little", preferred_alignment = 2 : i64, size = 4 : i64},
      !ac.struct<@types::@Response> = {abi_alignment = 2 : i64, endianness = "little", preferred_alignment = 2 : i64, size = 4 : i64}>}
  ac.module.generated @Bank : () -> () parameters {}
      generator {registry = "ac", name = "memory_bank"}
      {ac.memory = {data_type = i16, entries = 16 : i64, init = 0 : i64,
                    latency = 2 : i64},
       ac.services = [{name = "request",
                      request = !ac.struct<@types::@Command>,
                      response = i16,
                      max_outstanding = 1 : i64}]}
  ac.array @banks of @Bank shape [2, 2]() static [{}, {}, {}, {}]
      id "banks" path "banks" {ac.owner = "/sram"} : () -> ()

  %input = ac.source depth 2 latency 1
      : !ac.queue<!ac.struct<@types::@Decoded>>
  %response = ac.array.invoke @banks service "request", %input
      ordinal 0 depth 2 policy "priority" index {
    ^bb0(%item: !ac.var<!ac.struct<@types::@Decoded>>):
      %row = ac.var.get %item field "row"
          : !ac.var<!ac.struct<@types::@Decoded>> -> !ac.var<i1>
      %col = ac.var.get %item field "col"
          : !ac.var<!ac.struct<@types::@Decoded>> -> !ac.var<i1>
      %one = ac.var.constant 1 : i1 as !ac.var<i1>
      %and = ac.var.and %row, %one : !ac.var<i1>
      %or = ac.var.or %row, %one : !ac.var<i1>
      %xor = ac.var.xor %row, %one : !ac.var<i1>
      %shl = ac.var.shl %row, %one : !ac.var<i1>
      %lshr = ac.var.lshr %row, %one : !ac.var<i1>
      %ashr = ac.var.ashr %row, %one : !ac.var<i1>
      %udiv = ac.var.udiv %row, %one : !ac.var<i1>
      %sdiv = ac.var.sdiv %row, %one : !ac.var<i1>
      %urem = ac.var.urem %row, %one : !ac.var<i1>
      %srem = ac.var.srem %row, %one : !ac.var<i1>
      %condition = ac.var.cmp "eq" %row, %one
          : !ac.var<i1> -> !ac.var<i1>
      %selected = ac.var.select %condition, %and, %or
          : !ac.var<i1>, !ac.var<i1>
      ac.array.invoke.yield %row, %col : !ac.var<i1>, !ac.var<i1>
  } request {
    ^bb0(%item: !ac.var<!ac.struct<@types::@Decoded>>):
      %address = ac.var.get %item field "address"
          : !ac.var<!ac.struct<@types::@Decoded>> -> !ac.var<i4>
      %write = ac.var.get %item field "write"
          : !ac.var<!ac.struct<@types::@Decoded>> -> !ac.var<i1>
      %data = ac.var.get %item field "data"
          : !ac.var<!ac.struct<@types::@Decoded>> -> !ac.var<i16>
      %command = ac.var.create %address, %write, %data
          fields ["address", "write", "data"]
          : (!ac.var<i4>, !ac.var<i1>, !ac.var<i16>)
          -> !ac.var<!ac.struct<@types::@Command>>
      ac.array.invoke.yield %command
          : !ac.var<!ac.struct<@types::@Command>>
  } context {
    ^bb0(%item: !ac.var<!ac.struct<@types::@Decoded>>):
      %id = ac.var.get %item field "id"
          : !ac.var<!ac.struct<@types::@Decoded>> -> !ac.var<i8>
      ac.array.invoke.yield %id : !ac.var<i8>
  } response {
    ^bb0(%id: !ac.var<i8>, %data: !ac.var<i16>):
      %result = ac.var.create %id, %data fields ["id", "data"]
          : (!ac.var<i8>, !ac.var<i16>)
          -> !ac.var<!ac.struct<@types::@Response>>
      ac.array.invoke.yield %result
          : !ac.var<!ac.struct<@types::@Response>>
  } {ac.endpoint_path = "/sram/response", ac.name = "response"}
      : !ac.queue<!ac.struct<@types::@Decoded>>
      -> !ac.queue<!ac.struct<@types::@Response>>
  ac.sink %response : !ac.queue<!ac.struct<@types::@Response>>
}

// CHECK: ac.array @banks of @Bank shape [2, 2]
// CHECK: ac.array.invoke @banks service "request"
// CHECK: ac.array.invoke.yield
// CHECK: ac.var.and
// CHECK: ac.var.select
