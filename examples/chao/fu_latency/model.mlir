// Contract 0.2 dispatch and latency completion example.
//
// A workload process schedules one work item (payload 7) into the dispatch
// event queue every tick with a two-tick delay. A functional-unit control
// process pops it, adds one, asserts the result, and re-schedules it into a
// completion event queue with a one-tick latency. A retire control process
// forwards completed events into a native FIFO, and a sink control process
// consumes and checks them. All processes stream continuously and the run is
// capped by maxTicks (see runner.cpp).

builtin.module attributes {ac.contract_epoch = "0.2"} {
  ac.protocol @fifo {
    ac.role @sender dual @receiver cardinality "exclusive"
    ac.role @receiver dual @sender cardinality "exclusive"
    ac.state @idle initial true terminal false
    ac.state @done initial false terminal true
    ac.event @push from @sender to @receiver payload i32 action "offer"
    ac.transition from @idle to @done on @push transfer true retain false guard {}
  }

  ac.system @fu_demo root @Top as "root" tick 0 "cycle"
      workload @Top::@producer seed {kind = "fixed", value = 7 : i64}
      instrumentation [] results {id = "default", format = "json"} selected true

  ac.module @Top() parameters {} graph {
    ac.time_domain @core period 1 phase 0 scale 1
    ac.event_queue @dispatch payload !ac.event<i32> capacity 8
        ordering "time_then_sequence" domain @core id "dispatch" path "dispatch"
    ac.event_queue @complete payload !ac.event<i32> capacity 8
        ordering "time_then_sequence" domain @core id "complete" path "complete"
    ac.queue @results payload i32 entries 1 bytes 4 ordering "fifo"
        protocol @fifo ownership "exclusive" id "results" path "results"

    ac.process @producer kind "workload" {
      %payload = arith.constant 7 : i32
      %delay = arith.constant 2 : i64
      %accepted = ac.schedule @dispatch %payload after %delay : i32
      ac.yield_sim
    }

    ac.process @fu kind "control" {
      %value, %ready = ac.try_event @dispatch : i32
      scf.if %ready {
        %one = arith.constant 1 : i32
        %result = arith.addi %value, %one : i32
        %eight = arith.constant 8 : i32
        %correct = arith.cmpi eq, %result, %eight : i32
        ac.assert %correct, "fu result must equal 8"
        %latency = arith.constant 1 : i64
        %accepted = ac.schedule @complete %result after %latency : i32
      } else {
        ac.await_event @dispatch
      }
      ac.yield_sim
    }

    ac.process @retire kind "control" {
      %value, %ready = ac.try_event @complete : i32
      scf.if %ready {
        %accepted = ac.try_send @results %value : i32
        scf.if %accepted {
        } else {
          ac.await_queue @results until "writable"
        }
      } else {
        ac.await_event @complete
      }
      ac.yield_sim
    }

    ac.process @sink kind "control" {
      %value, %received = ac.try_recv @results : i32
      scf.if %received {
        %eight = arith.constant 8 : i32
        %correct = arith.cmpi eq, %value, %eight : i32
        ac.assert %correct, "sink received value must be 8"
      } else {
        ac.await_queue @results until "readable"
      }
      ac.yield_sim
    }

    ac.return
  }
}
