module attributes {ac.contract_epoch = "0.2", ac.freeze_epoch = "0.2", ac.frozen_instrumentation = [], ac.frozen_owners = [{kind = "ac.system_root", owner = @Top, path = "root", stable_id = "root"}, {kind = "ac.process", owner = @Top::@consumer, path = "root.consumer", stable_id = "root/consumer"}, {kind = "ac.queue", owner = @Top::@messages, path = "root.messages", stable_id = "root/messages"}, {kind = "ac.process", owner = @Top::@producer, path = "root.producer", stable_id = "root/producer"}], ac.frozen_primary_workload = {path = "root.producer", reference = @Top::@producer, stable_id = "root/producer"}, ac.frozen_system = @queue_demo, ac.topology_digest = "d0b157a611b56a9a49dd56b206ae31571933459e7d521fc4c7199161f593fcdb", ac.topology_frozen = true} {
  ac.system @queue_demo root @Top as "root" tick 0 "cycle" workload @Top::@producer seed {kind = "fixed", value = 7 : i64} instrumentation [] results {format = "json", id = "default"} selected true
  ac.protocol @fifo {
    ac.role @receiver dual @sender cardinality "exclusive"
    ac.role @sender dual @receiver cardinality "exclusive"
    ac.state @done initial false terminal true
    ac.state @idle initial true terminal false
    ac.event @push from @sender to @receiver payload i32 action "offer"
    ac.transition from @idle to @done on @push transfer true retain false guard {
    }
  }
  ac.module @Top() parameters {} graph {
    ac.queue @messages payload i32 entries 1 bytes 4 ordering "fifo" protocol @fifo ownership "exclusive" id "messages" path "messages" {ac.frozen_owners = [{kind = "ac.queue", owner = @Top::@messages, path = "root.messages", stable_id = "root/messages"}]}
    ac.process @consumer kind "control" {
      %value, %received = ac.try_recv @messages : i32
      scf.if %received {
      } else {
        ac.await_queue @messages until "readable"
      }
      ac.yield_sim
    } {ac.frozen_owners = [{kind = "ac.process", owner = @Top::@consumer, path = "root.consumer", stable_id = "root/consumer"}], ac.frozen_process_skeleton = ["process/r0/b0/o0 ac.try_recv{queue=@messages;}props={queue = @messages} operands= results=process/r0/b0/o0/v0:i32,process/r0/b0/o0/v1:i1, regions=", "process/r0/b0/o1 scf.if{}props=<<NULL ATTRIBUTE>> operands=process/r0/b0/o0/v1:i1, results= regions=[()][()]", "process/r0/b0/o1/r0/b0/o0 scf.yield{}props=<<NULL ATTRIBUTE>> operands= results= regions=", "process/r0/b0/o1/r1/b0/o0 ac.await_queue{queue=@messages;until=\22readable\22;}props={queue = @messages, until = \22readable\22} operands= results= regions=", "process/r0/b0/o1/r1/b0/o1 scf.yield{}props=<<NULL ATTRIBUTE>> operands= results= regions=", "process/r0/b0/o2 ac.yield_sim{}props=<<NULL ATTRIBUTE>> operands= results= regions="]}
    ac.process @producer kind "workload" {
      %c10_i32 = arith.constant 10 : i32
      %0 = ac.try_send @messages %c10_i32 : i32
      scf.if %0 {
      } else {
        ac.await_queue @messages until "writable"
      }
      ac.yield_sim
    } {ac.frozen_owners = [{kind = "ac.process", owner = @Top::@producer, path = "root.producer", stable_id = "root/producer"}], ac.frozen_process_skeleton = ["process/r0/b0/o0 arith.constant{value=10 : i32;}props={value = 10 : i32} operands= results=process/r0/b0/o0/v0:i32, regions=", "process/r0/b0/o1 ac.try_send{queue=@messages;}props={queue = @messages} operands=process/r0/b0/o0/v0:i32, results=process/r0/b0/o1/v0:i1, regions=", "process/r0/b0/o2 scf.if{}props=<<NULL ATTRIBUTE>> operands=process/r0/b0/o1/v0:i1, results= regions=[()][()]", "process/r0/b0/o2/r0/b0/o0 scf.yield{}props=<<NULL ATTRIBUTE>> operands= results= regions=", "process/r0/b0/o2/r1/b0/o0 ac.await_queue{queue=@messages;until=\22writable\22;}props={queue = @messages, until = \22writable\22} operands= results= regions=", "process/r0/b0/o2/r1/b0/o1 scf.yield{}props=<<NULL ATTRIBUTE>> operands= results= regions=", "process/r0/b0/o3 ac.yield_sim{}props=<<NULL ATTRIBUTE>> operands= results= regions="]}
    ac.return
  }
}

