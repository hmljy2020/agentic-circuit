// RUN: %acir_opt_public --split-input-file --verify-diagnostics --ac-verify-model %s

builtin.module attributes {ac.contract_epoch = "0.2"} {
  ac.protocol @ready_valid {
    ac.role @sender dual @receiver cardinality "exclusive"
    ac.role @receiver dual @sender cardinality "exclusive"
    ac.state @idle initial true terminal false
    ac.event @transfer from @sender to @receiver payload i32 action "offer"
  }
  ac.system @system root @Producer as "root" tick 0 "cycle"
      seed {kind = "fixed", value = 0 : i64} instrumentation []
      results {id = "default", format = "json"} selected true
  // expected-error @+1 {{ACFLOW-ROOT-ESCAPE: selected root Flow result 0 escapes to the harness}}
  ac.module @Producer() -> !ac.flow<i32, @ready_valid> parameters {} graph {
    ac.queue @out payload i32 entries 1 ordering "fifo" protocol @ready_valid
        ownership "exclusive" id "out" path "out"
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
  ac.system @system root @Top as "root" tick 0 "cycle"
      seed {kind = "fixed", value = 0 : i64} instrumentation []
      results {id = "default", format = "json"} selected true
  ac.module @Producer() -> !ac.flow<i32, @ready_valid> parameters {} graph {
    ac.queue @out payload i32 entries 1 ordering "fifo" protocol @ready_valid
        ownership "exclusive" id "out" path "out"
    // expected-error @+1 {{ACFLOW-DANGLING-EXPORT: Flow export has no import in the selected root hierarchy}}
    %flow = ac.flow.export @out : !ac.flow<i32, @ready_valid>
    ac.return %flow : !ac.flow<i32, @ready_valid>
  }
  ac.module @Top() parameters {} graph {
    %unused = ac.instance @producer of @Producer() static {} id "producer"
        path "producer" : () -> !ac.flow<i32, @ready_valid>
    ac.return
  }
}
