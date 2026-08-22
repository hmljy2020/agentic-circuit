// Scenario sc04 (test 4): B moves even when there is no eligible A flit.
// Only in0_B carries a flit (dst0); in0_A is present but empty, so no A
// eligibility ever holds. The B phase must pick it up and route it to out0_B.
//
// Expected: in0_B.completed == 1, out0_B.accepted == 1, in0_A.completed == 0.
// Flit: B = dst0 vc1 src0 seq0 (value 4100).

builtin.module attributes {ac.contract_epoch = "0.2"} {
  ac.protocol @fifo {
    ac.role @sender dual @receiver cardinality "exclusive"
    ac.role @receiver dual @sender cardinality "exclusive"
    ac.state @idle initial true terminal false
    ac.state @done initial false terminal true
    ac.event @push from @sender to @receiver payload i32 action "offer"
    ac.transition from @idle to @done on @push transfer true retain false guard {}
  }

  ac.system @sc04_demo root @Crossbar as "root" tick 0 "cycle"
      workload @Crossbar::@producer0 seed {kind = "fixed", value = 0 : i64}
      instrumentation [] results {id = "default", format = "json"} selected true

  ac.module @Crossbar() parameters {} graph {
    ac.queue @in0_A payload i32 entries 2 bytes 8 ordering "fifo"
        protocol @fifo ownership "exclusive" id "in0_A" path "in0_A"
    ac.queue @in0_B payload i32 entries 2 bytes 8 ordering "fifo"
        protocol @fifo ownership "exclusive" id "in0_B" path "in0_B"
    ac.queue @out0_A payload i32 entries 1 bytes 4 ordering "fifo"
        protocol @fifo ownership "exclusive" id "out0_A" path "out0_A"
    ac.queue @out0_B payload i32 entries 1 bytes 4 ordering "fifo"
        protocol @fifo ownership "exclusive" id "out0_B" path "out0_B"

    // Only a B flit exists; the A VC stays empty.
    ac.process @producer0 kind "workload" {
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
      %in0_free = arith.xori %ea, %true : i1
      %out0_free = arith.xori %ea, %true : i1
      %eb_a = arith.andi %v0b, %in0_free : i1
      %eb_b = arith.andi %eb_a, %out0_free : i1
      %eb_c = arith.andi %eb_b, %w0b : i1
      %eb = arith.andi %eb_c, %d0b_is0 : i1
      scf.if %eb {
        %s0 = ac.try_send @out0_B %h0b : i32
        ac.assert %s0, "sc04: B send must be accepted"
        scf.if %s0 {
          %v0, %g0 = ac.try_recv @in0_B : i32
          ac.assert %g0, "sc04: B grant must receive"
          %m0 = arith.cmpi eq, %v0, %h0b : i32
          ac.assert %m0, "sc04: B receive must match peek"
        }
      }
      ac.yield_sim
    }

    ac.return
  }
}
