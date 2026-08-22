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
    ac.resource @rr_pin0 capacity 1 issue_width 1 ii 1
        latency {kind = "fixed", ticks = 1 : i64}
        lifecycle {reservation = "propose_commit", release = "balanced", cancellation = "explicit"}
        ownership "exclusive" classes [] id "rr_pin0" path "rr_pin0"
    ac.resource @rr_pin1 capacity 1 issue_width 1 ii 1
        latency {kind = "fixed", ticks = 1 : i64}
        lifecycle {reservation = "propose_commit", release = "balanced", cancellation = "explicit"}
        ownership "exclusive" classes [] id "rr_pin1" path "rr_pin1"
    ac.resource @rr_pout0 capacity 1 issue_width 1 ii 1
        latency {kind = "fixed", ticks = 1 : i64}
        lifecycle {reservation = "propose_commit", release = "balanced", cancellation = "explicit"}
        ownership "exclusive" classes [] id "rr_pout0" path "rr_pout0"
    ac.process @scheduler kind "control" {
      %state = arith.constant 1 : i32
      %r0 = arith.constant true
      %r1 = arith.constant false
      %g0, %g1 = ac.arbitrate greedy_fixed_priority candidates [
        %r0 uses [@pin0, @pout0],
        %r1 uses [@pin1, @pout0]
      ] : (i1, i1)
      %rr0, %rr1, %next = ac.arbitrate round_robin state %state candidates [
        %r0 uses [@rr_pin0, @rr_pout0],
        %r1 uses [@rr_pin1, @rr_pout0]
      ] : (i32, i1, i1) -> (i1, i1, i32)
      ac.yield_sim
    }
    ac.return
  }
}

// CHECK: %[[R0:.+]] = arith.constant true
// CHECK: %[[R1:.+]] = arith.constant false
// CHECK: = ac.arbitrate greedy_fixed_priority candidates [%[[R0]] uses [@pin0, @pout0], %[[R1]] uses [@pin1, @pout0]] : (i1, i1)
// CHECK: = ac.arbitrate round_robin state {{%.+}} candidates [%[[R0]] uses [@rr_pin0, @rr_pout0], %[[R1]] uses [@rr_pin1, @rr_pout0]] : (i32, i1, i1) -> (i1, i1, i32)
