// Scenario sc03 (test 3): A beats B on the same input and destination.
// in0_A (vc A) and in0_B (vc B) both carry a flit destined for out0, and both
// output VCs are empty, so in the first competing cycle (epoch 1) exactly one
// transfer happens and it is A's: the scheduler runs the A phase first, and
// the per-input/per-output rules block B while A holds the resources.
//
// A sink drains out0_A, so A keeps returning to eligibility and dominates the
// bandwidth (3 transfers to B's 1 over six ticks). B moves only in the cycle
// after an A grant, when out0_A is full -- a single depth-1 destination VC
// keeps A off the input for one tick -- which is the bandwidth-reuse behavior
// of test 5, not a priority failure: strict A > B decides every simultaneous
// contention, and the sink self-checks that out0_A only ever carries A flits.
//
// Expected: epoch-1 completed == 1 (single grant, the A flit), and over the run
// in0_A.completed (3) > in0_B.completed (1), out0_A.accepted == 3,
// out0_B.accepted == 1. Flits: A = dst0 vc0 src0 seq0 (value 0);
// B = dst0 vc1 src0 seq0 (value 4100).

builtin.module attributes {ac.contract_epoch = "0.2"} {
  ac.protocol @fifo {
    ac.role @sender dual @receiver cardinality "exclusive"
    ac.role @receiver dual @sender cardinality "exclusive"
    ac.state @idle initial true terminal false
    ac.state @done initial false terminal true
    ac.event @push from @sender to @receiver payload i32 action "offer"
    ac.transition from @idle to @done on @push transfer true retain false guard {}
  }

  ac.system @sc03_demo root @Crossbar as "root" tick 0 "cycle"
      workload @Crossbar::@producer0 seed {kind = "fixed", value = 0 : i64}
      instrumentation [] results {id = "default", format = "json"} selected true

  ac.module @Crossbar() parameters {} graph {
    ac.queue @in0_A payload i32 entries 2 bytes 8 ordering "fifo"
        protocol @fifo ownership "exclusive" id "in0_A" path "in0_A"
    ac.queue @in0_B payload i32 entries 2 bytes 8 ordering "fifo"
        protocol @fifo ownership "exclusive" id "in0_B" path "in0_B"
    // out0_A is depth 1. A sink drains it, but only one tick after each grant:
    // the sink's same-cycle pop is a proposal rejected against the committed
    // (empty) queue -- pending pushes are invisible until Xfer -- so a depth-1
    // destination keeps A off the input for one tick after every grant. That
    // is the bandwidth-reuse window test 5 explores; here it caps A's edge.
    ac.queue @out0_A payload i32 entries 1 bytes 4 ordering "fifo"
        protocol @fifo ownership "exclusive" id "out0_A" path "out0_A"
    ac.queue @out0_B payload i32 entries 1 bytes 4 ordering "fifo"
        protocol @fifo ownership "exclusive" id "out0_B" path "out0_B"

    // A -> in0_A (dst0 vcA), B -> in0_B (dst0 vcB). Same physical input 0.
    ac.process @producer0 kind "workload" {
      %a = arith.constant 0 : i32
      %acc_a = ac.try_send @in0_A %a : i32
      %b = arith.constant 4100 : i32
      %acc_b = ac.try_send @in0_B %b : i32
      ac.yield_sim
    }

    ac.process @scheduler kind "control" {
      %h0a, %v0a = ac.peek @in0_A : i32
      %h0b, %v0b = ac.peek @in0_B : i32
      %o0a, %f0a = ac.peek @out0_A : i32
      %o0b, %f0b = ac.peek @out0_B : i32
      %c0 = arith.constant 0 : i32
      %c3 = arith.constant 3 : i32
      %true = arith.constant true
      %w0a = arith.xori %f0a, %true : i1
      %w0b = arith.xori %f0b, %true : i1
      %d0a = arith.andi %h0a, %c3 : i32
      %d0b = arith.andi %h0b, %c3 : i32
      %d0a_is0 = arith.cmpi eq, %d0a, %c0 : i32
      %d0b_is0 = arith.cmpi eq, %d0b, %c0 : i32
      %ea_a = arith.andi %v0a, %w0a : i1
      %ea = arith.andi %ea_a, %d0a_is0 : i1
      // A grants consume physical input 0 and physical output 0.
      %in0_free = arith.xori %ea, %true : i1
      %out0_free = arith.xori %ea, %true : i1
      // B eligible only if the physical input AND physical output are free.
      %eb_a = arith.andi %v0b, %in0_free : i1
      %eb_b = arith.andi %eb_a, %out0_free : i1
      %eb_c = arith.andi %eb_b, %w0b : i1
      %eb = arith.andi %eb_c, %d0b_is0 : i1
      // per-input rule asserted in-model: A and B cannot both leave input 0.
      %two_in = arith.andi %ea, %eb : i1
      %two_in_ok = arith.xori %two_in, %true : i1
      ac.assert %two_in_ok, "sc03: at most one flit per physical input"
      scf.if %ea {
        %s0 = ac.try_send @out0_A %h0a : i32
        ac.assert %s0, "sc03: A send must be accepted"
        scf.if %s0 {
          %v0, %g0 = ac.try_recv @in0_A : i32
          ac.assert %g0, "sc03: A grant must receive"
          %m0 = arith.cmpi eq, %v0, %h0a : i32
          ac.assert %m0, "sc03: A receive must match peek"
        }
      }
      scf.if %eb {
        %s0 = ac.try_send @out0_B %h0b : i32
        ac.assert %s0, "sc03: B send must be accepted"
        scf.if %s0 {
          %v0, %g0 = ac.try_recv @in0_B : i32
          ac.assert %g0, "sc03: B grant must receive"
          %m0 = arith.cmpi eq, %v0, %h0b : i32
          ac.assert %m0, "sc03: B receive must match peek"
        }
      }
      ac.yield_sim
    }

    // Sink: drains out0_A (one tick after each arrival, once the flit is
    // committed) and self-checks the A flit header -- dst 0, VC A, src 0,
    // payload == seq*97 + src + vc*16 == 0. This proves out0_A only ever
    // carries A flits: the epoch-1 transfer, which resolves the contention,
    // is this queue's first arrival.
    ac.process @sink0 kind "control" {
      %flit, %got = ac.try_recv @out0_A : i32
      scf.if %got {
        %c0 = arith.constant 0 : i32
        %c1 = arith.constant 1 : i32
        %c2 = arith.constant 2 : i32
        %c3 = arith.constant 3 : i32
        %c4 = arith.constant 4 : i32
        %c8 = arith.constant 8 : i32
        %c15 = arith.constant 15 : i32
        %c97 = arith.constant 97 : i32
        %c16 = arith.constant 16 : i32
        %dst = arith.andi %flit, %c3 : i32
        %dst_ok = arith.cmpi eq, %dst, %c0 : i32
        ac.assert %dst_ok, "sc03: out0_A flit destination must be 0"
        %sh2 = arith.shrui %flit, %c2 : i32
        %vc = arith.andi %sh2, %c1 : i32
        %vc_ok = arith.cmpi eq, %vc, %c0 : i32
        ac.assert %vc_ok, "sc03: out0_A flit must be VC A"
        %sh3 = arith.shrui %flit, %c3 : i32
        %src = arith.andi %sh3, %c1 : i32
        %src_ok = arith.cmpi eq, %src, %c0 : i32
        ac.assert %src_ok, "sc03: out0_A flit must come from src 0"
        %sh4 = arith.shrui %flit, %c4 : i32
        %seq = arith.andi %sh4, %c15 : i32
        %payload = arith.shrui %flit, %c8 : i32
        %prod = arith.muli %seq, %c97 : i32
        %exp = arith.addi %prod, %src : i32
        %pay_ok = arith.cmpi eq, %payload, %exp : i32
        ac.assert %pay_ok, "sc03: out0_A flit payload must equal seq*97 + src + vc*16"
      }
      ac.yield_sim
    }

    ac.return
  }
}
