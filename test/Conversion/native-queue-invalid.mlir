// RUN: %split_file %s %t
// RUN: %acir_opt --verify-each=false --pass-pipeline='builtin.module(ac-freeze-topology)' %t/per-key.mlir -o %t/per-key.frozen
// RUN: %not %acir_opt --ac-lower-to-acsim --ac-binding-profile=fast --ac-binding-target=arm64-apple-darwin %t/per-key.frozen -o %t/per-key.lowered 2>&1 | %FileCheck %s --check-prefix=PER-KEY
// RUN: test ! -s %t/per-key.lowered
// RUN: %acir_opt_public --verify-each=false --pass-pipeline='builtin.module(ac-freeze-topology)' %t/watermarks.mlir -o %t/watermarks.frozen
// RUN: %not %acir_opt_public --ac-lower-to-acsim --ac-binding-profile=fast --ac-binding-target=arm64-apple-darwin %t/watermarks.frozen -o %t/watermarks.lowered 2>&1 | %FileCheck %s --check-prefix=WATERMARKS
// RUN: test ! -s %t/watermarks.lowered

// PER-KEY: ACLOWER-UNSUPPORTED-CONSTRUCT: native queues require ordering 'fifo'; per_key queues are not supported in v0.2
// WATERMARKS: ACLOWER-UNSUPPORTED-CONSTRUCT: configured queue watermarks are not supported in v0.2 lowering

//--- per-key.mlir
builtin.module attributes {ac.contract_epoch = "0.2"} {
  "ac.type_scope"() <{sym_name = "types"}> ({
    "ac.packet"() <{sym_name = "Tagged", fields = [
      {name = "tag", type = i32}, {name = "payload", type = i32}
    ]}> : () -> ()
  }) {dlti.dl_spec = #dlti.dl_spec<
    !ac.packet<@types::@Tagged> = {
      abi_alignment = 4 : i64, endianness = "little",
      preferred_alignment = 4 : i64, serialization_width = 8 : i64,
      size = 8 : i64
    }
  >} : () -> ()
  ac.protocol @p {
    ac.role @sender dual @receiver cardinality "exclusive"
    ac.role @receiver dual @sender cardinality "exclusive"
    ac.state @idle initial true terminal false
    ac.event @push from @sender to @receiver payload !ac.packet<@types::@Tagged>
        action "offer"
    ac.transition from @idle to @idle on @push transfer true retain false guard {}
    ac.guarantee "ordering" = "per_key"
    ac.guarantee "correlation" = "tag"
  }
  ac.system @soc root @Top as "root" tick 0 "cycle"
      workload @Top::@worker seed {kind = "fixed", value = 7 : i64}
      instrumentation [] results {id = "default", format = "json"} selected true
  ac.module @Top() parameters {} graph {
    ac.queue @q payload !ac.packet<@types::@Tagged> entries 4 ordering "per_key" protocol @p
        ownership "exclusive" id "q" path "q"
    ac.process @worker kind "workload" { ac.yield_sim }
    ac.return
  }
}

//--- watermarks.mlir
builtin.module attributes {ac.contract_epoch = "0.2"} {
  ac.protocol @p {
    ac.role @sender dual @receiver cardinality "exclusive"
    ac.role @receiver dual @sender cardinality "exclusive"
    ac.state @idle initial true terminal false
    ac.event @push from @sender to @receiver payload i32 action "offer"
    ac.transition from @idle to @idle on @push transfer true retain false guard {}
    ac.guarantee "ordering" = "fifo"
  }
  ac.system @soc root @Top as "root" tick 0 "cycle"
      workload @Top::@worker seed {kind = "fixed", value = 7 : i64}
      instrumentation [] results {id = "default", format = "json"} selected true
  ac.module @Top() parameters {} graph {
    ac.queue @q payload i32 entries 4 ordering "fifo" protocol @p
        ownership "exclusive" id "q" path "q"
        watermarks {low = 1 : i64, high = 3 : i64}
    ac.process @worker kind "workload" { ac.yield_sim }
    ac.return
  }
}
