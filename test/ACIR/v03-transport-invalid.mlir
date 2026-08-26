// RUN: %split_file %s %t
// RUN: %not %acir_opt %t/fork-non-queue.mlir 2>&1 | %FileCheck %s --check-prefix=FORK-TYPE
// RUN: %not %acir_opt %t/merge-non-queue.mlir 2>&1 | %FileCheck %s --check-prefix=MERGE-TYPE
// RUN: %not %acir_opt %t/route-cardinality.mlir 2>&1 | %FileCheck %s --check-prefix=ROUTE-ARITY
// RUN: %not %acir_opt %t/queue-payload.mlir 2>&1 | %FileCheck %s --check-prefix=QUEUE-PAYLOAD
// RUN: %not %acir_opt %t/queue-epoch.mlir 2>&1 | %FileCheck %s --check-prefix=QUEUE-EPOCH
// RUN: %not %acir_opt %t/fork-payload.mlir 2>&1 | %FileCheck %s --check-prefix=FORK-PAYLOAD
// RUN: %not %acir_opt %t/merge-payload.mlir 2>&1 | %FileCheck %s --check-prefix=MERGE-PAYLOAD
// RUN: %not %acir_opt %t/route-field-path.mlir 2>&1 | %FileCheck %s --check-prefix=ROUTE-PATH

//--- fork-non-queue.mlir
builtin.module attributes {ac.contract_epoch = "0.3"} {
  ac.module @m() parameters {} graph {
    %source = ac.v03.source "input" : !ac.queue_v03<i1, #ac.queue_contract<depth = 1, latency = 1, rate = 1, domain = @core, ordering = fifo>>
    %bad = ac.v03.fork %source : (!ac.queue_v03<i1, #ac.queue_contract<depth = 1, latency = 1, rate = 1, domain = @core, ordering = fifo>>) -> (i32)
    ac.return
  }
}
// FORK-TYPE: fork output must have !ac.queue type

//--- merge-non-queue.mlir
builtin.module attributes {ac.contract_epoch = "0.3"} {
  ac.module @m() parameters {} graph {
    %source = ac.v03.source "input" : !ac.queue_v03<i1, #ac.queue_contract<depth = 1, latency = 1, rate = 1, domain = @core, ordering = fifo>>
    %bad = ac.v03.merge (%source) policy (#ac.policy<kind = round_robin>) : (!ac.queue_v03<i1, #ac.queue_contract<depth = 1, latency = 1, rate = 1, domain = @core, ordering = fifo>>) -> i32
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
    %source = ac.v03.source "input" : !ac.queue_v03<!ac.struct<@types::@Packet>, #ac.queue_contract<depth = 1, latency = 1, rate = 1, domain = @core, ordering = fifo>>
    %bad = ac.v03.route %source by (#ac.field<root = !ac.struct<@types::@Packet>, path = ["kind"], leaf = i1>) : (!ac.queue_v03<!ac.struct<@types::@Packet>, #ac.queue_contract<depth = 1, latency = 1, rate = 1, domain = @core, ordering = fifo>>) -> (!ac.queue_v03<!ac.struct<@types::@Packet>, #ac.queue_contract<depth = 1, latency = 1, rate = 1, domain = @core, ordering = fifo>>)
    ac.return
  }
}
// ROUTE-ARITY: direct-index route requires 2 outputs for selector width 1

//--- queue-payload.mlir
builtin.module attributes {ac.contract_epoch = "0.3"} {
  ac.module @m() parameters {} graph {
    %source = ac.v03.source "input" : !ac.queue_v03<i1, #ac.queue_contract<depth = 1, latency = 1, rate = 1, domain = @core, ordering = fifo>>
    %bad = ac.queue %source : !ac.queue_v03<i1, #ac.queue_contract<depth = 1, latency = 1, rate = 1, domain = @core, ordering = fifo>> -> !ac.queue_v03<i32, #ac.queue_contract<depth = 2, latency = 1, rate = 1, domain = @core, ordering = fifo>>
    ac.return
  }
}
// QUEUE-PAYLOAD: transport must preserve Queue payload type

//--- queue-epoch.mlir
builtin.module attributes {ac.contract_epoch = "0.1"} {
  ac.module @m(!ac.queue_v03<i1, #ac.queue_contract<depth = 1, latency = 1, rate = 1, domain = @core, ordering = fifo>>) parameters {} graph {
  ^bb0(%source : !ac.queue_v03<i1, #ac.queue_contract<depth = 1, latency = 1, rate = 1, domain = @core, ordering = fifo>>):
    %bad = ac.queue %source : !ac.queue_v03<i1, #ac.queue_contract<depth = 1, latency = 1, rate = 1, domain = @core, ordering = fifo>> -> !ac.queue_v03<i1, #ac.queue_contract<depth = 2, latency = 1, rate = 1, domain = @core, ordering = fifo>>
    ac.return
  }
}
// QUEUE-EPOCH: transport form is only legal in contract_epoch 0.3

//--- fork-payload.mlir
// A fork broadcasts one payload identity; changing a branch payload is not a cast.
builtin.module attributes {ac.contract_epoch = "0.3"} {
  ac.module @m() parameters {} graph {
    %source = ac.v03.source "input" : !ac.queue_v03<i1, #ac.queue_contract<depth = 1, latency = 1, rate = 1, domain = @core, ordering = fifo>>
    %bad = ac.v03.fork %source : (!ac.queue_v03<i1, #ac.queue_contract<depth = 1, latency = 1, rate = 1, domain = @core, ordering = fifo>>) -> (!ac.queue_v03<i32, #ac.queue_contract<depth = 1, latency = 1, rate = 1, domain = @core, ordering = fifo>>)
    ac.return
  }
}
// FORK-PAYLOAD: fork output Queue payload must be 'i1' but received 'i32'

//--- merge-payload.mlir
// A variadic merge arbitrates equivalent tokens; heterogeneous payloads are illegal.
builtin.module attributes {ac.contract_epoch = "0.3"} {
  ac.module @m() parameters {} graph {
    %left = ac.v03.source "left" : !ac.queue_v03<i1, #ac.queue_contract<depth = 1, latency = 1, rate = 1, domain = @core, ordering = fifo>>
    %right = ac.v03.source "right" : !ac.queue_v03<i32, #ac.queue_contract<depth = 1, latency = 1, rate = 1, domain = @core, ordering = fifo>>
    %bad = ac.v03.merge (%left, %right) policy (#ac.policy<kind = round_robin>) : (!ac.queue_v03<i1, #ac.queue_contract<depth = 1, latency = 1, rate = 1, domain = @core, ordering = fifo>>, !ac.queue_v03<i32, #ac.queue_contract<depth = 1, latency = 1, rate = 1, domain = @core, ordering = fifo>>) -> !ac.queue_v03<i1, #ac.queue_contract<depth = 1, latency = 1, rate = 1, domain = @core, ordering = fifo>>
    ac.return
  }
}
// MERGE-PAYLOAD: merge input Queue payload must be 'i1' but received 'i32'

//--- route-field-path.mlir
// Typed selectors resolve their full declaration path; strings are not hints.
builtin.module attributes {ac.contract_epoch = "0.3"} {
  ac.type_scope @types {
    ac.struct @Packet fields [{name = "kind", type = i1}]
  } {dlti.dl_spec = #dlti.dl_spec<
    !ac.struct<@types::@Packet> = {abi_alignment = 1 : i64, endianness = "little", preferred_alignment = 1 : i64, size = 1 : i64}
  >}
  ac.module @m() parameters {} graph {
    %source = ac.v03.source "input" : !ac.queue_v03<!ac.struct<@types::@Packet>, #ac.queue_contract<depth = 1, latency = 1, rate = 1, domain = @core, ordering = fifo>>
    %bad:2 = ac.v03.route %source by (#ac.field<root = !ac.struct<@types::@Packet>, path = ["missing"], leaf = i1>) : (!ac.queue_v03<!ac.struct<@types::@Packet>, #ac.queue_contract<depth = 1, latency = 1, rate = 1, domain = @core, ordering = fifo>>) -> (!ac.queue_v03<!ac.struct<@types::@Packet>, #ac.queue_contract<depth = 1, latency = 1, rate = 1, domain = @core, ordering = fifo>>, !ac.queue_v03<!ac.struct<@types::@Packet>, #ac.queue_contract<depth = 1, latency = 1, rate = 1, domain = @core, ordering = fifo>>)
    ac.return
  }
}
// ROUTE-PATH: selector field path/leaf does not resolve exactly
