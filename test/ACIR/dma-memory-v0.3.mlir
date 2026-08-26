// RUN: %acir_opt %s | %FileCheck %s
// RUN: %acir_opt %s | %acir_opt | %FileCheck %s
// RUN: %acir_opt --emit-bytecode -o %t.bc %s
// RUN: %acir_opt %t.bc | %FileCheck %s

module attributes {ac.contract_epoch = "0.3"} {
  ac.memory.resource @dram kind "dram" capacity_bytes 4096 read_latency 40 write_latency 20 bytes_per_cycle 32
  ac.memory.resource @sram kind "sram" capacity_bytes 1024 read_latency 2 write_latency 2 bytes_per_cycle 64
  %input = ac.source depth 1 latency 1 : !ac.queue<i8>
  %output = ac.queue.process %input inflight 1 depth 1 latency 1 {
  ^process(%item: !ac.var<i8>):
    %source = ac.var.constant 64 : i64 as !ac.var<i64>
    %size = ac.var.constant 128 : i32 as !ac.var<i32>
    %transfer = ac.memory.read @dram %source size %size : !ac.var<i64>, !ac.var<i32> -> !ac.memory_transfer
    %destination = ac.var.constant 256 : i64 as !ac.var<i64>
    ac.memory.write @sram %destination data %transfer : !ac.var<i64>, !ac.memory_transfer
    ac.queue.process.yield %item : !ac.var<i8>
  } : !ac.queue<i8> -> !ac.queue<i8>
  ac.sink %output : !ac.queue<i8>
}

// CHECK: ac.memory.resource @dram kind "dram"
// CHECK: ac.memory.resource @sram kind "sram"
// CHECK: ac.queue.process
// CHECK: ac.memory.read @dram
// CHECK: ac.memory.write @sram
// CHECK: ac.queue.process.yield
