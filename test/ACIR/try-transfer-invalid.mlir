// RUN: %acir_opt_public --split-input-file --verify-diagnostics %s

builtin.module attributes {ac.contract_epoch = "0.2"} {
  ac.protocol @fifo {
    ac.role @sender dual @receiver cardinality "exclusive"
    ac.role @receiver dual @sender cardinality "exclusive"
    ac.state @idle initial true terminal false
    ac.event @push from @sender to @receiver payload i32 action "offer"
  }
  ac.module @Bad() parameters {} graph {
    ac.queue @q payload i32 entries 1 ordering "fifo" protocol @fifo ownership "exclusive" id "q" path "q"
    ac.process @p kind "control" {
      %enable = arith.constant true
      // expected-error @+1 {{source and destination queues must be different}}
      %fire = ac.try_transfer @q to @q when %enable : i32
      ac.yield_sim
    }
    ac.return
  }
}

// -----

builtin.module attributes {ac.contract_epoch = "0.2"} {
  ac.protocol @fifo {
    ac.role @sender dual @receiver cardinality "exclusive"
    ac.role @receiver dual @sender cardinality "exclusive"
    ac.state @idle initial true terminal false
    ac.event @push from @sender to @receiver payload i32 action "offer"
  }
  ac.module @Bad() parameters {} graph {
    ac.queue @source payload i32 entries 1 ordering "fifo" protocol @fifo ownership "exclusive" id "source" path "source"
    ac.queue @d0 payload i32 entries 1 ordering "fifo" protocol @fifo ownership "exclusive" id "d0" path "d0"
    ac.queue @d1 payload i32 entries 1 ordering "fifo" protocol @fifo ownership "exclusive" id "d1" path "d1"
    ac.resource @input capacity 1 issue_width 1 ii 1 latency {kind = "fixed", ticks = 1 : i64} lifecycle {reservation = "propose_commit", release = "balanced", cancellation = "explicit"} ownership "exclusive" classes [] id "input" path "input"
    ac.resource @out0 capacity 1 issue_width 1 ii 1 latency {kind = "fixed", ticks = 1 : i64} lifecycle {reservation = "propose_commit", release = "balanced", cancellation = "explicit"} ownership "exclusive" classes [] id "out0" path "out0"
    ac.resource @out1 capacity 1 issue_width 1 ii 1 latency {kind = "fixed", ticks = 1 : i64} lifecycle {reservation = "propose_commit", release = "balanced", cancellation = "explicit"} ownership "exclusive" classes [] id "out1" path "out1"
    ac.process @p kind "control" {
      %r0 = arith.constant true
      %r1 = arith.constant true
      %g0, %g1 = ac.arbitrate greedy_fixed_priority candidates [
        %r0 uses [@input, @out0], %r1 uses [@input, @out1]
      ] : (i1, i1)
      %true = arith.constant true
      %rewritten = arith.andi %g1, %true : i1
      // expected-note @+1 {{conflicting operation is here}}
      %f0 = ac.try_transfer @source to @d0 when %g0 : i32
      // expected-error @+1 {{queue 'source' has conflicting pop operations in one commit epoch}}
      %f1 = ac.try_transfer @source to @d1 when %rewritten : i32
      ac.yield_sim
    }
    ac.return
  }
}

// -----

builtin.module attributes {ac.contract_epoch = "0.2"} {
  ac.protocol @fifo {
    ac.role @sender dual @receiver cardinality "exclusive"
    ac.role @receiver dual @sender cardinality "exclusive"
    ac.state @idle initial true terminal false
    ac.event @push from @sender to @receiver payload i32 action "offer"
  }
  ac.module @Bad() parameters {} graph {
    ac.queue @s0 payload i32 entries 1 ordering "fifo" protocol @fifo ownership "exclusive" id "s0" path "s0"
    ac.queue @s1 payload i32 entries 1 ordering "fifo" protocol @fifo ownership "exclusive" id "s1" path "s1"
    ac.queue @d0 payload i32 entries 1 ordering "fifo" protocol @fifo ownership "exclusive" id "d0" path "d0"
    ac.queue @d1 payload i32 entries 1 ordering "fifo" protocol @fifo ownership "exclusive" id "d1" path "d1"
    ac.resource @r capacity 1 issue_width 1 ii 1 latency {kind = "fixed", ticks = 1 : i64} lifecycle {reservation = "propose_commit", release = "balanced", cancellation = "explicit"} ownership "exclusive" classes [] id "r" path "r"
    ac.process @p kind "control" {
      %request = arith.constant true
      %grant = ac.arbitrate greedy_fixed_priority candidates [%request uses [@r]] : (i1)
      // expected-note @+1 {{first transfer enabled by this grant is here}}
      %f0 = ac.try_transfer @s0 to @d0 when %grant : i32
      // expected-error @+1 {{one arbiter grant may directly enable at most one ac.try_transfer}}
      %f1 = ac.try_transfer @s1 to @d1 when %grant : i32
      ac.yield_sim
    }
    ac.return
  }
}

// -----

builtin.module attributes {ac.contract_epoch = "0.2"} {
  ac.protocol @p0 {
    ac.role @sender dual @receiver cardinality "exclusive"
    ac.role @receiver dual @sender cardinality "exclusive"
    ac.state @idle initial true terminal false
    ac.event @push from @sender to @receiver payload i32 action "offer"
  }
  ac.protocol @p1 {
    ac.role @sender dual @receiver cardinality "exclusive"
    ac.role @receiver dual @sender cardinality "exclusive"
    ac.state @idle initial true terminal false
    ac.event @push from @sender to @receiver payload i32 action "offer"
  }
  ac.module @Bad() parameters {} graph {
    ac.queue @source payload i32 entries 1 ordering "fifo" protocol @p0 ownership "exclusive" id "source" path "source"
    ac.queue @destination payload i32 entries 1 ordering "fifo" protocol @p1 ownership "exclusive" id "destination" path "destination"
    ac.process @p kind "control" {
      %enable = arith.constant true
      // expected-error @+1 {{source and destination queue protocols must match}}
      %fire = ac.try_transfer @source to @destination when %enable : i32
      ac.yield_sim
    }
    ac.return
  }
}

// -----

builtin.module attributes {ac.contract_epoch = "0.2"} {
  ac.protocol @fifo {
    ac.role @sender dual @receiver cardinality "exclusive"
    ac.role @receiver dual @sender cardinality "exclusive"
    ac.state @idle initial true terminal false
    ac.event @push from @sender to @receiver payload i32 action "offer"
  }
  ac.module @Bad() parameters {} graph {
    ac.queue @source payload i32 entries 1 ordering "fifo" protocol @fifo ownership "exclusive" id "source" path "source"
    ac.queue @destination payload i32 entries 1 ordering "fifo" protocol @fifo ownership "exclusive" id "destination" path "destination"
    ac.process @p kind "control" {
      %enable = arith.constant true
      // expected-error @+2 {{payload type 'i16' does not match source queue payload type 'i32'}}
      // expected-error @+1 {{payload type 'i16' does not match destination queue payload type 'i32'}}
      %fire = ac.try_transfer @source to @destination when %enable : i16
      ac.yield_sim
    }
    ac.return
  }
}

// -----

builtin.module attributes {ac.contract_epoch = "0.2"} {
  ac.protocol @fifo {
    ac.role @sender dual @receiver cardinality "exclusive"
    ac.role @receiver dual @sender cardinality "exclusive"
    ac.state @idle initial true terminal false
    ac.event @push from @sender to @receiver payload i32 action "offer"
  }
  ac.module @Bad() parameters {} graph {
    ac.queue @source payload i32 entries 1 ordering "fifo" protocol @fifo ownership "exclusive" id "source" path "source"
    ac.queue @d0 payload i32 entries 1 ordering "fifo" protocol @fifo ownership "exclusive" id "d0" path "d0"
    ac.queue @d1 payload i32 entries 1 ordering "fifo" protocol @fifo ownership "exclusive" id "d1" path "d1"
    ac.process @p kind "control" {
      %enable = arith.constant true
      // expected-note @+1 {{conflicting operation is here}}
      %f0 = ac.try_transfer @source to @d0 when %enable : i32
      // expected-error @+1 {{queue 'source' has conflicting pop operations in one commit epoch}}
      %f1 = ac.try_transfer @source to @d1 when %enable : i32
      ac.yield_sim
    }
    ac.return
  }
}

// -----

builtin.module attributes {ac.contract_epoch = "0.2"} {
  ac.protocol @fifo {
    ac.role @sender dual @receiver cardinality "exclusive"
    ac.role @receiver dual @sender cardinality "exclusive"
    ac.state @idle initial true terminal false
    ac.event @push from @sender to @receiver payload i32 action "offer"
  }
  ac.module @Bad() parameters {} graph {
    ac.queue @source payload i32 entries 1 ordering "fifo" protocol @fifo ownership "exclusive" id "source" path "source"
    ac.queue @destination payload i32 entries 1 ordering "fifo" protocol @fifo ownership "exclusive" id "destination" path "destination"
    ac.process @p kind "control" {
      %enable = arith.constant true
      %value = arith.constant 1 : i32
      // expected-note @+1 {{conflicting operation is here}}
      %accepted = ac.try_send @destination %value : i32
      // expected-error @+1 {{queue 'destination' has conflicting push operations in one commit epoch}}
      %fire = ac.try_transfer @source to @destination when %enable : i32
      ac.yield_sim
    }
    ac.return
  }
}
