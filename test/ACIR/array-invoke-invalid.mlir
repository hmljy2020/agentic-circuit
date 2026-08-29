// RUN: %not %acir_opt %s --canonicalize 2>&1 | %FileCheck %s

// CHECK: error: 'ac.array.invoke' op ordinal must be non-negative and depth positive

builtin.module attributes {ac.contract_epoch = "0.4"} {
  ac.type_scope @types {
    ac.struct @Command fields [{name = "address", type = i4},
                               {name = "write", type = i1},
                               {name = "data", type = i16}]
    ac.struct @Response fields [{name = "id", type = i8},
                                {name = "data", type = i16}]
  } {dlti.dl_spec = #dlti.dl_spec<
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
  ac.array @banks of @Bank shape [2]() static [{}, {}]
      id "banks" path "banks" {ac.owner = "/"} : () -> ()

  %input = ac.source depth 2 latency 1
      : !ac.queue<!ac.struct<@types::@Command>>
  %response = ac.array.invoke @banks service "request", %input
      ordinal 0 depth 0 policy "priority" index {
    ^bb0(%item: !ac.var<!ac.struct<@types::@Command>>):
      %zero = ac.var.constant 0 : i1 as !ac.var<i1>
      ac.array.invoke.yield %zero : !ac.var<i1>
  } request {
    ^bb0(%item: !ac.var<!ac.struct<@types::@Command>>):
      ac.array.invoke.yield %item
          : !ac.var<!ac.struct<@types::@Command>>
  } context {
    ^bb0(%item: !ac.var<!ac.struct<@types::@Command>>):
      %id = ac.var.constant 0 : i8 as !ac.var<i8>
      ac.array.invoke.yield %id : !ac.var<i8>
  } response {
    ^bb0(%id: !ac.var<i8>, %data: !ac.var<i16>):
      %result = ac.var.create %id, %data fields ["id", "data"]
          : (!ac.var<i8>, !ac.var<i16>)
          -> !ac.var<!ac.struct<@types::@Response>>
      ac.array.invoke.yield %result
          : !ac.var<!ac.struct<@types::@Response>>
  } {ac.endpoint_path = "/response", ac.name = "response"}
      : !ac.queue<!ac.struct<@types::@Command>>
      -> !ac.queue<!ac.struct<@types::@Response>>
  ac.sink %response : !ac.queue<!ac.struct<@types::@Response>>
}
