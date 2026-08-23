builtin.module attributes {ac.contract_epoch = "0.2"} {
  ac.protocol @fifo {
    ac.role @sender dual @receiver cardinality "exclusive"
    ac.role @receiver dual @sender cardinality "exclusive"
    ac.state @idle initial true terminal false
    ac.state @done initial false terminal true
    ac.event @push from @sender to @receiver payload i32 action "offer"
    ac.transition from @idle to @done on @push transfer true retain false guard {}
  }

  ac.system @m0_arbitrate_transfer root @Top as "root" tick 0 "cycle"
      workload @Top::@producer0 seed {kind = "fixed", value = 7 : i64}
      instrumentation [] results {id = "default", format = "json"} selected true

  ac.module @Top() parameters {} graph {
    ac.queue @source0 payload i32 entries 1 bytes 4 ordering "fifo"
        protocol @fifo ownership "exclusive" id "source0" path "source0"
    ac.queue @source1 payload i32 entries 1 bytes 4 ordering "fifo"
        protocol @fifo ownership "exclusive" id "source1" path "source1"
    ac.queue @destination payload i32 entries 1 bytes 4 ordering "fifo"
        protocol @fifo ownership "exclusive" id "destination" path "destination"

    ac.resource @input0 capacity 1 issue_width 1 ii 1
        latency {kind = "fixed", ticks = 1 : i64}
        lifecycle {reservation = "propose_commit", release = "balanced", cancellation = "explicit"}
        ownership "exclusive" classes [] id "input0" path "input0"
    ac.resource @input1 capacity 1 issue_width 1 ii 1
        latency {kind = "fixed", ticks = 1 : i64}
        lifecycle {reservation = "propose_commit", release = "balanced", cancellation = "explicit"}
        ownership "exclusive" classes [] id "input1" path "input1"
    ac.resource @output capacity 1 issue_width 1 ii 1
        latency {kind = "fixed", ticks = 1 : i64}
        lifecycle {reservation = "propose_commit", release = "balanced", cancellation = "explicit"}
        ownership "exclusive" classes [] id "output" path "output"

    ac.process @producer0 kind "workload" {
      %value = arith.constant 10 : i32
      %accepted = ac.try_send @source0 %value : i32
      ac.yield_sim
    }

    ac.process @producer1 kind "control" {
      %value = arith.constant 20 : i32
      %accepted = ac.try_send @source1 %value : i32
      ac.yield_sim
    }

    ac.process @scheduler kind "control" {
      %head0, %valid0 = ac.peek @source0 : i32
      %head1, %valid1 = ac.peek @source1 : i32
      %space = ac.space @destination
      %zero = arith.constant 0 : i32
      %writable = arith.cmpi sgt, %space, %zero : i32
      %request0 = arith.andi %valid0, %writable : i1
      %request1 = arith.andi %valid1, %writable : i1
      %grant0, %grant1 = ac.arbitrate greedy_fixed_priority candidates [
        %request0 uses [@input0, @output],
        %request1 uses [@input1, @output]
      ] : (i1, i1)
      %fire0 = ac.try_transfer @source0 to @destination when %grant0 : i32
      %fire1 = ac.try_transfer @source1 to @destination when %grant1 : i32
      ac.yield_sim
    }

    ac.process @observer kind "control" {
      %value, %valid = ac.peek @destination : i32
      scf.if %valid {
        %ten = arith.constant 10 : i32
        %correct = arith.cmpi eq, %value, %ten : i32
        ac.assert %correct, "fixed priority must transfer the old source0 head"
      } else {
        ac.await_queue @destination until "readable"
      }
      ac.yield_sim
    }

    ac.return
  }
}
