// RUN: %split_file %s %t
// RUN: %not %acir_opt %t/fork-non-queue.mlir 2>&1 | %FileCheck %s --check-prefix=FORK-TYPE
// RUN: %not %acir_opt %t/merge-non-queue.mlir 2>&1 | %FileCheck %s --check-prefix=MERGE-TYPE
// RUN: %not %acir_opt %t/route-cardinality.mlir 2>&1 | %FileCheck %s --check-prefix=ROUTE-ARITY
// RUN: %not %acir_opt %t/queue-payload.mlir 2>&1 | %FileCheck %s --check-prefix=QUEUE-PAYLOAD
// RUN: %not %acir_opt %t/queue-epoch.mlir 2>&1 | %FileCheck %s --check-prefix=QUEUE-EPOCH

//--- fork-non-queue.mlir
builtin.module attributes {ac.contract_epoch = "0.3"} {
  ac.module @m() parameters {} graph {
    %source = ac.source "input" : !ac.queue<i1, #ac.queue_contract<depth = 1, latency = 1, rate = 1, domain = @core, ordering = fifo>>
    %bad = ac.fork %source : (!ac.queue<i1, #ac.queue_contract<depth = 1, latency = 1, rate = 1, domain = @core, ordering = fifo>>) -> (i32)
    ac.return
  }
}
// FORK-TYPE: fork output must have !ac.queue type

//--- merge-non-queue.mlir
builtin.module attributes {ac.contract_epoch = "0.3"} {
  ac.module @m() parameters {} graph {
    %source = ac.source "input" : !ac.queue<i1, #ac.queue_contract<depth = 1, latency = 1, rate = 1, domain = @core, ordering = fifo>>
    %bad = ac.merge (%source) policy (#ac.policy<kind = round_robin>) : (!ac.queue<i1, #ac.queue_contract<depth = 1, latency = 1, rate = 1, domain = @core, ordering = fifo>>) -> i32
    ac.return
  }
}
// MERGE-TYPE: output must have !ac.queue type

//--- route-cardinality.mlir
builtin.module attributes {ac.contract_epoch = "0.3"} {
  ac.type_scope @types {
    ac.struct @Packet fields [{name = "kind", type = i1}]
  } {dlti.dl_spec = #dlti.dl_spec<
    !ac.struct<@types::@Packet> = {abi_alignment = 1 : i64, endianness = "little", preferred_alignment = 1 : i64, size = 1 : i64}
  >}
  ac.module @m() parameters {} graph {
    %source = ac.source "input" : !ac.queue<!ac.struct<@types::@Packet>, #ac.queue_contract<depth = 1, latency = 1, rate = 1, domain = @core, ordering = fifo>>
    %bad = ac.route %source by (#ac.field<root = !ac.struct<@types::@Packet>, path = ["kind"], leaf = i1>) : (!ac.queue<!ac.struct<@types::@Packet>, #ac.queue_contract<depth = 1, latency = 1, rate = 1, domain = @core, ordering = fifo>>) -> (!ac.queue<!ac.struct<@types::@Packet>, #ac.queue_contract<depth = 1, latency = 1, rate = 1, domain = @core, ordering = fifo>>)
    ac.return
  }
}
// ROUTE-ARITY: direct-index route requires 2 outputs for selector width 1

//--- queue-payload.mlir
builtin.module attributes {ac.contract_epoch = "0.3"} {
  ac.module @m() parameters {} graph {
    %source = ac.source "input" : !ac.queue<i1, #ac.queue_contract<depth = 1, latency = 1, rate = 1, domain = @core, ordering = fifo>>
    %bad = ac.queue %source : !ac.queue<i1, #ac.queue_contract<depth = 1, latency = 1, rate = 1, domain = @core, ordering = fifo>> -> !ac.queue<i32, #ac.queue_contract<depth = 2, latency = 1, rate = 1, domain = @core, ordering = fifo>>
    ac.return
  }
}
// QUEUE-PAYLOAD: transport must preserve Queue payload type

//--- queue-epoch.mlir
builtin.module attributes {ac.contract_epoch = "0.1"} {
  ac.module @m(!ac.queue<i1, #ac.queue_contract<depth = 1, latency = 1, rate = 1, domain = @core, ordering = fifo>>) parameters {} graph {
  ^bb0(%source : !ac.queue<i1, #ac.queue_contract<depth = 1, latency = 1, rate = 1, domain = @core, ordering = fifo>>):
    %bad = ac.queue %source : !ac.queue<i1, #ac.queue_contract<depth = 1, latency = 1, rate = 1, domain = @core, ordering = fifo>> -> !ac.queue<i1, #ac.queue_contract<depth = 2, latency = 1, rate = 1, domain = @core, ordering = fifo>>
    ac.return
  }
}
// QUEUE-EPOCH: transport form is only legal in contract_epoch 0.3
