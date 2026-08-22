// Contract 0.2 2x2 input-queued crossbar with two virtual channels (A, B) per
// physical channel. Eight logical queues (in0.A/B, in1.A/B, out0.A/B,
// out1.A/B); a single centralized scheduler process computes a matching every
// cycle and commits up to two transfers atomically in the same epoch.
//
// Atomic transfer idiom (no propose_transfer op exists in v0.2):
//   %h, %v = ac.peek @in_src : i32          // non-destructive read
//   ...
//   %sent = ac.try_send @out_dst %h : i32   // propose the push FIRST
//   scf.if %sent {
//     %val, %got = ac.try_recv @in_src : i32  // pop only after grant confirmed
//   }
// All proposals observe the committed snapshot at epoch start and commit at the
// same Xfer barrier, so a granted pair dequeues the source and enqueues the
// destination atomically. A rejected push proposes nothing: the flit stays in
// the source (never dequeued before its output grant is confirmed). No
// process-local holding slot is used. The scheduler body is straight-line and
// terminates in ac.yield_sim (single PC, zero suspension points), so every
// grant commits in the same epoch; ac.await_queue and scf.for are deliberately
// avoided (await would split the pair across epochs; scf.for drops proposal ops).
//
// The physical-channel rules (<=1 flit per physical input, <=1 per physical
// output, per cycle) are MODEL rules enforced by the scheduler's matching: the
// four output VCs are independent SimQueues, so nothing at runtime enforces a
// "physical output" limit. Output VCs are depth 2 and the scheduler checks
// writability with ac.space (free-slot count > 0), so an output VC stays
// writable while a sink drains it (no more alternating A/B steady state).
//
// Flit layout (i32 bit-fields):
//   [1:0] dst     = destination output (0 or 1)
//   [2]   vc      = virtual channel (0 = A, 1 = B)
//   [3]   src     = source input (0 or 1)
//   [7:4] seq     = injection sequence
//   [31:8] payload = seq*97 + src + vc*16   (identity + corruption check)
//
// Traffic (steady state): producer0 injects A->out0 and B->out1; producer1
// injects A->out1 and B->out0. Input and output VCs are depth 2. Under the
// strict A>B priority, the output VCs never fill (sinks drain them every tick),
// so the scheduler grants both A transfers every tick and the B-phase never
// finds a free output: B is fully starved. Two independent A transfers commit
// in the same epoch, every cycle.

builtin.module attributes {ac.contract_epoch = "0.2"} {
  ac.protocol @fifo {
    ac.role @sender dual @receiver cardinality "exclusive"
    ac.role @receiver dual @sender cardinality "exclusive"
    ac.state @idle initial true terminal false
    ac.state @done initial false terminal true
    ac.event @push from @sender to @receiver payload i32 action "offer"
    ac.transition from @idle to @done on @push transfer true retain false guard {}
  }

  ac.system @crossbar_vc_demo root @Crossbar as "root" tick 0 "cycle"
      workload @Crossbar::@producer0 seed {kind = "fixed", value = 0 : i64}
      instrumentation [] results {id = "default", format = "json"} selected true

  ac.module @Crossbar() parameters {} graph {
    // ---- input VCs (depth 2: queueing + backpressure) ----
    ac.queue @in0_A payload i32 entries 2 bytes 8 ordering "fifo"
        protocol @fifo ownership "exclusive" id "in0_A" path "in0_A"
    ac.queue @in0_B payload i32 entries 2 bytes 8 ordering "fifo"
        protocol @fifo ownership "exclusive" id "in0_B" path "in0_B"
    ac.queue @in1_A payload i32 entries 2 bytes 8 ordering "fifo"
        protocol @fifo ownership "exclusive" id "in1_A" path "in1_A"
    ac.queue @in1_B payload i32 entries 2 bytes 8 ordering "fifo"
        protocol @fifo ownership "exclusive" id "in1_B" path "in1_B"

    // ---- output VCs (depth 2: free capacity via ac.space) ----
    ac.queue @out0_A payload i32 entries 2 bytes 8 ordering "fifo"
        protocol @fifo ownership "exclusive" id "out0_A" path "out0_A"
    ac.queue @out0_B payload i32 entries 2 bytes 8 ordering "fifo"
        protocol @fifo ownership "exclusive" id "out0_B" path "out0_B"
    ac.queue @out1_A payload i32 entries 2 bytes 8 ordering "fifo"
        protocol @fifo ownership "exclusive" id "out1_A" path "out1_A"
    ac.queue @out1_B payload i32 entries 2 bytes 8 ordering "fifo"
        protocol @fifo ownership "exclusive" id "out1_B" path "out1_B"

    // Producer 0 (src = 0): re-proposes one A flit (dst 0) into in0_A and one
    // B flit (dst 1) into in0_B every tick; a full input VC soft-rejects and
    // the value is retried next tick. Values are compile-time constants.
    ac.process @producer0 kind "workload" {
      %a = arith.constant 0 : i32            // A: dst0 vc0 src0 seq0 payload 0
      %accepted_a = ac.try_send @in0_A %a : i32
      %b = arith.constant 28949 : i32        // B: dst1 vc1 src0 seq1 payload 113
      %accepted_b = ac.try_send @in0_B %b : i32
      ac.yield_sim
    }

    // Producer 1 (src = 1): re-proposes one A flit (dst 1) into in1_A and one
    // B flit (dst 0) into in1_B every tick.
    ac.process @producer1 kind "workload" {
      %a = arith.constant 49961 : i32        // A: dst1 vc0 src1 seq2 payload 195
      %accepted_a = ac.try_send @in1_A %a : i32
      %b = arith.constant 78908 : i32        // B: dst0 vc1 src1 seq3 payload 308
      %accepted_b = ac.try_send @in1_B %b : i32
      ac.yield_sim
    }

    // Centralized crossbar scheduler. Straight-line body, one epoch:
    //   snapshot inputs -> snapshot outputs -> match -> submit grants.
    // A phase maximizes A grants (per output, lower input wins contention);
    // B phase fills remaining inputs/outputs; lower input wins a same-output
    // B/B tie. Every grant issues try_send first, try_recv only if accepted.
    ac.process @scheduler kind "control" {
      // ---- 1. snapshot input heads (non-destructive) ----
      %h0a, %v0a = ac.peek @in0_A : i32
      %h0b, %v0b = ac.peek @in0_B : i32
      %h1a, %v1a = ac.peek @in1_A : i32
      %h1b, %v1b = ac.peek @in1_B : i32

      // ---- 2. snapshot output VCs (writable == free slots > 0) ----
      %s0a = ac.space @out0_A
      %s0b = ac.space @out0_B
      %s1a = ac.space @out1_A
      %s1b = ac.space @out1_B

      %c0 = arith.constant 0 : i32
      %c1 = arith.constant 1 : i32
      %c3 = arith.constant 3 : i32
      %true = arith.constant true
      %false = arith.constant false

      // ---- decode destination of each valid input head ----
      %d0a = arith.andi %h0a, %c3 : i32
      %d0b = arith.andi %h0b, %c3 : i32
      %d1a = arith.andi %h1a, %c3 : i32
      %d1b = arith.andi %h1b, %c3 : i32

      // ---- output writable flags (free capacity > 0) ----
      %w0a = arith.cmpi sgt, %s0a, %c0 : i32
      %w0b = arith.cmpi sgt, %s0b, %c0 : i32
      %w1a = arith.cmpi sgt, %s1a, %c0 : i32
      %w1b = arith.cmpi sgt, %s1b, %c0 : i32

      %d0a_is0 = arith.cmpi eq, %d0a, %c0 : i32
      %d0a_is1 = arith.cmpi eq, %d0a, %c1 : i32
      %d1a_is0 = arith.cmpi eq, %d1a, %c0 : i32
      %d1a_is1 = arith.cmpi eq, %d1a, %c1 : i32

      // ---- A-phase eligibility: valid && dst==out && out_A writable ----
      %ea0_o0_a = arith.andi %v0a, %w0a : i1
      %ea0_o0 = arith.andi %ea0_o0_a, %d0a_is0 : i1      // in0_A -> out0_A
      %ea0_o1_a = arith.andi %v0a, %w1a : i1
      %ea0_o1 = arith.andi %ea0_o1_a, %d0a_is1 : i1      // in0_A -> out1_A
      %ea1_o0_a = arith.andi %v1a, %w0a : i1
      %ea1_o0 = arith.andi %ea1_o0_a, %d1a_is0 : i1      // in1_A -> out0_A
      %ea1_o1_a = arith.andi %v1a, %w1a : i1
      %ea1_o1 = arith.andi %ea1_o1_a, %d1a_is1 : i1      // in1_A -> out1_A

      // ---- A-phase matching: per output, lower input index wins ----
      %not_ea0_o0 = arith.xori %ea0_o0, %true : i1
      %ga0_o0_i1 = arith.andi %ea1_o0, %not_ea0_o0 : i1  // in1_A->out0 only if in0_A not
      %not_ea0_o1 = arith.xori %ea0_o1, %true : i1
      %ga0_o1_i1 = arith.andi %ea1_o1, %not_ea0_o1 : i1  // in1_A->out1 only if in0_A not

      // ---- used-input / used-output flags (model-level physical rules) ----
      %in0_used = arith.ori %ea0_o0, %ea0_o1 : i1
      %in1_used = arith.ori %ga0_o0_i1, %ga0_o1_i1 : i1
      %out0_used = arith.ori %ea0_o0, %ga0_o0_i1 : i1
      %out1_used = arith.ori %ea0_o1, %ga0_o1_i1 : i1
      %in0_free = arith.xori %in0_used, %true : i1
      %in1_free = arith.xori %in1_used, %true : i1
      %out0_free = arith.xori %out0_used, %true : i1
      %out1_free = arith.xori %out1_used, %true : i1

      // ---- B-phase eligibility (input free && dest output free && writable) ----
      %d0b_is0 = arith.cmpi eq, %d0b, %c0 : i32
      %d0b_is1 = arith.cmpi eq, %d0b, %c1 : i32
      %d1b_is0 = arith.cmpi eq, %d1b, %c0 : i32
      %d1b_is1 = arith.cmpi eq, %d1b, %c1 : i32

      %eb0_o0_a = arith.andi %v0b, %in0_free : i1
      %eb0_o0_b = arith.andi %eb0_o0_a, %out0_free : i1
      %eb0_o0 = arith.andi %eb0_o0_b, %w0b : i1
      %eb0_o1_a = arith.andi %v0b, %in0_free : i1
      %eb0_o1_b = arith.andi %eb0_o1_a, %out1_free : i1
      %eb0_o1 = arith.andi %eb0_o1_b, %w1b : i1
      %eb0_a = arith.andi %d0b_is0, %eb0_o0 : i1
      %eb0_b = arith.andi %d0b_is1, %eb0_o1 : i1
      %eb0 = arith.ori %eb0_a, %eb0_b : i1                 // in0_B eligible

      %eb1_o0_a = arith.andi %v1b, %in1_free : i1
      %eb1_o0_b = arith.andi %eb1_o0_a, %out0_free : i1
      %eb1_o0 = arith.andi %eb1_o0_b, %w0b : i1
      %eb1_o1_a = arith.andi %v1b, %in1_free : i1
      %eb1_o1_b = arith.andi %eb1_o1_a, %out1_free : i1
      %eb1_o1 = arith.andi %eb1_o1_b, %w1b : i1
      %eb1_a = arith.andi %d1b_is0, %eb1_o0 : i1
      %eb1_b = arith.andi %d1b_is1, %eb1_o1 : i1
      %eb1 = arith.ori %eb1_a, %eb1_b : i1                 // in1_B eligible

      // B grants: lower input first; in1_B blocked only if same dest AND in0_B
      // was granted (per-output rule).
      %xb = arith.xori %d0b_is0, %d1b_is0 : i1
      %same_dest = arith.xori %xb, %true : i1
      %not_same = arith.xori %same_dest, %true : i1
      %not_gb0 = arith.xori %eb0, %true : i1
      %gB1_ok = arith.ori %not_same, %not_gb0 : i1
      %gB_1 = arith.andi %eb1, %gB1_ok : i1

      // ---- 3. submit grants (send-then-recv: push first, pop if accepted) ----
      // in0_A -> out0_A
      scf.if %ea0_o0 {
        %s0 = ac.try_send @out0_A %h0a : i32
        ac.assert %s0, "A grant send must be accepted"
        scf.if %s0 {
          %v0, %g0 = ac.try_recv @in0_A : i32
          ac.assert %g0, "A grant source must be receivable"
          %m0 = arith.cmpi eq, %v0, %h0a : i32
          ac.assert %m0, "A grant receive must match peek"
        }
      }
      // in1_A -> out0_A
      scf.if %ga0_o0_i1 {
        %s0 = ac.try_send @out0_A %h1a : i32
        ac.assert %s0, "A grant send must be accepted"
        scf.if %s0 {
          %v0, %g0 = ac.try_recv @in1_A : i32
          ac.assert %g0, "A grant source must be receivable"
          %m0 = arith.cmpi eq, %v0, %h1a : i32
          ac.assert %m0, "A grant receive must match peek"
        }
      }
      // in0_A -> out1_A
      scf.if %ea0_o1 {
        %s0 = ac.try_send @out1_A %h0a : i32
        ac.assert %s0, "A grant send must be accepted"
        scf.if %s0 {
          %v0, %g0 = ac.try_recv @in0_A : i32
          ac.assert %g0, "A grant source must be receivable"
          %m0 = arith.cmpi eq, %v0, %h0a : i32
          ac.assert %m0, "A grant receive must match peek"
        }
      }
      // in1_A -> out1_A
      scf.if %ga0_o1_i1 {
        %s0 = ac.try_send @out1_A %h1a : i32
        ac.assert %s0, "A grant send must be accepted"
        scf.if %s0 {
          %v0, %g0 = ac.try_recv @in1_A : i32
          ac.assert %g0, "A grant source must be receivable"
          %m0 = arith.cmpi eq, %v0, %h1a : i32
          ac.assert %m0, "A grant receive must match peek"
        }
      }
      // in0_B -> its destination (out1_B in this model)
      scf.if %eb0 {
        scf.if %d0b_is0 {
          %s0 = ac.try_send @out0_B %h0b : i32
          ac.assert %s0, "B grant send must be accepted"
          scf.if %s0 {
            %v0, %g0 = ac.try_recv @in0_B : i32
            ac.assert %g0, "B grant source must be receivable"
            %m0 = arith.cmpi eq, %v0, %h0b : i32
            ac.assert %m0, "B grant receive must match peek"
          }
        } else {
          %s0 = ac.try_send @out1_B %h0b : i32
          ac.assert %s0, "B grant send must be accepted"
          scf.if %s0 {
            %v0, %g0 = ac.try_recv @in0_B : i32
            ac.assert %g0, "B grant source must be receivable"
            %m0 = arith.cmpi eq, %v0, %h0b : i32
            ac.assert %m0, "B grant receive must match peek"
          }
        }
      }
      // in1_B -> its destination (out0_B in this model)
      scf.if %gB_1 {
        scf.if %d1b_is0 {
          %s0 = ac.try_send @out0_B %h1b : i32
          ac.assert %s0, "B grant send must be accepted"
          scf.if %s0 {
            %v0, %g0 = ac.try_recv @in1_B : i32
            ac.assert %g0, "B grant source must be receivable"
            %m0 = arith.cmpi eq, %v0, %h1b : i32
            ac.assert %m0, "B grant receive must match peek"
          }
        } else {
          %s0 = ac.try_send @out1_B %h1b : i32
          ac.assert %s0, "B grant send must be accepted"
          scf.if %s0 {
            %v0, %g0 = ac.try_recv @in1_B : i32
            ac.assert %g0, "B grant source must be receivable"
            %m0 = arith.cmpi eq, %v0, %h1b : i32
            ac.assert %m0, "B grant receive must match peek"
          }
        }
      }

      // ---- 4. physical-channel rules, asserted in-model (test 6) ----
      // Grant decisions are computed independently above; re-verify that the
      // chosen set never over-commits a physical channel. The four output VCs
      // are independent SimQueues, so nothing at runtime enforces a per-output
      // limit; these asserts make any matching regression fail the model.
      %in0_granted = arith.ori %ea0_o0, %ea0_o1 : i1        // in0_A -> some A out
      %in1_granted = arith.ori %ga0_o0_i1, %ga0_o1_i1 : i1  // in1_A -> some A out
      %no_2_in0 = arith.andi %in0_granted, %eb0 : i1
      %no_2_in0_ok = arith.xori %no_2_in0, %true : i1
      ac.assert %no_2_in0_ok, "per-input rule: in0 carries at most one flit"
      %no_2_in1 = arith.andi %in1_granted, %gB_1 : i1
      %no_2_in1_ok = arith.xori %no_2_in1, %true : i1
      ac.assert %no_2_in1_ok, "per-input rule: in1 carries at most one flit"
      %ob0_A = arith.andi %eb0, %d0b_is0 : i1              // in0_B -> out0_B
      %ob1_A = arith.andi %gB_1, %d1b_is0 : i1             // in1_B -> out0_B
      %out0_phys = arith.ori %ob0_A, %ob1_A : i1
      %o0_2x = arith.andi %out0_used, %out0_phys : i1      // out0_A and out0_B
      %o0_2x_ok = arith.xori %o0_2x, %true : i1
      ac.assert %o0_2x_ok, "per-output rule: out0 carries at most one flit"
      %ob0_B = arith.andi %eb0, %d0b_is1 : i1              // in0_B -> out1_B
      %ob1_B = arith.andi %gB_1, %d1b_is1 : i1             // in1_B -> out1_B
      %out1_phys = arith.ori %ob0_B, %ob1_B : i1
      %o1_2x = arith.andi %out1_used, %out1_phys : i1      // out1_A and out1_B
      %o1_2x_ok = arith.xori %o1_2x, %true : i1
      ac.assert %o1_2x_ok, "per-output rule: out1 carries at most one flit"
      ac.yield_sim
    }

    // Sink 0: drains out0.A (expect dst 0, vc A, src 0) and out0.B (expect
    // dst 0, vc B, src 1), self-checking destination, VC, source, and payload
    // identity (payload == seq*97 + src + vc*16) on every flit.
    ac.process @sink0 kind "control" {
      %fa, %ra = ac.try_recv @out0_A : i32
      scf.if %ra {
        %c0 = arith.constant 0 : i32
        %c1 = arith.constant 1 : i32
        %c2 = arith.constant 2 : i32
        %c3 = arith.constant 3 : i32
        %c4 = arith.constant 4 : i32
        %c8 = arith.constant 8 : i32
        %c15 = arith.constant 15 : i32
        %c97 = arith.constant 97 : i32
        %c16 = arith.constant 16 : i32
        %dst = arith.andi %fa, %c3 : i32
        %dst_ok = arith.cmpi eq, %dst, %c0 : i32
        ac.assert %dst_ok, "out0_A flit destination must be 0"
        %sh2 = arith.shrui %fa, %c2 : i32
        %vc = arith.andi %sh2, %c1 : i32
        %vc_ok = arith.cmpi eq, %vc, %c0 : i32
        ac.assert %vc_ok, "out0_A flit must be VC A"
        %sh3 = arith.shrui %fa, %c3 : i32
        %src = arith.andi %sh3, %c1 : i32
        %src_ok = arith.cmpi eq, %src, %c0 : i32
        ac.assert %src_ok, "out0_A flit must come from src 0"
        %sh4 = arith.shrui %fa, %c4 : i32
        %seq = arith.andi %sh4, %c15 : i32
        %payload = arith.shrui %fa, %c8 : i32
        %prod = arith.muli %seq, %c97 : i32
        %exp = arith.addi %prod, %src : i32
        %exp2 = arith.addi %exp, %c0 : i32
        %pay_ok = arith.cmpi eq, %payload, %exp2 : i32
        ac.assert %pay_ok, "out0_A flit payload must equal seq*97 + src + vc*16"
      }
      %fb, %rb = ac.try_recv @out0_B : i32
      scf.if %rb {
        %c0 = arith.constant 0 : i32
        %c1 = arith.constant 1 : i32
        %c2 = arith.constant 2 : i32
        %c3 = arith.constant 3 : i32
        %c4 = arith.constant 4 : i32
        %c8 = arith.constant 8 : i32
        %c15 = arith.constant 15 : i32
        %c97 = arith.constant 97 : i32
        %c16 = arith.constant 16 : i32
        %dst = arith.andi %fb, %c3 : i32
        %dst_ok = arith.cmpi eq, %dst, %c0 : i32
        ac.assert %dst_ok, "out0_B flit destination must be 0"
        %sh2 = arith.shrui %fb, %c2 : i32
        %vc = arith.andi %sh2, %c1 : i32
        %vc_ok = arith.cmpi eq, %vc, %c1 : i32
        ac.assert %vc_ok, "out0_B flit must be VC B"
        %sh3 = arith.shrui %fb, %c3 : i32
        %src = arith.andi %sh3, %c1 : i32
        %src_ok = arith.cmpi eq, %src, %c1 : i32
        ac.assert %src_ok, "out0_B flit must come from src 1"
        %sh4 = arith.shrui %fb, %c4 : i32
        %seq = arith.andi %sh4, %c15 : i32
        %payload = arith.shrui %fb, %c8 : i32
        %prod = arith.muli %seq, %c97 : i32
        %exp = arith.addi %prod, %src : i32
        %vc16 = arith.muli %vc, %c16 : i32
        %exp2 = arith.addi %exp, %vc16 : i32
        %pay_ok = arith.cmpi eq, %payload, %exp2 : i32
        ac.assert %pay_ok, "out0_B flit payload must equal seq*97 + src + vc*16"
      }
      ac.yield_sim
    }

    // Sink 1: drains out1.A (expect dst 1, vc A, src 1) and out1.B (expect
    // dst 1, vc B, src 0).
    ac.process @sink1 kind "control" {
      %fa, %ra = ac.try_recv @out1_A : i32
      scf.if %ra {
        %c0 = arith.constant 0 : i32
        %c1 = arith.constant 1 : i32
        %c2 = arith.constant 2 : i32
        %c3 = arith.constant 3 : i32
        %c4 = arith.constant 4 : i32
        %c8 = arith.constant 8 : i32
        %c15 = arith.constant 15 : i32
        %c97 = arith.constant 97 : i32
        %c16 = arith.constant 16 : i32
        %dst = arith.andi %fa, %c3 : i32
        %dst_ok = arith.cmpi eq, %dst, %c1 : i32
        ac.assert %dst_ok, "out1_A flit destination must be 1"
        %sh2 = arith.shrui %fa, %c2 : i32
        %vc = arith.andi %sh2, %c1 : i32
        %vc_ok = arith.cmpi eq, %vc, %c0 : i32
        ac.assert %vc_ok, "out1_A flit must be VC A"
        %sh3 = arith.shrui %fa, %c3 : i32
        %src = arith.andi %sh3, %c1 : i32
        %src_ok = arith.cmpi eq, %src, %c1 : i32
        ac.assert %src_ok, "out1_A flit must come from src 1"
        %sh4 = arith.shrui %fa, %c4 : i32
        %seq = arith.andi %sh4, %c15 : i32
        %payload = arith.shrui %fa, %c8 : i32
        %prod = arith.muli %seq, %c97 : i32
        %exp = arith.addi %prod, %src : i32
        %exp2 = arith.addi %exp, %c0 : i32
        %pay_ok = arith.cmpi eq, %payload, %exp2 : i32
        ac.assert %pay_ok, "out1_A flit payload must equal seq*97 + src + vc*16"
      }
      %fb, %rb = ac.try_recv @out1_B : i32
      scf.if %rb {
        %c0 = arith.constant 0 : i32
        %c1 = arith.constant 1 : i32
        %c2 = arith.constant 2 : i32
        %c3 = arith.constant 3 : i32
        %c4 = arith.constant 4 : i32
        %c8 = arith.constant 8 : i32
        %c15 = arith.constant 15 : i32
        %c97 = arith.constant 97 : i32
        %c16 = arith.constant 16 : i32
        %dst = arith.andi %fb, %c3 : i32
        %dst_ok = arith.cmpi eq, %dst, %c1 : i32
        ac.assert %dst_ok, "out1_B flit destination must be 1"
        %sh2 = arith.shrui %fb, %c2 : i32
        %vc = arith.andi %sh2, %c1 : i32
        %vc_ok = arith.cmpi eq, %vc, %c1 : i32
        ac.assert %vc_ok, "out1_B flit must be VC B"
        %sh3 = arith.shrui %fb, %c3 : i32
        %src = arith.andi %sh3, %c1 : i32
        %src_ok = arith.cmpi eq, %src, %c0 : i32
        ac.assert %src_ok, "out1_B flit must come from src 0"
        %sh4 = arith.shrui %fb, %c4 : i32
        %seq = arith.andi %sh4, %c15 : i32
        %payload = arith.shrui %fb, %c8 : i32
        %prod = arith.muli %seq, %c97 : i32
        %exp = arith.addi %prod, %src : i32
        %vc16 = arith.muli %vc, %c16 : i32
        %exp2 = arith.addi %exp, %vc16 : i32
        %pay_ok = arith.cmpi eq, %payload, %exp2 : i32
        ac.assert %pay_ok, "out1_B flit payload must equal seq*97 + src + vc*16"
      }
      ac.yield_sim
    }

    ac.return
  }
}
