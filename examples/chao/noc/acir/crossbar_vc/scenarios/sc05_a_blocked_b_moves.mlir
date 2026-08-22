// Scenario sc05 (test 5): a full destination VC blocks A, but B still moves.
// in0_A carries two A flits for out0 (seq 0 then seq 1); in0_B carries one B
// flit for out1. The scheduler transfers A seq0 -> out0_A on tick 1, filling
// it. From tick 2 on, out0_A is full, so the second A flit is blocked -- but
// in0_B is now free and its destination VC out1_B is empty, so B moves to
// out1_B (a different physical output, untouched by the A grant).
//
// Expected: in0_A.completed == 1 (A seq0), in0_A.occupancy == 1 (A seq1 stuck),
// in0_B.completed == 1, out0_A.accepted == 1, out1_B.accepted == 1.
// Flits: A0 = dst0 vc0 src0 seq0 (0); A1 = dst0 vc0 src0 seq1 (24848);
// B = dst1 vc1 src0 seq0 (4101).

builtin.module attributes {ac.contract_epoch = "0.2"} {
  ac.protocol @fifo {
    ac.role @sender dual @receiver cardinality "exclusive"
    ac.role @receiver dual @sender cardinality "exclusive"
    ac.state @idle initial true terminal false
    ac.state @done initial false terminal true
    ac.event @push from @sender to @receiver payload i32 action "offer"
    ac.transition from @idle to @done on @push transfer true retain false guard {}
  }

  ac.system @sc05_demo root @Crossbar as "root" tick 0 "cycle"
      workload @Crossbar::@producer0 seed {kind = "fixed", value = 0 : i64}
      instrumentation [] results {id = "default", format = "json"} selected true

  ac.module @Crossbar() parameters {} graph {
    ac.queue @in0_A payload i32 entries 2 bytes 8 ordering "fifo"
        protocol @fifo ownership "exclusive" id "in0_A" path "in0_A"
    ac.queue @in0_B payload i32 entries 2 bytes 8 ordering "fifo"
        protocol @fifo ownership "exclusive" id "in0_B" path "in0_B"
    ac.queue @out0_A payload i32 entries 1 bytes 4 ordering "fifo"
        protocol @fifo ownership "exclusive" id "out0_A" path "out0_A"
    ac.queue @out1_B payload i32 entries 1 bytes 4 ordering "fifo"
        protocol @fifo ownership "exclusive" id "out1_B" path "out1_B"

    ac.process @producer0 kind "workload" {
      %a0 = arith.constant 0 : i32
      %sa0 = ac.try_send @in0_A %a0 : i32
      %a1 = arith.constant 24848 : i32
      %sa1 = ac.try_send @in0_A %a1 : i32
      %b = arith.constant 4101 : i32
      %sb = ac.try_send @in0_B %b : i32
      ac.yield_sim
    }

    ac.process @scheduler kind "control" {
      %h0a, %v0a = ac.peek @in0_A : i32
      %h0b, %v0b = ac.peek @in0_B : i32
      %o0a, %f0a = ac.peek @out0_A : i32
      %o1b, %f1b = ac.peek @out1_B : i32
      %c0 = arith.constant 0 : i32
      %c1 = arith.constant 1 : i32
      %c3 = arith.constant 3 : i32
      %true = arith.constant true
      %w0a = arith.xori %f0a, %true : i1
      %w1b = arith.xori %f1b, %true : i1
      %d0a = arith.andi %h0a, %c3 : i32
      %d0b = arith.andi %h0b, %c3 : i32
      %d0a_is0 = arith.cmpi eq, %d0a, %c0 : i32
      %d0b_is1 = arith.cmpi eq, %d0b, %c1 : i32
      %ea_a = arith.andi %v0a, %w0a : i1
      %ea = arith.andi %ea_a, %d0a_is0 : i1
      // A grants consume physical input 0 and physical output 0 only.
      %in0_free = arith.xori %ea, %true : i1
      %out0_free = arith.xori %ea, %true : i1
      // out1 is never touched by the A phase here -> always free.
      %out1_free = arith.constant true
      %eb_a = arith.andi %v0b, %in0_free : i1
      %eb_b = arith.andi %eb_a, %out1_free : i1
      %eb_c = arith.andi %eb_b, %w1b : i1
      %eb = arith.andi %eb_c, %d0b_is1 : i1
      %two_in = arith.andi %ea, %eb : i1
      %two_in_ok = arith.xori %two_in, %true : i1
      ac.assert %two_in_ok, "sc05: at most one flit per physical input"
      scf.if %ea {
        %s0 = ac.try_send @out0_A %h0a : i32
        ac.assert %s0, "sc05: A send must be accepted"
        scf.if %s0 {
          %v0, %g0 = ac.try_recv @in0_A : i32
          ac.assert %g0, "sc05: A grant must receive"
          %m0 = arith.cmpi eq, %v0, %h0a : i32
          ac.assert %m0, "sc05: A receive must match peek"
        }
      }
      scf.if %eb {
        %s0 = ac.try_send @out1_B %h0b : i32
        ac.assert %s0, "sc05: B send must be accepted"
        scf.if %s0 {
          %v0, %g0 = ac.try_recv @in0_B : i32
          ac.assert %g0, "sc05: B grant must receive"
          %m0 = arith.cmpi eq, %v0, %h0b : i32
          ac.assert %m0, "sc05: B receive must match peek"
        }
      }
      ac.yield_sim
    }

    ac.return
  }
}
