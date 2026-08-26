// RUN: %split_file %s %t
// RUN: %not %acir_opt %t/depth.mlir 2>&1 | %FileCheck %s --check-prefix=DEPTH
// RUN: %not %acir_opt %t/latency.mlir 2>&1 | %FileCheck %s --check-prefix=LATENCY
// RUN: %not %acir_opt %t/rate.mlir 2>&1 | %FileCheck %s --check-prefix=RATE
// RUN: %not %acir_opt %t/nested-queue.mlir 2>&1 | %FileCheck %s --check-prefix=NESTED-QUEUE
// RUN: %not %acir_opt %t/nested-var.mlir 2>&1 | %FileCheck %s --check-prefix=NESTED-VAR

// DEPTH: error: queue depth must be positive
// LATENCY: error: queue latency must be at least one
// RATE: error: queue rate must be positive
// NESTED-QUEUE: error: queue payload cannot be a queue or var type
// NESTED-VAR: error: var element cannot be a queue or var type

//--- depth.mlir
builtin.module attributes {ac.contract_epoch = "0.1"} {
  "builtin.unrealized_conversion_cast"() : () -> !ac.queue<i16, #ac.queue_contract<depth = 0, latency = 1, rate = 1, domain = @core, ordering = fifo>>
}

//--- latency.mlir
builtin.module attributes {ac.contract_epoch = "0.1"} {
  "builtin.unrealized_conversion_cast"() : () -> !ac.queue<i16, #ac.queue_contract<depth = 1, latency = 0, rate = 1, domain = @core, ordering = fifo>>
}

//--- rate.mlir
builtin.module attributes {ac.contract_epoch = "0.1"} {
  "builtin.unrealized_conversion_cast"() : () -> !ac.queue<i16, #ac.queue_contract<depth = 1, latency = 1, rate = 0, domain = @core, ordering = fifo>>
}

//--- nested-queue.mlir
builtin.module attributes {ac.contract_epoch = "0.1"} {
  "builtin.unrealized_conversion_cast"() : () -> !ac.queue<!ac.queue<i16, #ac.queue_contract<depth = 1, latency = 1, rate = 1, domain = @core, ordering = fifo>>, #ac.queue_contract<depth = 1, latency = 1, rate = 1, domain = @core, ordering = fifo>>
}

//--- nested-var.mlir
builtin.module attributes {ac.contract_epoch = "0.1"} {
  "builtin.unrealized_conversion_cast"() : () -> !ac.var<!ac.queue<i16, #ac.queue_contract<depth = 1, latency = 1, rate = 1, domain = @core, ordering = fifo>>>
}
