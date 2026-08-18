module attributes {ac.contract_epoch = "0.2", ac.freeze_epoch = "0.2", ac.frozen_instrumentation = [], ac.frozen_owners = [{kind = "ac.system_root", owner = @Top, path = "root", stable_id = "root"}, {kind = "ac.event_queue", owner = @Top::@complete, path = "root.complete", stable_id = "root/complete"}, {kind = "ac.event_queue", owner = @Top::@dispatch, path = "root.dispatch", stable_id = "root/dispatch"}, {kind = "ac.process", owner = @Top::@fu, path = "root.fu", stable_id = "root/fu"}, {kind = "ac.process", owner = @Top::@producer, path = "root.producer", stable_id = "root/producer"}, {kind = "ac.queue", owner = @Top::@results, path = "root.results", stable_id = "root/results"}, {kind = "ac.process", owner = @Top::@retire, path = "root.retire", stable_id = "root/retire"}, {kind = "ac.process", owner = @Top::@sink, path = "root.sink", stable_id = "root/sink"}], ac.frozen_primary_workload = {path = "root.producer", reference = @Top::@producer, stable_id = "root/producer"}, ac.frozen_system = @fu_demo, ac.topology_digest = "c3fa338fe6f22c1af53e9b2823eec71e05f9c8dbd1caaa51e082ad4282ead151", ac.topology_frozen = true} {
  ac.system @fu_demo root @Top as "root" tick 0 "cycle" workload @Top::@producer seed {kind = "fixed", value = 7 : i64} instrumentation [] results {format = "json", id = "default"} selected true
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
    ac.event_queue @complete payload !ac.event<i32> capacity 8 ordering "time_then_sequence" domain @core id "complete" path "complete" {ac.frozen_owners = [{kind = "ac.event_queue", owner = @Top::@complete, path = "root.complete", stable_id = "root/complete"}]}
    ac.event_queue @dispatch payload !ac.event<i32> capacity 8 ordering "time_then_sequence" domain @core id "dispatch" path "dispatch" {ac.frozen_owners = [{kind = "ac.event_queue", owner = @Top::@dispatch, path = "root.dispatch", stable_id = "root/dispatch"}]}
    ac.queue @results payload i32 entries 1 bytes 4 ordering "fifo" protocol @fifo ownership "exclusive" id "results" path "results" {ac.frozen_owners = [{kind = "ac.queue", owner = @Top::@results, path = "root.results", stable_id = "root/results"}]}
    ac.time_domain @core period 1 phase 0 scale 1
    ac.process @fu kind "control" {
      %value, %ready = ac.try_event @dispatch : i32
      scf.if %ready {
        %c1_i32 = arith.constant 1 : i32
        %0 = arith.addi %value, %c1_i32 : i32
        %c8_i32 = arith.constant 8 : i32
        %1 = arith.cmpi eq, %0, %c8_i32 : i32
        ac.assert %1, "fu result must equal 8"
        %c1_i64 = arith.constant 1 : i64
        %2 = ac.schedule @complete %0 after %c1_i64 : i32
      } else {
        ac.await_event @dispatch
      }
      ac.yield_sim
    } {ac.frozen_owners = [{kind = "ac.process", owner = @Top::@fu, path = "root.fu", stable_id = "root/fu"}], ac.frozen_process_skeleton = ["process/r0/b0/o0 ac.try_event{event_queue=@dispatch;}props={event_queue = @dispatch} operands= results=process/r0/b0/o0/v0:i32,process/r0/b0/o0/v1:i1, regions=", "process/r0/b0/o1 scf.if{}props=<<NULL ATTRIBUTE>> operands=process/r0/b0/o0/v1:i1, results= regions=[()][()]", "process/r0/b0/o1/r0/b0/o0 arith.constant{value=1 : i32;}props={value = 1 : i32} operands= results=process/r0/b0/o1/r0/b0/o0/v0:i32, regions=", "process/r0/b0/o1/r0/b0/o1 arith.addi{overflowFlags=#arith.overflow<none>;}props={overflowFlags = #arith.overflow<none>} operands=process/r0/b0/o0/v0:i32,process/r0/b0/o1/r0/b0/o0/v0:i32, results=process/r0/b0/o1/r0/b0/o1/v0:i32, regions=", "process/r0/b0/o1/r0/b0/o2 arith.constant{value=8 : i32;}props={value = 8 : i32} operands= results=process/r0/b0/o1/r0/b0/o2/v0:i32, regions=", "process/r0/b0/o1/r0/b0/o3 arith.cmpi{predicate=0 : i64;}props={predicate = 0 : i64} operands=process/r0/b0/o1/r0/b0/o1/v0:i32,process/r0/b0/o1/r0/b0/o2/v0:i32, results=process/r0/b0/o1/r0/b0/o3/v0:i1, regions=", "process/r0/b0/o1/r0/b0/o4 ac.assert{message=\22fu result must equal 8\22;}props={message = \22fu result must equal 8\22} operands=process/r0/b0/o1/r0/b0/o3/v0:i1, results= regions=", "process/r0/b0/o1/r0/b0/o5 arith.constant{value=1 : i64;}props={value = 1 : i64} operands= results=process/r0/b0/o1/r0/b0/o5/v0:i64, regions=", "process/r0/b0/o1/r0/b0/o6 ac.schedule{target=@complete;}props={target = @complete} operands=process/r0/b0/o1/r0/b0/o1/v0:i32,process/r0/b0/o1/r0/b0/o5/v0:i64, results=process/r0/b0/o1/r0/b0/o6/v0:i1, regions=", "process/r0/b0/o1/r0/b0/o7 scf.yield{}props=<<NULL ATTRIBUTE>> operands= results= regions=", "process/r0/b0/o1/r1/b0/o0 ac.await_event{event_queue=@dispatch;}props={event_queue = @dispatch} operands= results= regions=", "process/r0/b0/o1/r1/b0/o1 scf.yield{}props=<<NULL ATTRIBUTE>> operands= results= regions=", "process/r0/b0/o2 ac.yield_sim{}props=<<NULL ATTRIBUTE>> operands= results= regions="]}
    ac.process @producer kind "workload" {
      %c7_i32 = arith.constant 7 : i32
      %c2_i64 = arith.constant 2 : i64
      %0 = ac.schedule @dispatch %c7_i32 after %c2_i64 : i32
      ac.yield_sim
    } {ac.frozen_owners = [{kind = "ac.process", owner = @Top::@producer, path = "root.producer", stable_id = "root/producer"}], ac.frozen_process_skeleton = ["process/r0/b0/o0 arith.constant{value=7 : i32;}props={value = 7 : i32} operands= results=process/r0/b0/o0/v0:i32, regions=", "process/r0/b0/o1 arith.constant{value=2 : i64;}props={value = 2 : i64} operands= results=process/r0/b0/o1/v0:i64, regions=", "process/r0/b0/o2 ac.schedule{target=@dispatch;}props={target = @dispatch} operands=process/r0/b0/o0/v0:i32,process/r0/b0/o1/v0:i64, results=process/r0/b0/o2/v0:i1, regions=", "process/r0/b0/o3 ac.yield_sim{}props=<<NULL ATTRIBUTE>> operands= results= regions="]}
    ac.process @retire kind "control" {
      %value, %ready = ac.try_event @complete : i32
      scf.if %ready {
        %0 = ac.try_send @results %value : i32
        scf.if %0 {
        } else {
          ac.await_queue @results until "writable"
        }
      } else {
        ac.await_event @complete
      }
      ac.yield_sim
    } {ac.frozen_owners = [{kind = "ac.process", owner = @Top::@retire, path = "root.retire", stable_id = "root/retire"}], ac.frozen_process_skeleton = ["process/r0/b0/o0 ac.try_event{event_queue=@complete;}props={event_queue = @complete} operands= results=process/r0/b0/o0/v0:i32,process/r0/b0/o0/v1:i1, regions=", "process/r0/b0/o1 scf.if{}props=<<NULL ATTRIBUTE>> operands=process/r0/b0/o0/v1:i1, results= regions=[()][()]", "process/r0/b0/o1/r0/b0/o0 ac.try_send{queue=@results;}props={queue = @results} operands=process/r0/b0/o0/v0:i32, results=process/r0/b0/o1/r0/b0/o0/v0:i1, regions=", "process/r0/b0/o1/r0/b0/o1 scf.if{}props=<<NULL ATTRIBUTE>> operands=process/r0/b0/o1/r0/b0/o0/v0:i1, results= regions=[()][()]", "process/r0/b0/o1/r0/b0/o1/r0/b0/o0 scf.yield{}props=<<NULL ATTRIBUTE>> operands= results= regions=", "process/r0/b0/o1/r0/b0/o1/r1/b0/o0 ac.await_queue{queue=@results;until=\22writable\22;}props={queue = @results, until = \22writable\22} operands= results= regions=", "process/r0/b0/o1/r0/b0/o1/r1/b0/o1 scf.yield{}props=<<NULL ATTRIBUTE>> operands= results= regions=", "process/r0/b0/o1/r0/b0/o2 scf.yield{}props=<<NULL ATTRIBUTE>> operands= results= regions=", "process/r0/b0/o1/r1/b0/o0 ac.await_event{event_queue=@complete;}props={event_queue = @complete} operands= results= regions=", "process/r0/b0/o1/r1/b0/o1 scf.yield{}props=<<NULL ATTRIBUTE>> operands= results= regions=", "process/r0/b0/o2 ac.yield_sim{}props=<<NULL ATTRIBUTE>> operands= results= regions="]}
    ac.process @sink kind "control" {
      %value, %received = ac.try_recv @results : i32
      scf.if %received {
        %c8_i32 = arith.constant 8 : i32
        %0 = arith.cmpi eq, %value, %c8_i32 : i32
        ac.assert %0, "sink received value must be 8"
      } else {
        ac.await_queue @results until "readable"
      }
      ac.yield_sim
    } {ac.frozen_owners = [{kind = "ac.process", owner = @Top::@sink, path = "root.sink", stable_id = "root/sink"}], ac.frozen_process_skeleton = ["process/r0/b0/o0 ac.try_recv{queue=@results;}props={queue = @results} operands= results=process/r0/b0/o0/v0:i32,process/r0/b0/o0/v1:i1, regions=", "process/r0/b0/o1 scf.if{}props=<<NULL ATTRIBUTE>> operands=process/r0/b0/o0/v1:i1, results= regions=[()][()]", "process/r0/b0/o1/r0/b0/o0 arith.constant{value=8 : i32;}props={value = 8 : i32} operands= results=process/r0/b0/o1/r0/b0/o0/v0:i32, regions=", "process/r0/b0/o1/r0/b0/o1 arith.cmpi{predicate=0 : i64;}props={predicate = 0 : i64} operands=process/r0/b0/o0/v0:i32,process/r0/b0/o1/r0/b0/o0/v0:i32, results=process/r0/b0/o1/r0/b0/o1/v0:i1, regions=", "process/r0/b0/o1/r0/b0/o2 ac.assert{message=\22sink received value must be 8\22;}props={message = \22sink received value must be 8\22} operands=process/r0/b0/o1/r0/b0/o1/v0:i1, results= regions=", "process/r0/b0/o1/r0/b0/o3 scf.yield{}props=<<NULL ATTRIBUTE>> operands= results= regions=", "process/r0/b0/o1/r1/b0/o0 ac.await_queue{queue=@results;until=\22readable\22;}props={queue = @results, until = \22readable\22} operands= results= regions=", "process/r0/b0/o1/r1/b0/o1 scf.yield{}props=<<NULL ATTRIBUTE>> operands= results= regions=", "process/r0/b0/o2 ac.yield_sim{}props=<<NULL ATTRIBUTE>> operands= results= regions="]}
    ac.return
  }
}

