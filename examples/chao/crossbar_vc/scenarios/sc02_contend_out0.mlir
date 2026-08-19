// Scenario sc02 (test 2): two inputs contend for the same output.
// in0_A and in1_A both carry an A flit destined for out0. The scheduler must
// grant exactly ONE of them (lower input index wins: in0_A). in1_A's flit
// stays queued forever because out0_A fills and is never drained (no sink).
//
// Expected: in0_A.completed == 1, in1_A.completed == 0, out0_A.accepted == 1.
// The flits encode dst0/vcA and payload == seq*97 + src, so the sink-side
// identity checks are not needed here (no sink) -- the runner counts decide.

builtin.module attributes {ac.contract_epoch = "0.2"} {
  ac.protocol @fifo {
    ac.role @sender dual @receiver cardinality "exclusive"
    ac.role @receiver dual @sender cardinality "exclusive"
    ac.state @idle initial true terminal false
    ac.state @done initial false terminal true
    ac.event @push from @sender to @receiver payload i32 action "offer"
    ac.transition from @idle to @done on @push transfer true retain false guard {}
  }

  ac.system @sc02_demo root @Crossbar as "root" tick 0 "cycle"
      workload @Crossbar::@producer0 seed {kind = "fixed", value = 0 : i64}
      instrumentation [] results {id = "default", format = "json"} selected true

  ac.module @Crossbar() parameters {} graph {
    ac.queue @in0_A payload i32 entries 2 bytes 8 ordering "fifo"
        protocol @fifo ownership "exclusive" id "in0_A" path "in0_A"
    ac.queue @in1_A payload i32 entries 2 bytes 8 ordering "fifo"
        protocol @fifo ownership "exclusive" id "in1_A" path "in1_A"
    ac.queue @out0_A payload i32 entries 1 bytes 4 ordering "fifo"
        protocol @fifo ownership "exclusive" id "out0_A" path "out0_A"

    // in0_A: A flit, dst0, vc0, src0, seq0 -> value 0.
    ac.process @producer0 kind "workload" {
      %a = arith.constant 0 : i32
      %acc = ac.try_send @in0_A %a : i32
      ac.yield_sim
    }
    // in1_A: A flit, dst0, vc0, src1, seq1 -> value 0 | 1<<3 | 1<<4 | 113<<8.
    ac.process @producer1 kind "workload" {
      %a = arith.constant 25112 : i32
      %acc = ac.try_send @in1_A %a : i32
      ac.yield_sim
    }

    // Scheduler: 2 inputs, 1 output. Lower input index wins the output.
    ac.process @scheduler kind "control" {
      %h0a, %v0a = ac.peek @in0_A : i32
      %h1a, %v1a = ac.peek @in1_A : i32
      %o0a, %f0a = ac.peek @out0_A : i32
      %c0 = arith.constant 0 : i32
      %c3 = arith.constant 3 : i32
      %true = arith.constant true
      %w0a = arith.xori %f0a, %true : i1
      %d0a = arith.andi %h0a, %c3 : i32
      %d1a = arith.andi %h1a, %c3 : i32
      %d0a_is0 = arith.cmpi eq, %d0a, %c0 : i32
      %d1a_is0 = arith.cmpi eq, %d1a, %c0 : i32
      %ea0_a = arith.andi %v0a, %w0a : i1
      %ea0 = arith.andi %ea0_a, %d0a_is0 : i1
      %ea1_a = arith.andi %v1a, %w0a : i1
      %ea1 = arith.andi %ea1_a, %d1a_is0 : i1
      // per-output rule: in1_A->out0 only if in0_A is not taking it.
      %not_ea0 = arith.xori %ea0, %true : i1
      %g1 = arith.andi %ea1, %not_ea0 : i1
      // assert: at most one grant to out0_A this cycle.
      %both = arith.andi %ea0, %g1 : i1
      %both_ok = arith.xori %both, %true : i1
      ac.assert %both_ok, "sc02: at most one grant to out0"
      scf.if %ea0 {
        %s0 = ac.try_send @out0_A %h0a : i32
        ac.assert %s0, "sc02: in0_A send must be accepted"
        scf.if %s0 {
          %v0, %g0 = ac.try_recv @in0_A : i32
          ac.assert %g0, "sc02: in0_A grant must receive"
          %m0 = arith.cmpi eq, %v0, %h0a : i32
          ac.assert %m0, "sc02: in0_A receive must match peek"
        }
      }
      scf.if %g1 {
        %s0 = ac.try_send @out0_A %h1a : i32
        ac.assert %s0, "sc02: in1_A send must be accepted"
        scf.if %s0 {
          %v0, %g0 = ac.try_recv @in1_A : i32
          ac.assert %g0, "sc02: in1_A grant must receive"
          %m0 = arith.cmpi eq, %v0, %h1a : i32
          ac.assert %m0, "sc02: in1_A receive must match peek"
        }
      }
      ac.yield_sim
    }

    ac.return
  }
}
