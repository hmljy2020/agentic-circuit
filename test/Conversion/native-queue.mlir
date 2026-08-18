// RUN: %acir_opt_public --verify-each=false --pass-pipeline='builtin.module(ac-freeze-topology)' %s -o %t.frozen
// RUN: %acir_opt_public --ac-lower-to-acsim --ac-binding-profile=fast --ac-binding-target=arm64-apple-darwin %t.frozen | %FileCheck %s

builtin.module attributes {ac.contract_epoch = "0.2"} {
  ac.protocol @fifo {
    ac.role @sender dual @receiver cardinality "exclusive"
    ac.role @receiver dual @sender cardinality "exclusive"
    ac.state @idle initial true terminal false
    ac.state @done initial false terminal true
    ac.event @push from @sender to @receiver payload i32 action "offer"
    ac.transition from @idle to @done on @push transfer true retain false guard {}
  }
  ac.system @soc root @Top as "root" tick 0 "cycle"
      workload @Top::@worker seed {kind = "fixed", value = 7 : i64}
      instrumentation [] results {id = "default", format = "json"} selected true
  ac.module @Top() parameters {} graph {
    ac.queue @fifo_queue payload i32 entries 1 bytes 4 ordering "fifo"
        protocol @fifo ownership "exclusive" id "fifo_queue" path "fifo_queue"
    ac.process @worker kind "workload" {
      %ten = arith.constant 10 : i32
      %accepted = ac.try_send @fifo_queue %ten : i32
      scf.if %accepted {
      } else {
        ac.await_queue @fifo_queue until "writable"
      }
      %value, %received = ac.try_recv @fifo_queue : i32
      scf.if %received {
      } else {
        ac.await_queue @fifo_queue until "readable"
      }
      ac.yield_sim
    }
    ac.return
  }
}

// CHECK: acsim.type @acir_queue_{{[0-9a-f]+}} cpp "gfsim::Queue<std::int32_t>" kind "runtime_object"
// CHECK-NOT: acsim.binding
// CHECK: %[[QUEUE:.+]] = acsim.instance @fifo_queue target @acir_queue_{{[0-9a-f]+}} args [1, 4]
// CHECK: acsim.process @worker captures(%[[QUEUE]] : !acsim.owner<@acir_queue_{{[0-9a-f]+}}>) names ["queue_fifo_queue"]
// CHECK: acsim.invoke @acir_impl_queue_try_send_{{[0-9a-f]+}}(%{{.+}}, %{{.+}}) : (!acsim.owner<@acir_queue_{{[0-9a-f]+}}>, i32) -> i1
// CHECK: acsim.invoke @acir_impl_wake_queue_writable_{{[0-9a-f]+}}(%{{.+}})
// CHECK: acsim.invoke @acir_impl_queue_try_recv_{{[0-9a-f]+}}(%{{.+}}) : (!acsim.owner<@acir_queue_{{[0-9a-f]+}}>) -> (i32, i1)
// CHECK: acsim.invoke @acir_impl_wake_queue_readable_{{[0-9a-f]+}}(%{{.+}})
// CHECK: acsim.dispatch @Top::@fifo_queue path "root.fifo_queue"
// CHECK: acsim.dispatch @Top::@worker path "root.worker"
// CHECK: acsim.activate %{{.+}} to %{{.+}}
