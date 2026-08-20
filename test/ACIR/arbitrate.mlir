// RUN: %acir_opt_public %s | %FileCheck %s

builtin.module attributes {ac.contract_epoch = "0.2"} {
  ac.module @Arbiter() parameters {} graph {
    ac.resource @pin0 capacity 1 issue_width 1 ii 1
        latency {kind = "fixed", ticks = 1 : i64}
        lifecycle {reservation = "propose_commit", release = "balanced", cancellation = "explicit"}
        ownership "exclusive" classes [] id "pin0" path "pin0"
    ac.resource @pin1 capacity 1 issue_width 1 ii 1
        latency {kind = "fixed", ticks = 1 : i64}
        lifecycle {reservation = "propose_commit", release = "balanced", cancellation = "explicit"}
        ownership "exclusive" classes [] id "pin1" path "pin1"
    ac.resource @pout0 capacity 1 issue_width 1 ii 1
        latency {kind = "fixed", ticks = 1 : i64}
        lifecycle {reservation = "propose_commit", release = "balanced", cancellation = "explicit"}
        ownership "exclusive" classes [] id "pout0" path "pout0"
    ac.process @scheduler kind "control" {
      %r0 = arith.constant true
      %r1 = arith.constant false
      %g0, %g1 = ac.arbitrate greedy_fixed_priority candidates [
        %r0 uses [@pin0, @pout0],
        %r1 uses [@pin1, @pout0]
      ] : (i1, i1)
      ac.yield_sim
    }
    ac.return
  }
}

// CHECK: %[[R0:.+]] = arith.constant true
// CHECK: %[[R1:.+]] = arith.constant false
// CHECK: = ac.arbitrate greedy_fixed_priority candidates [%[[R0]] uses [@pin0, @pout0], %[[R1]] uses [@pin1, @pout0]] : (i1, i1)
