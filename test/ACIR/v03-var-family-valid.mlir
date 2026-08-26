// RUN: %acir_opt %s | %FileCheck %s
// RUN: %acir_opt %s | %acir_opt | %FileCheck %s

builtin.module attributes {ac.contract_epoch = "0.3"} {
  ac.type_scope @types {
    ac.struct @Pair fields [{name = "value", type = i16}]
  } {dlti.dl_spec = #dlti.dl_spec<
    !ac.struct<@types::@Pair> = {abi_alignment = 2 : i64, endianness = "little", preferred_alignment = 2 : i64, size = 2 : i64}
  >}
  ac.system @s root @m as "m" tick 0 "cycle" seed {kind = "fixed", value = 0 : i64} instrumentation [] results {id = "default", format = "json"} selected true
  ac.module @m() parameters {} graph {
    %source = ac.source "input" : !ac.queue<i16, #ac.queue_contract<depth = 1, latency = 1, rate = 1, domain = @core, ordering = fifo>>
    %result = ac.compute %source {
    ^bb0(%input: !ac.var<i16>):
      %one = ac.var.constant 1 : i16 as !ac.var<i16>
      %index = ac.var.constant 0 : i64 as !ac.var<i64>
      %record = ac.var.struct ["value"](%input) : (!ac.var<i16>) -> !ac.var<!ac.struct<@types::@Pair>>
      %value = ac.var.get %record ["value"] : (!ac.var<!ac.struct<@types::@Pair>>) -> !ac.var<i16>
      %sum = ac.var.binary "add" %value, %one : (!ac.var<i16>) -> !ac.var<i16> rhs !ac.var<i16>
      %updated = ac.var.update %record ["value"](%sum) : (!ac.var<!ac.struct<@types::@Pair>>) -> !ac.var<!ac.struct<@types::@Pair>> with !ac.var<i16>
      %array = ac.var.array (%value, %sum) : (!ac.var<i16>, !ac.var<i16>) -> !ac.var<!ac.vector<2 x i16>>
      %element = ac.var.extract %array[%index] : (!ac.var<!ac.vector<2 x i16>>) -> !ac.var<i16> index !ac.var<i64>
      %negated = ac.var.unary "neg" %element : (!ac.var<i16>) -> !ac.var<i16>
      %equal = ac.var.compare "eq" %negated, %sum : (!ac.var<i16>) -> !ac.var<i1> rhs !ac.var<i16>
      %selected = ac.var.select %equal, %negated, %sum : (!ac.var<i16>) -> !ac.var<i16> condition !ac.var<i1> false !ac.var<i16>
      %wide = ac.var.cast %selected : (!ac.var<i16>) -> !ac.var<i32>
      ac.var.yield %selected : !ac.var<i16>
    } : (!ac.queue<i16, #ac.queue_contract<depth = 1, latency = 1, rate = 1, domain = @core, ordering = fifo>>) -> !ac.queue<i16, #ac.queue_contract<depth = 1, latency = 1, rate = 1, domain = @core, ordering = fifo>>
    ac.observe %result as "result" fields [] : !ac.queue<i16, #ac.queue_contract<depth = 1, latency = 1, rate = 1, domain = @core, ordering = fifo>>
    ac.return
  }
}

// CHECK: ac.var.constant
// CHECK: ac.var.struct
// CHECK: ac.var.get
// CHECK: ac.var.binary
// CHECK: ac.var.update
// CHECK: ac.var.array
// CHECK: ac.var.extract
// CHECK: ac.var.unary
// CHECK: ac.var.compare
// CHECK: ac.var.select
// CHECK: ac.var.cast
// CHECK: ac.var.yield
