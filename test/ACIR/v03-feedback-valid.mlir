// This executable example proves that a cyclic Graph region is legal when
// its ordinary Queue SSA edges carry positive latency contracts.  No owned
// queue and no special feedback operation is required.
// RUN: %acir_opt %s | %FileCheck %s
// RUN: %acir_opt %s | %acir_opt | %FileCheck %s

builtin.module attributes {ac.contract_epoch = "0.3"} {
  ac.system @feedback_system root @feedback as "feedback" tick 0 "cycle"
      seed {kind = "fixed", value = 0 : i64} instrumentation []
      results {id = "default", format = "json"} selected true
  ac.module @feedback() parameters {} graph {
    %source = ac.source "input" : !ac.queue<i1, #ac.queue_contract<depth = 1, latency = 1, rate = 1, domain = @core, ordering = fifo>>
    %selected = ac.merge (%source, %completed) policy (#ac.policy<kind = round_robin>) : (!ac.queue<i1, #ac.queue_contract<depth = 1, latency = 1, rate = 1, domain = @core, ordering = fifo>>, !ac.queue<i1, #ac.queue_contract<depth = 1, latency = 1, rate = 1, domain = @core, ordering = fifo>>) -> !ac.queue<i1, #ac.queue_contract<depth = 1, latency = 1, rate = 1, domain = @core, ordering = fifo>>
    %completed = ac.compute %selected {
    ^bb0(%value: !ac.var<i1>):
      ac.var.yield %value : !ac.var<i1>
    } : (!ac.queue<i1, #ac.queue_contract<depth = 1, latency = 1, rate = 1, domain = @core, ordering = fifo>>) -> !ac.queue<i1, #ac.queue_contract<depth = 1, latency = 1, rate = 1, domain = @core, ordering = fifo>>
    ac.observe %completed as "completed" fields [] : !ac.queue<i1, #ac.queue_contract<depth = 1, latency = 1, rate = 1, domain = @core, ordering = fifo>>
    ac.return
  }
}

// CHECK: %{{.*}} = ac.merge(%{{.*}}, %{{.*}}) policy(#ac.policy<kind = round_robin>)
// CHECK: %{{.*}} = ac.compute %{{.*}}
