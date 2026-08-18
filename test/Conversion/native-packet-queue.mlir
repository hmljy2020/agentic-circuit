// RUN: %acir_opt --verify-each=false --pass-pipeline='builtin.module(ac-freeze-topology)' %s -o %t.frozen
// RUN: %acir_opt --ac-lower-to-acsim --ac-binding-profile=fast --ac-binding-target=arm64-apple-darwin %t.frozen | %FileCheck %s

builtin.module attributes {ac.contract_epoch = "0.2"} {
  "ac.type_scope"() <{sym_name = "types"}> ({
    "ac.packet"() <{sym_name = "Request", fields = [
      {name = "opcode", type = i8}, {name = "payload", type = i32}
    ]}> : () -> ()
  }) {dlti.dl_spec = #dlti.dl_spec<
    !ac.packet<@types::@Request> = {
      abi_alignment = 4 : i64, endianness = "little",
      preferred_alignment = 4 : i64, serialization_width = 8 : i64,
      size = 8 : i64
    }
  >} : () -> ()
  ac.protocol @fifo {
    ac.role @sender dual @receiver cardinality "exclusive"
    ac.role @receiver dual @sender cardinality "exclusive"
    ac.state @idle initial true terminal false
    ac.state @done initial false terminal true
    ac.event @push from @sender to @receiver payload !ac.packet<@types::@Request>
        action "offer"
    ac.transition from @idle to @done on @push transfer true retain false guard {}
  }
  ac.system @soc root @Top as "root" tick 0 "cycle"
      workload @Top::@worker seed {kind = "fixed", value = 7 : i64}
      instrumentation [] results {id = "default", format = "json"} selected true
  ac.module @Top() parameters {} graph {
    ac.queue @packets payload !ac.packet<@types::@Request> entries 2 bytes 16
        ordering "fifo" protocol @fifo ownership "exclusive"
        id "packets" path "packets"
    ac.process @worker kind "workload" { ac.yield_sim }
    ac.return
  }
}

// CHECK: acsim.type @acir_queue_{{[0-9a-f]+}} cpp "gfsim::Queue<std::array<std::byte, 8>>" kind "runtime_object"
// CHECK-NOT: acsim.binding
// CHECK: acsim.instance @packets target @acir_queue_{{[0-9a-f]+}} args [2, 16]
