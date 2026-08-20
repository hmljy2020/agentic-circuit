// RUN: %acir_opt_public --split-input-file --verify-diagnostics %s

builtin.module attributes {ac.contract_epoch = "0.2"} {
  ac.module @Bad() parameters {} graph {
    ac.process @p kind "control" {
      %r = arith.constant true
      // expected-error @+1 {{policy must be exactly 'greedy_fixed_priority'}}
      %g = ac.arbitrate round_robin candidates [%r uses []] : (i1)
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
