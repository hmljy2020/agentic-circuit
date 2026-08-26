module attributes {ac.contract_epoch = "0.3", ac.system = "tma_dma_memory"} {
  ac.type_scope @types {
    ac.struct @DmaOp fields [{name = "src", type = i64}, {name = "dst", type = i64}, {name = "size", type = i32}, {name = "tag", type = i16}]
  } {dlti.dl_spec = #dlti.dl_spec<!ac.struct<@types::@DmaOp> = {abi_alignment = 8 : i64, endianness = "little", preferred_alignment = 8 : i64, size = 24 : i64}>}
  ac.memory.resource @dram kind "dram" capacity_bytes 1073741824 read_latency 40 write_latency 20 bytes_per_cycle 32
  ac.memory.resource @sram kind "sram" capacity_bytes 1048576 read_latency 2 write_latency 2 bytes_per_cycle 64
  %requests = ac.source depth 4 latency 1 {ac.name = "requests"} : !ac.queue<!ac.struct<@types::@DmaOp>>
  %completed = ac.scope @tma_engine(%requests) {
  ^body(%requests__in: !ac.queue<!ac.struct<@types::@DmaOp>>):
    %completed__local = ac.queue.process %requests__in inflight 1 depth 1 latency 1 {
    ^process(%item: !ac.var<!ac.struct<@types::@DmaOp>>):
      %pv0 = ac.var.get %item field "src" : !ac.var<!ac.struct<@types::@DmaOp>> -> !ac.var<i64>
      %pv1 = ac.var.get %item field "size" : !ac.var<!ac.struct<@types::@DmaOp>> -> !ac.var<i32>
      %completed__transfer = ac.memory.read @dram %pv0 size %pv1 : !ac.var<i64>, !ac.var<i32> -> !ac.memory_transfer
      %pv2 = ac.var.get %item field "dst" : !ac.var<!ac.struct<@types::@DmaOp>> -> !ac.var<i64>
      ac.memory.write @sram %pv2 data %completed__transfer : !ac.var<i64>, !ac.memory_transfer
      ac.queue.process.yield %item : !ac.var<!ac.struct<@types::@DmaOp>>
    } {ac.name = "completed"} : !ac.queue<!ac.struct<@types::@DmaOp>> -> !ac.queue<!ac.struct<@types::@DmaOp>>
    ac.scope.yield %completed__local : !ac.queue<!ac.struct<@types::@DmaOp>>
  } : (!ac.queue<!ac.struct<@types::@DmaOp>>) -> !ac.queue<!ac.struct<@types::@DmaOp>>
  ac.sink %completed {ac.name = "sink_6"} : !ac.queue<!ac.struct<@types::@DmaOp>>
}
