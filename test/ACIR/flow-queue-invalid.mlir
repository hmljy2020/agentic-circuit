// RUN: %acir_opt_public --split-input-file --verify-diagnostics %s

builtin.module attributes {ac.contract_epoch = "0.2"} {
  ac.protocol @ready_valid {
    ac.role @sender dual @receiver cardinality "exclusive"
    ac.role @receiver dual @sender cardinality "exclusive"
    ac.state @idle initial true terminal false
    ac.event @transfer from @sender to @receiver payload i32 action "offer"
    ac.event @transfer16 from @sender to @receiver payload i16 action "offer"
  }
  ac.module @Bad() -> !ac.flow<i32, @ready_valid> parameters {} graph {
    // expected-error @+1 {{ACFLOW-QUEUE-UNRESOLVED: queue '@missing' does not resolve to a local ac.queue}}
    %flow = ac.flow.export @missing : !ac.flow<i32, @ready_valid>
    ac.return %flow : !ac.flow<i32, @ready_valid>
  }
}

// -----

builtin.module attributes {ac.contract_epoch = "0.2"} {
  ac.protocol @ready_valid {
    ac.role @sender dual @receiver cardinality "exclusive"
    ac.role @receiver dual @sender cardinality "exclusive"
    ac.state @idle initial true terminal false
    ac.event @transfer from @sender to @receiver payload i32 action "offer"
    ac.event @transfer16 from @sender to @receiver payload i16 action "offer"
  }
  ac.module @Bad() -> !ac.flow<i32, @ready_valid> parameters {} graph {
    ac.queue @out payload i16 entries 1 ordering "fifo" protocol @ready_valid
        ownership "exclusive" id "out" path "out"
    // expected-error @+1 {{ACFLOW-PAYLOAD-MISMATCH: flow element type 'i32' does not match queue payload type 'i16'}}
    %flow = ac.flow.export @out : !ac.flow<i32, @ready_valid>
    ac.return %flow : !ac.flow<i32, @ready_valid>
  }
}

// -----

builtin.module attributes {ac.contract_epoch = "0.2"} {
  ac.protocol @ready_valid {
    ac.role @sender dual @receiver cardinality "exclusive"
    ac.role @receiver dual @sender cardinality "exclusive"
    ac.state @idle initial true terminal false
    ac.event @transfer from @sender to @receiver payload i32 action "offer"
  }
  ac.protocol @other {
    ac.role @sender dual @receiver cardinality "exclusive"
    ac.role @receiver dual @sender cardinality "exclusive"
    ac.state @idle initial true terminal false
    ac.event @transfer from @sender to @receiver payload i32 action "offer"
  }
  ac.module @Bad(!ac.flow<i32, @ready_valid>) parameters {} graph {
  ^bb0(%flow : !ac.flow<i32, @ready_valid>):
    ac.queue @in payload i32 entries 1 ordering "fifo" protocol @other
        ownership "exclusive" id "in" path "in"
    // expected-error @+1 {{ACFLOW-PROTOCOL-MISMATCH: flow protocol @ready_valid does not match queue protocol @other}}
    ac.flow.import %flow to @in : !ac.flow<i32, @ready_valid>
    ac.return
  }
}

// -----

builtin.module attributes {ac.contract_epoch = "0.2"} {
  ac.protocol @ready_valid {
    ac.role @sender dual @receiver cardinality "exclusive"
    ac.role @receiver dual @sender cardinality "exclusive"
    ac.state @idle initial true terminal false
    ac.event @transfer from @sender to @receiver payload i32 action "offer"
  }
  ac.module @Bad(!ac.flow<i32, @ready_valid>) parameters {} graph {
  ^bb0(%flow : !ac.flow<i32, @ready_valid>):
    ac.queue @in payload i32 entries 1 ordering "fifo" protocol @ready_valid
        ownership "exclusive" id "in" path "in"
    ac.flow.import %flow to @in : !ac.flow<i32, @ready_valid>
    ac.process @writer kind "control" {
      %zero = arith.constant 0 : i32
      // expected-error @+1 {{ACFLOW-QUEUE-ROLE: Flow destination queue 'in' cannot be written by a local process}}
      %accepted = ac.try_send @in %zero : i32
      ac.yield_sim
    }
    ac.return
  }
}
