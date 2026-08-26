// RUN: %acir_opt %s | %FileCheck %s
// RUN: %acir_opt %s | %acir_opt | %FileCheck %s
// RUN: %acir_opt --emit-bytecode -o %t.bc %s
// RUN: %acir_opt %t.bc | %FileCheck %s

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
    %source = ac.v03.source "input" : !ac.queue_v03<!ac.struct<@types::@Input>, #ac.queue_contract<depth = 1, latency = 1, rate = 1, domain = @core, ordering = fifo>>
    %result = ac.compute %source {
    ^bb0(%record: !ac.var<!ac.struct<@types::@Input>>):
      %value = ac.var.get %record field "value" : !ac.var<!ac.struct<@types::@Input>> -> !ac.var<i16>
      %one = ac.var.constant 1 : i16 as !ac.var<i16>
      %sum = ac.var.binary "add" %value, %one : (!ac.var<i16>) -> !ac.var<i16> rhs !ac.var<i16>
      %output = ac.var.struct ["value"](%sum) : (!ac.var<i16>) -> !ac.var<!ac.struct<@types::@Output>>
      ac.var.yield %output : !ac.var<!ac.struct<@types::@Output>>
    } : (!ac.queue_v03<!ac.struct<@types::@Input>, #ac.queue_contract<depth = 1, latency = 1, rate = 1, domain = @core, ordering = fifo>>) -> !ac.queue_v03<!ac.struct<@types::@Output>, #ac.queue_contract<depth = 1, latency = 1, rate = 1, domain = @core, ordering = fifo>>
    ac.v03.observe %result as "result" fields ["value"] : !ac.queue_v03<!ac.struct<@types::@Output>, #ac.queue_contract<depth = 1, latency = 1, rate = 1, domain = @core, ordering = fifo>>
    ac.v03.observe %result as "result_copy" fields [] : !ac.queue_v03<!ac.struct<@types::@Output>, #ac.queue_contract<depth = 1, latency = 1, rate = 1, domain = @core, ordering = fifo>>
    ac.return
  }
}

// CHECK: ac.v03.source "input"
// CHECK: ac.compute
// CHECK: ac.var.get
// CHECK: ac.var.constant
// CHECK: ac.var.binary
// CHECK: ac.var.struct
// CHECK: ac.var.yield
// CHECK: ac.v03.observe
