// RUN: %acir_opt %s | %FileCheck %s
// RUN: %acir_opt %s | %acir_opt | %FileCheck %s
// RUN: %acir_opt --emit-bytecode -o %t.bc %s
// RUN: %acir_opt %t.bc | %FileCheck %s

builtin.module attributes {ac.contract_epoch = "0.3"} {
  "builtin.unrealized_conversion_cast"() : () -> !ac.var<i16>
  "builtin.unrealized_conversion_cast"() : () -> !ac.queue<i16, #ac.queue_contract<depth = 4, latency = 1, rate = 2, domain = @core, ordering = fifo>>
}

// CHECK: !ac.var<i16>
// CHECK: !ac.queue<i16, #ac.queue_contract<depth = 4, latency = 1, rate = 2, domain = @core, ordering = fifo>>
