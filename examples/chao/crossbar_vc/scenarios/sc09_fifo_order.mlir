// Scenario sc09 (test 9): FIFO ordering within a VC.
// A one-shot burst of four A flits (seq 0..3, dst0) enters in0_A and is
// drained one per tick through out0_A. The sink self-checks, via a depth-2
// self-loop register @prev holding the last observed sequence number, that the
// sequence is strictly increasing (seq == prev + 1) for every adjacent pair.
// A FIFO violation in the queue (out-of-order dequeue) fails the in-model
// assert. (Depth 2 so the store never collides with a same-tick pending pop;
// see the @prev declaration.)
//
// The burst is injected once (latch @gate) so the producer cannot re-inject
// seq 0 once in0_A has headroom, which would reorder the tail.
//
// Expected: in0_A.completed == 4, out0_A.completed == 4, and the sink's
// order/payload asserts all pass. Flits: seq0 = 0, seq1 = 24848, seq2 = 49696,
// seq3 = 74544 (dst0 vc0 src0, payload == seq*97).

builtin.module attributes {ac.contract_epoch = "0.2"} {
  ac.protocol @fifo {
    ac.role @sender dual @receiver cardinality "exclusive"
    ac.role @receiver dual @sender cardinality "exclusive"
    ac.state @idle initial true terminal false
    ac.state @done initial false terminal true
    ac.event @push from @sender to @receiver payload i32 action "offer"
    ac.transition from @idle to @done on @push transfer true retain false guard {}
  }

  ac.system @sc09_demo root @Crossbar as "root" tick 0 "cycle"
      workload @Crossbar::@producer0 seed {kind = "fixed", value = 0 : i64}
      instrumentation [] results {id = "default", format = "json"} selected true

  ac.module @Crossbar() parameters {} graph {
    ac.queue @in0_A payload i32 entries 4 bytes 16 ordering "fifo"
        protocol @fifo ownership "exclusive" id "in0_A" path "in0_A"
    ac.queue @out0_A payload i32 entries 1 bytes 4 ordering "fifo"
        protocol @fifo ownership "exclusive" id "out0_A" path "out0_A"
    // One-shot latch: capacity-1 self-loop register owned by @producer0.
    ac.queue @gate payload i32 entries 1 bytes 4 ordering "fifo"
        protocol @fifo ownership "exclusive" id "gate" path "gate"
    // Order-check register: depth-2 self-loop owned by @sink0, holds prev seq.
    // Depth 2 (not 1) so the store is never rejected: the sink always recvs
    // first, so a depth-1 register would hold a stale value on the tick its
    // pending pop has not yet committed (proposePush sees committedSize 1 +
    // pending 0 >= capacity 1 and rejects the store), skipping the check for
    // the next pair. Depth 2 keeps the register at one committed element while
    // letting every store land, so each adjacent seq pair is verified.
    ac.queue @prev payload i32 entries 2 bytes 8 ordering "fifo"
        protocol @fifo ownership "exclusive" id "prev" path "prev"

    ac.process @producer0 kind "workload" {
      %true = arith.constant true
      %gh, %gv = ac.peek @gate : i32
      %not_done = arith.xori %gv, %true : i1
      scf.if %not_done {
        %c0 = arith.constant 0 : i32
        %c1 = arith.constant 24848 : i32
        %c2 = arith.constant 49696 : i32
        %c3 = arith.constant 74544 : i32
        %s0 = ac.try_send @in0_A %c0 : i32
        %s1 = ac.try_send @in0_A %c1 : i32
        %s2 = ac.try_send @in0_A %c2 : i32
        %s3 = ac.try_send @in0_A %c3 : i32
        %one = arith.constant 1 : i32
        %latch = ac.try_send @gate %one : i32
      }
      ac.yield_sim
    }

    ac.process @scheduler kind "control" {
      %h0a, %v0a = ac.peek @in0_A : i32
      %o0a, %f0a = ac.peek @out0_A : i32
      %c0 = arith.constant 0 : i32
      %c3 = arith.constant 3 : i32
      %true = arith.constant true
      %w0a = arith.xori %f0a, %true : i1
      %d0a = arith.andi %h0a, %c3 : i32
      %d0a_is0 = arith.cmpi eq, %d0a, %c0 : i32
      %ea_a = arith.andi %v0a, %w0a : i1
      %ea = arith.andi %ea_a, %d0a_is0 : i1
      scf.if %ea {
        %s0 = ac.try_send @out0_A %h0a : i32
        ac.assert %s0, "sc09: send must be accepted"
        scf.if %s0 {
          %v0, %g0 = ac.try_recv @in0_A : i32
          ac.assert %g0, "sc09: grant must receive"
          %m0 = arith.cmpi eq, %v0, %h0a : i32
          ac.assert %m0, "sc09: receive must match peek"
        }
      }
      ac.yield_sim
    }

    ac.process @sink0 kind "control" {
      %flit, %got = ac.try_recv @out0_A : i32
      scf.if %got {
        %c0 = arith.constant 0 : i32
        %c1 = arith.constant 1 : i32
        %c4 = arith.constant 4 : i32
        %c8 = arith.constant 8 : i32
        %c15 = arith.constant 15 : i32
        %c97 = arith.constant 97 : i32
        %sh4 = arith.shrui %flit, %c4 : i32
        %seq = arith.andi %sh4, %c15 : i32
        %payload = arith.shrui %flit, %c8 : i32
        %prod = arith.muli %seq, %c97 : i32
        %exp = arith.addi %prod, %c0 : i32
        %pay_ok = arith.cmpi eq, %payload, %exp : i32
        ac.assert %pay_ok, "sc09: payload identity (seq*97 + src + vc*16)"
        // Strictly increasing order check against the previous seq. @prev is a
        // capacity-1 register: consume the old value first, then store the new
        // one (the adder register idiom).
        %ph, %pv = ac.try_recv @prev : i32
        scf.if %pv {
          %exp_seq = arith.addi %ph, %c1 : i32
          %seq_ok = arith.cmpi eq, %seq, %exp_seq : i32
          ac.assert %seq_ok, "sc09: seq must be strictly increasing (FIFO)"
        }
        %sent = ac.try_send @prev %seq : i32
      }
      ac.yield_sim
    }

    ac.return
  }
}
