// RUN: %split_file %s %t
// RUN: %not %acir_opt %t/epoch.mlir 2>&1 | %FileCheck %s --check-prefix=EPOCH
// RUN: %not %acir_opt %t/contract.mlir 2>&1 | %FileCheck %s --check-prefix=CONTRACT
// RUN: %not %acir_opt %t/negative-latency.mlir 2>&1 | %FileCheck %s --check-prefix=NEGATIVE-LATENCY
// RUN: %not %acir_opt %t/unused.mlir 2>&1 | %FileCheck %s --check-prefix=UNUSED
// RUN: %not %acir_opt %t/transfer-escape.mlir 2>&1 | %FileCheck %s --check-prefix=TRANSFER-ESCAPE
// RUN: %not %acir_opt %t/inflight.mlir 2>&1 | %FileCheck %s --check-prefix=INFLIGHT
// RUN: %not %acir_opt %t/read-bounds.mlir 2>&1 | %FileCheck %s --check-prefix=READ-BOUNDS
// RUN: %not %acir_opt %t/write-bounds.mlir 2>&1 | %FileCheck %s --check-prefix=WRITE-BOUNDS

// EPOCH: error: 'ac.memory.resource' op requires top-level ac.contract_epoch = "0.3"
// CONTRACT: error: 'ac.memory.resource' op capacity_bytes and bytes_per_cycle must be positive
// NEGATIVE-LATENCY: error: 'ac.memory.resource' op read_latency and write_latency must be non-negative
// UNUSED: error: 'ac.memory.resource' op must be referenced by exactly one queue process
// TRANSFER-ESCAPE: error: memory_transfer type is private to ac.memory.read/write
// INFLIGHT: error: 'ac.queue.process' op v0.3 prototype requires inflight = 1
// READ-BOUNDS: error: 'ac.memory.read' op constant access exceeds memory capacity
// WRITE-BOUNDS: error: 'ac.memory.write' op constant access exceeds memory capacity

//--- epoch.mlir
module attributes {ac.contract_epoch = "0.2"} {
  ac.memory.resource @unused kind "sram" capacity_bytes 64 read_latency 1 write_latency 1 bytes_per_cycle 8
}

//--- contract.mlir
module attributes {ac.contract_epoch = "0.3"} {
  ac.memory.resource @bad kind "sram" capacity_bytes 0 read_latency 1 write_latency 1 bytes_per_cycle 8
}

//--- negative-latency.mlir
module attributes {ac.contract_epoch = "0.3"} {
  ac.memory.resource @bad kind "sram" capacity_bytes 64 read_latency -1 write_latency 1 bytes_per_cycle 8
}

//--- unused.mlir
module attributes {ac.contract_epoch = "0.3"} {
  ac.memory.resource @unused kind "sram" capacity_bytes 64 read_latency 1 write_latency 1 bytes_per_cycle 8
}

//--- transfer-escape.mlir
module attributes {ac.contract_epoch = "0.3"} {
  func.func private @escape(!ac.memory_transfer)
}

//--- inflight.mlir
module attributes {ac.contract_epoch = "0.3"} {
  ac.memory.resource @dram kind "dram" capacity_bytes 4096 read_latency 40 write_latency 20 bytes_per_cycle 32
  ac.memory.resource @sram kind "sram" capacity_bytes 1024 read_latency 2 write_latency 2 bytes_per_cycle 64
  %input = ac.source depth 1 latency 1 : !ac.queue<i8>
  %output = ac.queue.process %input inflight 2 depth 1 latency 1 {
  ^process(%item: !ac.var<i8>):
    %address = ac.var.constant 0 : i64 as !ac.var<i64>
    %size = ac.var.constant 8 : i32 as !ac.var<i32>
    %transfer = ac.memory.read @dram %address size %size : !ac.var<i64>, !ac.var<i32> -> !ac.memory_transfer
    ac.memory.write @sram %address data %transfer : !ac.var<i64>, !ac.memory_transfer
    ac.queue.process.yield %item : !ac.var<i8>
  } : !ac.queue<i8> -> !ac.queue<i8>
  ac.sink %output : !ac.queue<i8>
}

//--- read-bounds.mlir
module attributes {ac.contract_epoch = "0.3"} {
  ac.memory.resource @dram kind "dram" capacity_bytes 64 read_latency 40 write_latency 20 bytes_per_cycle 32
  ac.memory.resource @sram kind "sram" capacity_bytes 64 read_latency 2 write_latency 2 bytes_per_cycle 64
  %input = ac.source depth 1 latency 1 : !ac.queue<i8>
  %output = ac.queue.process %input inflight 1 depth 1 latency 1 {
  ^process(%item: !ac.var<i8>):
    %source = ac.var.constant 60 : i64 as !ac.var<i64>
    %size = ac.var.constant 8 : i32 as !ac.var<i32>
    %transfer = ac.memory.read @dram %source size %size : !ac.var<i64>, !ac.var<i32> -> !ac.memory_transfer
    %destination = ac.var.constant 0 : i64 as !ac.var<i64>
    ac.memory.write @sram %destination data %transfer : !ac.var<i64>, !ac.memory_transfer
    ac.queue.process.yield %item : !ac.var<i8>
  } : !ac.queue<i8> -> !ac.queue<i8>
  ac.sink %output : !ac.queue<i8>
}

//--- write-bounds.mlir
module attributes {ac.contract_epoch = "0.3"} {
  ac.memory.resource @dram kind "dram" capacity_bytes 64 read_latency 40 write_latency 20 bytes_per_cycle 32
  ac.memory.resource @sram kind "sram" capacity_bytes 64 read_latency 2 write_latency 2 bytes_per_cycle 64
  %input = ac.source depth 1 latency 1 : !ac.queue<i8>
  %output = ac.queue.process %input inflight 1 depth 1 latency 1 {
  ^process(%item: !ac.var<i8>):
    %source = ac.var.constant 0 : i64 as !ac.var<i64>
    %size = ac.var.constant 8 : i32 as !ac.var<i32>
    %transfer = ac.memory.read @dram %source size %size : !ac.var<i64>, !ac.var<i32> -> !ac.memory_transfer
    %destination = ac.var.constant 60 : i64 as !ac.var<i64>
    ac.memory.write @sram %destination data %transfer : !ac.var<i64>, !ac.memory_transfer
    ac.queue.process.yield %item : !ac.var<i8>
  } : !ac.queue<i8> -> !ac.queue<i8>
  ac.sink %output : !ac.queue<i8>
}
