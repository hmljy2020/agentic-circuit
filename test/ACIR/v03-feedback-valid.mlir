// This executable example proves that a cyclic Graph region is legal when
// its ordinary Queue SSA edges carry positive latency contracts.  No owned
// queue and no special feedback operation is required.
// RUN: %acir_opt --pass-pipeline='builtin.module(ac-verify-model)' %s | %FileCheck %s
// RUN: %acir_opt %s | %acir_opt --pass-pipeline='builtin.module(ac-verify-model)' | %FileCheck %s

builtin.module attributes {ac.contract_epoch = "0.3"} {
  ac.system @feedback_system root @feedback as "feedback" tick 0 "cycle"
      seed {kind = "fixed", value = 0 : i64} instrumentation []
      results {id = "default", format = "json"} selected true
  ac.module @feedback() parameters {} graph {
    %source = ac.v03.source "input" : !ac.queue_v03<i1, #ac.queue_contract<depth = 1, latency = 1, rate = 1, domain = @core, ordering = fifo>>
    %selected = ac.v03.merge (%source, %completed) policy (#ac.policy<kind = round_robin>) : (!ac.queue_v03<i1, #ac.queue_contract<depth = 1, latency = 1, rate = 1, domain = @core, ordering = fifo>>, !ac.queue_v03<i1, #ac.queue_contract<depth = 1, latency = 1, rate = 1, domain = @core, ordering = fifo>>) -> !ac.queue_v03<i1, #ac.queue_contract<depth = 1, latency = 1, rate = 1, domain = @core, ordering = fifo>>
    %completed = ac.compute %selected {
    ^bb0(%value: !ac.var<i1>):
      ac.var.yield %value : !ac.var<i1>
    } : (!ac.queue_v03<i1, #ac.queue_contract<depth = 1, latency = 1, rate = 1, domain = @core, ordering = fifo>>) -> !ac.queue_v03<i1, #ac.queue_contract<depth = 1, latency = 1, rate = 1, domain = @core, ordering = fifo>>
    ac.v03.observe %completed as "completed" fields [] : !ac.queue_v03<i1, #ac.queue_contract<depth = 1, latency = 1, rate = 1, domain = @core, ordering = fifo>>
    ac.return
  }
}

// CHECK: %{{.*}} = ac.v03.merge(%{{.*}}, %{{.*}}) policy(#ac.policy<kind = round_robin>)
// CHECK: %{{.*}} = ac.compute %{{.*}}
