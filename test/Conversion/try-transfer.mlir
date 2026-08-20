// RUN: %acir_opt_public %s | %FileCheck %s --check-prefix=ROUNDTRIP
// RUN: %acir_opt_public --verify-each=false --pass-pipeline='builtin.module(ac-freeze-topology)' %s -o %t.frozen
// RUN: %acir_opt_public --ac-lower-to-acsim --ac-binding-profile=fast --ac-binding-target=arm64-apple-darwin %t.frozen | %FileCheck %s --check-prefix=LOWER

builtin.module attributes {ac.contract_epoch = "0.2"} {
  ac.protocol @fifo {
    ac.role @sender dual @receiver cardinality "exclusive"
    ac.role @receiver dual @sender cardinality "exclusive"
    ac.state @idle initial true terminal false
    ac.state @done initial false terminal true
    ac.event @push from @sender to @receiver payload i32 action "offer"
    ac.transition from @idle to @done on @push transfer true retain false guard {}
  }
  ac.system @soc root @Top as "root" tick 0 "cycle"
      workload @Top::@mover seed {kind = "fixed", value = 7 : i64}
      instrumentation [] results {id = "default", format = "json"} selected true
  ac.module @Top() parameters {} graph {
    ac.queue @source payload i32 entries 2 bytes 8 ordering "fifo"
        protocol @fifo ownership "exclusive" id "source" path "source"
    ac.queue @destination payload i32 entries 2 bytes 8 ordering "fifo"
        protocol @fifo ownership "exclusive" id "destination" path "destination"
    ac.queue @source2 payload i32 entries 2 bytes 8 ordering "fifo"
        protocol @fifo ownership "exclusive" id "source2" path "source2"
    ac.queue @destination2 payload i32 entries 2 bytes 8 ordering "fifo"
        protocol @fifo ownership "exclusive" id "destination2" path "destination2"
    ac.process @mover kind "workload" {
      %enable = arith.constant true
      %fire = ac.try_transfer @source to @destination when %enable : i32
      %fire2 = ac.try_transfer @source2 to @destination2 when %enable : i32
      ac.yield_sim
    }
    ac.return
  }
}

// ROUNDTRIP: %[[ENABLE:.+]] = arith.constant true
// ROUNDTRIP: %{{.+}} = ac.try_transfer @source to @destination when %[[ENABLE]] : i32
// ROUNDTRIP: %{{.+}} = ac.try_transfer @source2 to @destination2 when %[[ENABLE]] : i32
// LOWER-COUNT-1: acsim.type @acir_impl_queue_try_transfer_{{[0-9a-f]+}} cpp "acir::generated::impl_queue_try_transfer_{{[0-9a-f]+}}" kind "implementation"
// LOWER-NOT: acsim.binding
// LOWER: %[[DESTINATION:.+]] = acsim.instance @destination target @[[QUEUE:acir_queue_[0-9a-f]+]]
// LOWER: %[[SOURCE:.+]] = acsim.instance @source target @[[QUEUE]]
// LOWER: acsim.process @mover
// LOWER-COUNT-2: acsim.invoke @acir_impl_queue_try_transfer_{{[0-9a-f]+}}(%{{.+}}, %{{.+}}, %{{.+}}) : (!acsim.owner<@[[QUEUE]]>, !acsim.owner<@[[QUEUE]]>, i1) -> i1
