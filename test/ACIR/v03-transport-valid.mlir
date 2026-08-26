// RUN: %acir_opt %s | %FileCheck %s
// RUN: %acir_opt %s | %acir_opt | %FileCheck %s
// RUN: %acir_opt --emit-bytecode -o %t.bc %s
// RUN: %acir_opt %t.bc | %FileCheck %s

!packet_q = !ac.queue<!ac.struct<@types::@Packet>, #ac.queue_contract<depth = 1, latency = 1, rate = 1, domain = @core, ordering = fifo>>

builtin.module attributes {ac.contract_epoch = "0.3"} {
  ac.type_scope @types {
    ac.struct @Packet fields [{name = "kind", type = i1}]
  } {dlti.dl_spec = #dlti.dl_spec<
    !ac.struct<@types::@Packet> = {abi_alignment = 1 : i64, endianness = "little", preferred_alignment = 1 : i64, size = 1 : i64}
  >}
  ac.system @s root @m as "m" tick 0 "cycle" seed {kind = "fixed", value = 0 : i64} instrumentation [] results {id = "default", format = "json"} selected true
  ac.module @m() parameters {} graph {
    %source = ac.source "input" : !packet_q
    %lane:2 = ac.route %source by (#ac.field<root = !ac.struct<@types::@Packet>, path = ["kind"], leaf = i1>) : (!packet_q) -> (!packet_q, !packet_q)
    %joined = ac.merge (%lane#0, %lane#1) policy (#ac.policy<kind = round_robin>) : (!packet_q, !packet_q) -> !packet_q
    %copy:2 = ac.fork %joined : (!packet_q) -> (!packet_q, !packet_q)
    ac.observe %copy#0 as "copy0" fields [] : !packet_q
    ac.observe %copy#1 as "copy1" fields [] : !packet_q
    ac.return
  }
}

// CHECK: #ac.field<root = !ac.struct<@types::@Packet>, path = ["kind"], leaf = i1>
// CHECK: #ac.policy<kind = round_robin>
// CHECK: ac.route
// CHECK: ac.merge
// CHECK: ac.fork
