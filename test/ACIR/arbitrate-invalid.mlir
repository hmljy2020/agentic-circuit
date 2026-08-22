// RUN: %acir_opt_public --split-input-file --verify-diagnostics %s

builtin.module attributes {ac.contract_epoch = "0.2"} {
  ac.module @Bad() parameters {} graph {
    ac.process @p kind "control" {
      %r = arith.constant true
      // expected-error @+1 {{policy must be one of 'greedy_fixed_priority' or 'round_robin'}}
      %g = ac.arbitrate random candidates [%r uses []] : (i1)
      ac.yield_sim
    }
    ac.return
  }
}

// -----

builtin.module attributes {ac.contract_epoch = "0.2"} {
  ac.module @Bad() parameters {} graph {
    ac.resource @r0 capacity 1 issue_width 1 ii 1
        latency {kind = "fixed", ticks = 1 : i64}
        lifecycle {reservation = "propose_commit", release = "balanced", cancellation = "explicit"}
        ownership "exclusive" classes [] id "r0" path "r0"
    ac.resource @r1 capacity 1 issue_width 1 ii 1
        latency {kind = "fixed", ticks = 1 : i64}
        lifecycle {reservation = "propose_commit", release = "balanced", cancellation = "explicit"}
        ownership "exclusive" classes [] id "r1" path "r1"
    ac.process @p kind "control" {
      %state = arith.constant 0 : i32
      %request = arith.constant true
      // expected-error @+1 {{round_robin candidates must share at least one common resource}}
      %g0, %g1, %next = ac.arbitrate round_robin state %state candidates [
        %request uses [@r0], %request uses [@r1]
      ] : (i32, i1, i1) -> (i1, i1, i32)
      ac.yield_sim
    }
    ac.return
  }
}

// -----

builtin.module attributes {ac.contract_epoch = "0.2"} {
  ac.module @Bad() parameters {} graph {
    ac.process @p kind "control" {
      %r = arith.constant true
      // expected-error @+1 {{resource '@missing' must resolve to an ac.resource in the same module}}
      %g = ac.arbitrate greedy_fixed_priority candidates [%r uses [@missing]] : (i1)
      ac.yield_sim
    }
    ac.return
  }
}

// -----

builtin.module attributes {ac.contract_epoch = "0.2"} {
  ac.module @Bad() parameters {} graph {
    ac.resource @r capacity 1 issue_width 1 ii 1
        latency {kind = "fixed", ticks = 1 : i64}
        lifecycle {reservation = "propose_commit", release = "balanced", cancellation = "explicit"}
        ownership "exclusive" classes [] id "r" path "r"
    ac.process @p kind "control" {
      %request = arith.constant true
      // expected-error @+1 {{candidate 0 contains duplicate resource '@r'}}
      %g = ac.arbitrate greedy_fixed_priority candidates [%request uses [@r, @r]] : (i1)
      ac.yield_sim
    }
    ac.return
  }
}

// -----

builtin.module attributes {ac.contract_epoch = "0.2"} {
  ac.module @Bad() parameters {} graph {
    ac.resource @r capacity 2 issue_width 1 ii 1
        latency {kind = "fixed", ticks = 1 : i64}
        lifecycle {reservation = "propose_commit", release = "balanced", cancellation = "explicit"}
        ownership "exclusive" classes [] id "r" path "r"
    ac.process @p kind "control" {
      %request = arith.constant true
      // expected-error @+1 {{must have capacity=1, issue_width=1, ii=1, and fixed latency of 1 tick}}
      %g = ac.arbitrate greedy_fixed_priority candidates [%request uses [@r]] : (i1)
      ac.yield_sim
    }
    ac.return
  }
}

// -----

builtin.module attributes {ac.contract_epoch = "0.2"} {
  ac.module @Bad() parameters {} graph {
    ac.resource @r capacity 1 issue_width 1 ii 1
        latency {kind = "fixed", ticks = 1 : i64}
        lifecycle {reservation = "propose_commit", release = "balanced", cancellation = "explicit"}
        ownership "exclusive" classes [] id "r" path "r"
    ac.process @p kind "control" {
      %request = arith.constant true
      %condition = arith.constant true
      scf.if %condition {
        // expected-error @+1 {{greedy_fixed_priority must be directly inside an ac.process body}}
        %g = ac.arbitrate greedy_fixed_priority candidates [%request uses [@r]] : (i1)
      }
      ac.yield_sim
    }
    ac.return
  }
}

// -----

builtin.module attributes {ac.contract_epoch = "0.2"} {
  ac.module @Bad() parameters {} graph {
    ac.resource @r capacity 1 issue_width 1 ii 1
        latency {kind = "fixed", ticks = 1 : i64}
        lifecycle {reservation = "propose_commit", release = "balanced", cancellation = "explicit"}
        ownership "exclusive" classes [] id "r" path "r"
    ac.process @p kind "control" {
      %request = arith.constant true
      %g0 = ac.arbitrate greedy_fixed_priority candidates [%request uses [@r]] : (i1)
      // expected-note @-1 {{first arbiter using this resource is here}}
      // expected-error @+1 {{resource '@r' may belong to only one arbiter in a commit epoch}}
      %g1 = ac.arbitrate greedy_fixed_priority candidates [%request uses [@r]] : (i1)
      ac.yield_sim
    }
    ac.return
  }
}
