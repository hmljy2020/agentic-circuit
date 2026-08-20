// RUN: %acir_opt_public --verify-each=false --pass-pipeline='builtin.module(ac-freeze-topology)' %s -o %t.frozen
// RUN: %acir_opt_public --ac-lower-to-acsim --ac-binding-profile=fast --ac-binding-target=arm64-apple-darwin %t.frozen | %FileCheck %s

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
    ac.queue @d0 payload i32 entries 2 bytes 8 ordering "fifo"
        protocol @fifo ownership "exclusive" id "d0" path "d0"
    ac.queue @d1 payload i32 entries 2 bytes 8 ordering "fifo"
        protocol @fifo ownership "exclusive" id "d1" path "d1"
    ac.resource @input capacity 1 issue_width 1 ii 1
        latency {kind = "fixed", ticks = 1 : i64}
        lifecycle {reservation = "propose_commit", release = "balanced", cancellation = "explicit"}
        ownership "exclusive" classes [] id "input" path "input"
    ac.resource @out0 capacity 1 issue_width 1 ii 1
        latency {kind = "fixed", ticks = 1 : i64}
        lifecycle {reservation = "propose_commit", release = "balanced", cancellation = "explicit"}
        ownership "exclusive" classes [] id "out0" path "out0"
    ac.resource @out1 capacity 1 issue_width 1 ii 1
        latency {kind = "fixed", ticks = 1 : i64}
        lifecycle {reservation = "propose_commit", release = "balanced", cancellation = "explicit"}
        ownership "exclusive" classes [] id "out1" path "out1"
    ac.process @mover kind "workload" {
      %r0 = arith.constant true
      %r1 = arith.constant true
      %g0, %g1 = ac.arbitrate greedy_fixed_priority candidates [
        %r0 uses [@input, @out0],
        %r1 uses [@input, @out1]
      ] : (i1, i1)
      %f0 = ac.try_transfer @source to @d0 when %g0 : i32
      %f1 = ac.try_transfer @source to @d1 when %g1 : i32
      ac.yield_sim
    }
    ac.return
  }
}

// CHECK-NOT: ac.arbitrate
// CHECK-NOT: arbiter
// CHECK-NOT: acsim.binding
// CHECK: acsim.process @mover
// CHECK: arith.xori
// CHECK: arith.andi
// CHECK-COUNT-2: acsim.invoke @acir_impl_queue_try_transfer_{{[0-9a-f]+}}
