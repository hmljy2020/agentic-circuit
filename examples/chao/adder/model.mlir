// Contract 0.2 streaming adder — register pipeline, correct under skew.
//
// The three-queue streaming adder (model.mlir.xkp port) had a latent
// correctness bug: @adder did two unguarded destructive reads
//   %lhs, %received_a = ac.try_recv @op_a : i32
//   %rhs, %received_b = ac.try_recv @op_b : i32
//   scf.if arith.andi %received_a, %received_b ...
// try_recv consumes even when the other operand is absent, so if @op_a and
// @op_b ever arrive in different ticks the earlier-arrived value is silently
// dropped. This version removes that bug and makes the cross-tick hold real.
//
// ACIR v0.2 has no process-local mutable register — the only mutable storage
// is ac.queue — so a "register" is modeled as a capacity-1 self-loop queue
// that the owning process both sends to and receives from (a pattern that is
// native-lowerable, see test/Conversion/native-queue.mlir). The ALU is a
// two-stage pipeline:
//   stage 1 (load):  @op_a -> @reg_a,  @op_b -> @reg_b, but only into an
//                    EMPTY register. A full register holds an operand whose
//                    partner has not arrived; overwriting it would drop it.
//   stage 2 (compute): when BOTH @reg_a and @reg_b are full (peeked, not
//                    consumed), recv both and add. Both recvs are then
//                    guaranteed to succeed.
// Because a try_send is pending until Xfer, a value loaded this tick is not
// visible to compute until the next tick — the pipeline registers have one
// real tick of latency, so @op_a genuinely sits in @reg_a waiting for @op_b.
//
// @op_b is skewed one tick behind @op_a: @source injects 2 and 3 in the same
// tick, and @delay moves @op_b_delay -> @op_b with a peek-gated move (never
// drops, never overwrites an unconsumed value). The adder's input pair (2, 3)
// is therefore only ever complete one tick after @op_a arrives, which is
// exactly the situation that exercised the destructive-load bug.

builtin.module attributes {ac.contract_epoch = "0.2"} {
  ac.protocol @fifo {
    ac.role @sender dual @receiver cardinality "exclusive"
    ac.role @receiver dual @sender cardinality "exclusive"
    ac.state @idle initial true terminal false
    ac.state @done initial false terminal true
    ac.event @push from @sender to @receiver payload i32 action "offer"
    ac.transition from @idle to @done on @push transfer true retain false guard {}
  }

  ac.system @adder_demo root @Adder as "root" tick 0 "cycle"
      workload @Adder::@source seed {kind = "fixed", value = 0 : i64}
      instrumentation [] results {id = "default", format = "json"} selected true

  ac.module @Adder() parameters {} graph {
    ac.queue @op_a payload i32 entries 1 bytes 4 ordering "fifo"
        protocol @fifo ownership "exclusive" id "op_a" path "op_a"
    ac.queue @op_b_delay payload i32 entries 1 bytes 4 ordering "fifo"
        protocol @fifo ownership "exclusive" id "op_b_delay" path "op_b_delay"
    ac.queue @op_b payload i32 entries 1 bytes 4 ordering "fifo"
        protocol @fifo ownership "exclusive" id "op_b" path "op_b"
    ac.queue @reg_a payload i32 entries 1 bytes 4 ordering "fifo"
        protocol @fifo ownership "exclusive" id "reg_a" path "reg_a"
    ac.queue @reg_b payload i32 entries 1 bytes 4 ordering "fifo"
        protocol @fifo ownership "exclusive" id "reg_b" path "reg_b"
    ac.queue @result payload i32 entries 1 bytes 4 ordering "fifo"
        protocol @fifo ownership "exclusive" id "result" path "result"

    // Injects operands 2 and 3 continuously (yield_sim re-fires every tick);
    // a full queue soft-rejects and the value is retried next tick. Values are
    // compile-time constants, so a soft-reject loses nothing.
    ac.process @source kind "workload" {
      %two = arith.constant 2 : i32
      %three = arith.constant 3 : i32
      %accepted_a = ac.try_send @op_a %two : i32
      %accepted_d = ac.try_send @op_b_delay %three : i32
      ac.yield_sim
    }

    // One-tick delay line for operand B. Moves @op_b_delay -> @op_b only when
    // @op_b is empty (peek-gated), so a value @alu has not yet consumed is
    // never overwritten and the pipe never drops a flit.
    ac.process @delay kind "control" {
      %held, %op_b_full = ac.peek @op_b : i32
      scf.if %op_b_full {
        // @op_b still holds an operand @alu has not loaded; hold the pipe.
      } else {
        %pending, %delay_ok = ac.peek @op_b_delay : i32
        scf.if %delay_ok {
          %operand, %got = ac.try_recv @op_b_delay : i32
          %stored = ac.try_send @op_b %operand : i32
        }
      }
      ac.yield_sim
    }

    // Two-stage register ALU. Load only into an EMPTY register (a full one
    // holds an operand whose partner has not arrived); compute only when both
    // registers are full (peeked first, so both recvs succeed). @reg_a and
    // @reg_b are capacity-1 self-loop queues acting as process-local storage.
    ac.process @alu kind "control" {
      // Stage 1a: load @op_a -> @reg_a.
      %ra, %reg_a_full = ac.peek @reg_a : i32
      scf.if %reg_a_full {
      } else {
        %a, %got_a = ac.try_recv @op_a : i32
        scf.if %got_a {
          %stored_a = ac.try_send @reg_a %a : i32
        }
      }

      // Stage 1b: load @op_b -> @reg_b.
      %rb, %reg_b_full = ac.peek @reg_b : i32
      scf.if %reg_b_full {
      } else {
        %b, %got_b = ac.try_recv @op_b : i32
        scf.if %got_b {
          %stored_b = ac.try_send @reg_b %b : i32
        }
      }

      // Stage 2: compute when the pair is complete.
      %ra2, %rfull_a = ac.peek @reg_a : i32
      %rb2, %rfull_b = ac.peek @reg_b : i32
      %both = arith.andi %rfull_a, %rfull_b : i1
      scf.if %both {
        %lhs, %cgot_a = ac.try_recv @reg_a : i32
        %rhs, %cgot_b = ac.try_recv @reg_b : i32
        %sum = arith.addi %lhs, %rhs : i32
        %five = arith.constant 5 : i32
        %correct = arith.cmpi eq, %sum, %five : i32
        ac.assert %correct, "adder result must equal 5"
        %result_sent = ac.try_send @result %sum : i32
      }
      ac.yield_sim
    }

    ac.process @sink kind "control" {
      %value, %received = ac.try_recv @result : i32
      scf.if %received {
        // Drain @result so it never stays full.
      }
      ac.yield_sim
    }

    ac.return
  }
}
