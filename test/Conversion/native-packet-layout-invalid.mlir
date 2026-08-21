// RUN: %acir_opt --verify-each=false --pass-pipeline='builtin.module(ac-freeze-topology)' %s -o %t.frozen
// RUN: %not %acir_opt --ac-lower-to-acsim --ac-binding-profile=fast --ac-binding-target=x86_64-linux-gnu %t.frozen 2>&1 | %FileCheck %s

builtin.module attributes {ac.contract_epoch = "0.2"} {
  "ac.type_scope"() <{sym_name = "types"}> ({
    "ac.packet"() <{sym_name = "Bad", fields = [
      {name = "opcode", type = i8}, {name = "payload", type = i32}
    ]}> : () -> ()
  }) {dlti.dl_spec = #dlti.dl_spec<
    !ac.packet<@types::@Bad> = {
      abi_alignment = 4 : i64, endianness = "little",
      preferred_alignment = 4 : i64, serialization_width = 7 : i64,
      size = 7 : i64
    }
  >} : () -> ()
  ac.protocol @ready_valid {
    ac.role @sender dual @receiver cardinality "exclusive"
    ac.role @receiver dual @sender cardinality "exclusive"
    ac.state @idle initial true terminal false
    ac.state @done initial false terminal true
    ac.event @push from @sender to @receiver payload !ac.packet<@types::@Bad>
        action "offer"
    ac.transition from @idle to @done on @push transfer true retain false guard {}
  }
  ac.system @soc root @Top as "root" tick 0 "cycle"
      workload @Top::@worker seed {kind = "fixed", value = 7 : i64}
      instrumentation [] results {id = "default", format = "json"} selected true
  ac.module @Top() parameters {} graph {
    ac.queue @packets payload !ac.packet<@types::@Bad> entries 2 bytes 14
        ordering "fifo" protocol @ready_valid ownership "exclusive"
        id "packets" path "packets"
    ac.process @worker kind "workload" {
      ac.yield_sim
    }
    ac.return
  }
}

// CHECK: ACLOWER-TYPE-MISMATCH: native queue payload has no closed C++ realization
