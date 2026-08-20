// DESIGN SKETCH ONLY -- intentionally not accepted by the current ACIR parser.
//
// This file shows the desired RTL-lowerable representation of the scheduler in
// model.mlir.  It uses only two proposed Core operations:
//
//   * ac.arbitrate ... -> one ordinary i1 grant per candidate
//   * ac.try_transfer ...
//
// Existing ac.peek, ac.space, arith operations, queues, resources, processes,
// and ac.yield_sim retain their current meanings.  The proposed operations are
// deliberately explicit enough that neither ACSim nor an RTL backend needs to
// recognize a try_send -> try_recv -> assert idiom.
//
// One scheduler epoch has three phases:
//
//   Observe: read every input head and output free-space value from the same
//            committed queue snapshot.
//   Decide:  form pure requests, then compute one deterministic matching under
//            four capacity-1 physical-lane resources.
//   Commit:  issue one statically addressed atomic try_transfer per candidate;
//            grants from the common arbiter prove the operations exclusive.
//
// Candidate order is part of the hardware contract.  All A candidates precede
// all B candidates; within one class and output, physical input 0 precedes
// physical input 1.  The fixed-priority matching is combinational and owns no
// persistent arbitration state.

builtin.module attributes {
  ac.contract_epoch = "0.2",
  ac.design_status = "unsupported-rtl-ideal-sketch"
} {
  ac.protocol @fifo {
    ac.role @sender dual @receiver cardinality "exclusive"
    ac.role @receiver dual @sender cardinality "exclusive"
    ac.state @idle initial true terminal false
    ac.state @done initial false terminal true
    ac.event @push from @sender to @receiver payload i32 action "offer"
    ac.transition from @idle to @done on @push transfer true retain false guard {}
  }

  ac.module @CrossbarVC() parameters {} graph {
    // Logical VC queues.  Queue port counts are implicitly one read and one
    // write per epoch in this sketch; the RTL profile must make that default
    // explicit and verifiable.
    ac.queue @in0_A payload i32 entries 2 bytes 8 ordering "fifo"
        protocol @fifo ownership "exclusive" id "in0_A" path "in0_A"
    ac.queue @in0_B payload i32 entries 2 bytes 8 ordering "fifo"
        protocol @fifo ownership "exclusive" id "in0_B" path "in0_B"
    ac.queue @in1_A payload i32 entries 2 bytes 8 ordering "fifo"
        protocol @fifo ownership "exclusive" id "in1_A" path "in1_A"
    ac.queue @in1_B payload i32 entries 2 bytes 8 ordering "fifo"
        protocol @fifo ownership "exclusive" id "in1_B" path "in1_B"

    ac.queue @out0_A payload i32 entries 2 bytes 8 ordering "fifo"
        protocol @fifo ownership "exclusive" id "out0_A" path "out0_A"
    ac.queue @out0_B payload i32 entries 2 bytes 8 ordering "fifo"
        protocol @fifo ownership "exclusive" id "out0_B" path "out0_B"
    ac.queue @out1_A payload i32 entries 2 bytes 8 ordering "fifo"
        protocol @fifo ownership "exclusive" id "out1_A" path "out1_A"
    ac.queue @out1_B payload i32 entries 2 bytes 8 ordering "fifo"
        protocol @fifo ownership "exclusive" id "out1_B" path "out1_B"

    // These resources describe switch bandwidth, not additional buffering.
    // @pin0 is shared by in0_A/in0_B, @pin1 by in1_A/in1_B.  @pout0 is
    // shared by out0_A/out0_B, and @pout1 by out1_A/out1_B.  A candidate needs
    // one input lane and one output lane in the same epoch.
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
    ac.resource @pout1 capacity 1 issue_width 1 ii 1
        latency {kind = "fixed", ticks = 1 : i64}
        lifecycle {reservation = "propose_commit", release = "balanced", cancellation = "explicit"}
        ownership "exclusive" classes [] id "pout1" path "pout1"

    ac.process @scheduler kind "control" {
      // ------------------------------------------------------------------
      // OBSERVE: every value below comes from the committed epoch snapshot.
      // ------------------------------------------------------------------
      %h0a, %v0a = ac.peek @in0_A : i32
      %h0b, %v0b = ac.peek @in0_B : i32
      %h1a, %v1a = ac.peek @in1_A : i32
      %h1b, %v1b = ac.peek @in1_B : i32

      %space0a = ac.space @out0_A
      %space0b = ac.space @out0_B
      %space1a = ac.space @out1_A
      %space1b = ac.space @out1_B

      // ------------------------------------------------------------------
      // DECIDE (pure): decode routes and build the 8 request bits.
      // Flit bits [1:0] hold dst.  The VC class comes from the source queue,
      // so A queues can target only A output queues and likewise for B.
      // ------------------------------------------------------------------
      %c0 = arith.constant 0 : i32
      %c1 = arith.constant 1 : i32
      %dst_mask = arith.constant 3 : i32

      %dst0a = arith.andi %h0a, %dst_mask : i32
      %dst0b = arith.andi %h0b, %dst_mask : i32
      %dst1a = arith.andi %h1a, %dst_mask : i32
      %dst1b = arith.andi %h1b, %dst_mask : i32

      %dst0a_o0 = arith.cmpi eq, %dst0a, %c0 : i32
      %dst0a_o1 = arith.cmpi eq, %dst0a, %c1 : i32
      %dst0b_o0 = arith.cmpi eq, %dst0b, %c0 : i32
      %dst0b_o1 = arith.cmpi eq, %dst0b, %c1 : i32
      %dst1a_o0 = arith.cmpi eq, %dst1a, %c0 : i32
      %dst1a_o1 = arith.cmpi eq, %dst1a, %c1 : i32
      %dst1b_o0 = arith.cmpi eq, %dst1b, %c0 : i32
      %dst1b_o1 = arith.cmpi eq, %dst1b, %c1 : i32

      %w0a = arith.cmpi sgt, %space0a, %c0 : i32
      %w0b = arith.cmpi sgt, %space0b, %c0 : i32
      %w1a = arith.cmpi sgt, %space1a, %c0 : i32
      %w1b = arith.cmpi sgt, %space1b, %c0 : i32

      %a0_o0_valid = arith.andi %v0a, %dst0a_o0 : i1
      %req_a0_o0 = arith.andi %a0_o0_valid, %w0a : i1
      %a1_o0_valid = arith.andi %v1a, %dst1a_o0 : i1
      %req_a1_o0 = arith.andi %a1_o0_valid, %w0a : i1
      %a0_o1_valid = arith.andi %v0a, %dst0a_o1 : i1
      %req_a0_o1 = arith.andi %a0_o1_valid, %w1a : i1
      %a1_o1_valid = arith.andi %v1a, %dst1a_o1 : i1
      %req_a1_o1 = arith.andi %a1_o1_valid, %w1a : i1

      %b0_o0_valid = arith.andi %v0b, %dst0b_o0 : i1
      %req_b0_o0 = arith.andi %b0_o0_valid, %w0b : i1
      %b1_o0_valid = arith.andi %v1b, %dst1b_o0 : i1
      %req_b1_o0 = arith.andi %b1_o0_valid, %w0b : i1
      %b0_o1_valid = arith.andi %v0b, %dst0b_o1 : i1
      %req_b0_o1 = arith.andi %b0_o1_valid, %w1b : i1
      %b1_o1_valid = arith.andi %v1b, %dst1b_o1 : i1
      %req_b1_o1 = arith.andi %b1_o1_valid, %w1b : i1

      // PROPOSED OP.
      //
      // Greedily visits candidates in textual order.  It grants an active
      // candidate iff every listed capacity-1 resource is still available.
      // Therefore the result is simultaneously:
      //   * <= 1 grant using @pin0 and <= 1 using @pin1;
      //   * <= 1 grant using @pout0 and <= 1 using @pout1;
      //   * A-before-B;
      //   * lower-input-first for same-class/same-output contention.
      //
      // Each result is an ordinary i1, but it must be used directly as the
      // grant of its corresponding ac.try_transfer.  The defining op and
      // result number retain enough provenance for the verifier; a dedicated
      // !ac.grant_set type is unnecessary.
      %g0, %g1, %g2, %g3, %g4, %g5, %g6, %g7 =
        ac.arbitrate greedy_fixed_priority
          candidates [
            %req_a0_o0 uses [@pin0, @pout0],
            %req_a1_o0 uses [@pin1, @pout0],
            %req_a0_o1 uses [@pin0, @pout1],
            %req_a1_o1 uses [@pin1, @pout1],
            %req_b0_o0 uses [@pin0, @pout0],
            %req_b1_o0 uses [@pin1, @pout0],
            %req_b0_o1 uses [@pin0, @pout1],
            %req_b1_o1 uses [@pin1, @pout1]
          ]
          : (i1, i1, i1, i1, i1, i1, i1, i1)

      // ------------------------------------------------------------------
      // COMMIT: one static atomic transfer edge per candidate.
      // ------------------------------------------------------------------

      // PROPOSED OP.
      // fire = grant && source.readable && destination.writable.  On fire,
      // Xfer atomically pops the committed source head and pushes that exact
      // value to the destination; otherwise neither queue changes.  Since
      // candidates sharing any capacity-1 resource cannot both be granted,
      // the verifier can prove all eight effects mutually safe without
      // recognizing arbitrary Boolean or scf patterns.
      %f0 = ac.try_transfer @in0_A to @out0_A grant %g0 : i32
      %f1 = ac.try_transfer @in1_A to @out0_A grant %g1 : i32
      %f2 = ac.try_transfer @in0_A to @out1_A grant %g2 : i32
      %f3 = ac.try_transfer @in1_A to @out1_A grant %g3 : i32
      %f4 = ac.try_transfer @in0_B to @out0_B grant %g4 : i32
      %f5 = ac.try_transfer @in1_B to @out0_B grant %g5 : i32
      %f6 = ac.try_transfer @in0_B to @out1_B grant %g6 : i32
      %f7 = ac.try_transfer @in1_B to @out1_B grant %g7 : i32

      // %f0..%f7 are available to statistics or a future stateful arbiter
      // update.  Fixed priority has no state to update.
      ac.yield_sim
    }

    ac.return
  }
}
