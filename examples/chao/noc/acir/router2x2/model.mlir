// Contract 0.2 2x2 input-queued crossbar example.
//
// Two workload producers continuously re-propose an eight-flit burst into two
// deep input FIFOs. Every process body must terminate in ac.yield_sim, and
// yield_sim resumes the process at its entry on the next tick, so a producer
// re-fires its burst every tick; a proposal that finds the queue full is
// soft-rejected and simply retried on the next tick. A single arbiter control
// process polls both inputs every tick and drains the higher-priority (in0)
// queue first, routing each flit to the output named by its two-bit
// destination field. Two sinks drain the outputs and self-check every flit's
// destination and payload. The run is capped by maxTicks (see runner.cpp).
//
// Flit layout (i32 bit-fields, documented in README.md):
//   [1:0]  dst     = destination output (0 or 1)
//   [3:2]  src     = source producer (0 or 1)
//   [7:4]  seq     = injection sequence number (0..7)
//   [31:8] payload = seq*97 + src   (corruption + flit-identity check)
//
// This is the first example to exercise multi-entry native queues
// (entries > 1) in a linked, executed binary. Under continuous saturation the
// fixed-priority (in0 > in1) arbiter starves @in1 completely — zero
// completions, occupancy pinned at the 16-entry capacity — while @in0
// backpressures at ~15/16 occupancy and drains one flit per tick. A
// deterministic, observable arbitration and backpressure pattern.

builtin.module attributes {ac.contract_epoch = "0.2"} {
  ac.protocol @fifo {
    ac.role @sender dual @receiver cardinality "exclusive"
    ac.role @receiver dual @sender cardinality "exclusive"
    ac.state @idle initial true terminal false
    ac.state @done initial false terminal true
    ac.event @push from @sender to @receiver payload i32 action "offer"
    ac.transition from @idle to @done on @push transfer true retain false guard {}
  }

  ac.system @router2x2_demo root @Top as "root" tick 0 "cycle"
      workload @Top::@producer0 seed {kind = "fixed", value = 0 : i64}
      instrumentation [] results {id = "default", format = "json"} selected true

  ac.module @Top() parameters {} graph {
    ac.queue @in0 payload i32 entries 16 bytes 64 ordering "fifo"
        protocol @fifo ownership "exclusive" id "in0" path "in0"
    ac.queue @in1 payload i32 entries 16 bytes 64 ordering "fifo"
        protocol @fifo ownership "exclusive" id "in1" path "in1"
    ac.queue @out0 payload i32 entries 16 bytes 64 ordering "fifo"
        protocol @fifo ownership "exclusive" id "out0" path "out0"
    ac.queue @out1 payload i32 entries 16 bytes 64 ordering "fifo"
        protocol @fifo ownership "exclusive" id "out1" path "out1"

    // Producer 0 (src = 0): re-proposes the same eight-flit burst into @in0
    // every tick (soft-reject when the queue is full), dst = seq & 1,
    // payload = seq*97 + 0, packed as
    // [1:0] dst | [3:2] src | [7:4] seq | [31:8] payload. Each value is a
    // compile-time constant because the traffic matrix is static. The burst
    // is manually unrolled rather than written as scf.for because the
    // process-state expansion drops proposal ops (ac.try_send) inside static
    // loop bodies — a documented toolchain limitation, see README.md.
    ac.process @producer0 kind "workload" {
      %flit0 = arith.constant 0 : i32          // seq 0, dst 0, payload 0
      %a0 = ac.try_send @in0 %flit0 : i32
      %flit1 = arith.constant 24849 : i32      // seq 1, dst 1, payload 97
      %a1 = ac.try_send @in0 %flit1 : i32
      %flit2 = arith.constant 49696 : i32      // seq 2, dst 0, payload 194
      %a2 = ac.try_send @in0 %flit2 : i32
      %flit3 = arith.constant 74545 : i32      // seq 3, dst 1, payload 291
      %a3 = ac.try_send @in0 %flit3 : i32
      %flit4 = arith.constant 99392 : i32      // seq 4, dst 0, payload 388
      %a4 = ac.try_send @in0 %flit4 : i32
      %flit5 = arith.constant 124241 : i32     // seq 5, dst 1, payload 485
      %a5 = ac.try_send @in0 %flit5 : i32
      %flit6 = arith.constant 149088 : i32     // seq 6, dst 0, payload 582
      %a6 = ac.try_send @in0 %flit6 : i32
      %flit7 = arith.constant 173937 : i32     // seq 7, dst 1, payload 679
      %a7 = ac.try_send @in0 %flit7 : i32
      ac.yield_sim
    }

    // Producer 1 (src = 1): re-proposes the same eight-flit burst into @in1
    // every tick (soft-reject when the queue is full), dst = (seq + 1) & 1,
    // payload = seq*97 + 1, same packing as producer 0. Manually unrolled
    // for the same reason as producer 0 (see above).
    ac.process @producer1 kind "workload" {
      %flit0 = arith.constant 261 : i32        // seq 0, dst 1, payload 1
      %a0 = ac.try_send @in1 %flit0 : i32
      %flit1 = arith.constant 25108 : i32      // seq 1, dst 0, payload 98
      %a1 = ac.try_send @in1 %flit1 : i32
      %flit2 = arith.constant 49957 : i32      // seq 2, dst 1, payload 195
      %a2 = ac.try_send @in1 %flit2 : i32
      %flit3 = arith.constant 74804 : i32      // seq 3, dst 0, payload 292
      %a3 = ac.try_send @in1 %flit3 : i32
      %flit4 = arith.constant 99653 : i32      // seq 4, dst 1, payload 389
      %a4 = ac.try_send @in1 %flit4 : i32
      %flit5 = arith.constant 124500 : i32     // seq 5, dst 0, payload 486
      %a5 = ac.try_send @in1 %flit5 : i32
      %flit6 = arith.constant 149349 : i32     // seq 6, dst 1, payload 583
      %a6 = ac.try_send @in1 %flit6 : i32
      %flit7 = arith.constant 174196 : i32     // seq 7, dst 0, payload 680
      %a7 = ac.try_send @in1 %flit7 : i32
      ac.yield_sim
    }

    // Single arbiter: polls both inputs each tick, fixed priority in0 > in1.
    // Routes the drained flit to the output named by its dst field. The
    // recv-then-send ordering (proven in examples/chao/router_tree) means an
    // output that cannot accept parks the already-consumed flit and retries
    // the send on wake; the input is never re-read and the flit is never lost.
    ac.process @arbiter kind "control" {
      %f0, %v0 = ac.peek @in0 : i32
      scf.if %v0 {
        %r0, %got0 = ac.try_recv @in0 : i32
        ac.assert %got0, "peeked in0 flit must remain receivable"
        %same0 = arith.cmpi eq, %r0, %f0 : i32
        ac.assert %same0, "in0 receive must match peek"
        %c3 = arith.constant 3 : i32
        %c0 = arith.constant 0 : i32
        %dst0 = arith.andi %r0, %c3 : i32
        %to_out0 = arith.cmpi eq, %dst0, %c0 : i32
        scf.if %to_out0 {
          %sent = ac.try_send @out0 %r0 : i32
          scf.if %sent {
          } else {
            ac.await_queue @out0 until "writable"
          }
        } else {
          %sent = ac.try_send @out1 %r0 : i32
          scf.if %sent {
          } else {
            ac.await_queue @out1 until "writable"
          }
        }
      } else {
        %f1, %v1 = ac.peek @in1 : i32
        scf.if %v1 {
          %r1, %got1 = ac.try_recv @in1 : i32
          ac.assert %got1, "peeked in1 flit must remain receivable"
          %same1 = arith.cmpi eq, %r1, %f1 : i32
          ac.assert %same1, "in1 receive must match peek"
          %c3 = arith.constant 3 : i32
          %c0 = arith.constant 0 : i32
          %dst1 = arith.andi %r1, %c3 : i32
          %to_out0 = arith.cmpi eq, %dst1, %c0 : i32
          scf.if %to_out0 {
            %sent = ac.try_send @out0 %r1 : i32
            scf.if %sent {
            } else {
              ac.await_queue @out0 until "writable"
            }
          } else {
            %sent = ac.try_send @out1 %r1 : i32
            scf.if %sent {
            } else {
              ac.await_queue @out1 until "writable"
            }
          }
        }
      }
      ac.yield_sim
    }

    // Sink 0: drains out0 and self-checks every flit (dst == 0, and the
    // payload must equal seq*97 + src, which also verifies the flit fields
    // were packed and stripped consistently at every stage).
    ac.process @sink0 kind "control" {
      %flit, %received = ac.try_recv @out0 : i32
      scf.if %received {
        %c0 = arith.constant 0 : i32
        %c2 = arith.constant 2 : i32
        %c3 = arith.constant 3 : i32
        %c4 = arith.constant 4 : i32
        %c8 = arith.constant 8 : i32
        %c15 = arith.constant 15 : i32
        %c97 = arith.constant 97 : i32
        %dst = arith.andi %flit, %c3 : i32
        %dst_ok = arith.cmpi eq, %dst, %c0 : i32
        ac.assert %dst_ok, "out0 flit destination must be 0"
        %sh2 = arith.shrui %flit, %c2 : i32
        %src = arith.andi %sh2, %c3 : i32
        %sh4 = arith.shrui %flit, %c4 : i32
        %seq = arith.andi %sh4, %c15 : i32
        %payload = arith.shrui %flit, %c8 : i32
        %prod = arith.muli %seq, %c97 : i32
        %expect = arith.addi %prod, %src : i32
        %pay_ok = arith.cmpi eq, %payload, %expect : i32
        ac.assert %pay_ok, "out0 flit payload must equal seq*97 + src"
      } else {
        ac.await_queue @out0 until "readable"
      }
      ac.yield_sim
    }

    // Sink 1: drains out1 and self-checks every flit (dst == 1).
    ac.process @sink1 kind "control" {
      %flit, %received = ac.try_recv @out1 : i32
      scf.if %received {
        %c1 = arith.constant 1 : i32
        %c2 = arith.constant 2 : i32
        %c3 = arith.constant 3 : i32
        %c4 = arith.constant 4 : i32
        %c8 = arith.constant 8 : i32
        %c15 = arith.constant 15 : i32
        %c97 = arith.constant 97 : i32
        %dst = arith.andi %flit, %c3 : i32
        %dst_ok = arith.cmpi eq, %dst, %c1 : i32
        ac.assert %dst_ok, "out1 flit destination must be 1"
        %sh2 = arith.shrui %flit, %c2 : i32
        %src = arith.andi %sh2, %c3 : i32
        %sh4 = arith.shrui %flit, %c4 : i32
        %seq = arith.andi %sh4, %c15 : i32
        %payload = arith.shrui %flit, %c8 : i32
        %prod = arith.muli %seq, %c97 : i32
        %expect = arith.addi %prod, %src : i32
        %pay_ok = arith.cmpi eq, %payload, %expect : i32
        ac.assert %pay_ok, "out1 flit payload must equal seq*97 + src"
      } else {
        ac.await_queue @out1 until "readable"
      }
      ac.yield_sim
    }

    ac.return
  }
}
