builtin.module attributes {ac.contract_epoch = "0.2"} {
  ac.protocol @fifo {
    ac.role @sender dual @receiver cardinality "exclusive"
    ac.role @receiver dual @sender cardinality "exclusive"
    ac.state @idle initial true terminal false
    ac.state @done initial false terminal true
    ac.event @push from @sender to @receiver payload i32 action "offer"
    ac.transition from @idle to @done on @push transfer true retain false guard {}
  }

  ac.system @m0_event_latency root @Top as "root" tick 0 "cycle"
      workload @Top::@producer seed {kind = "fixed", value = 7 : i64}
      instrumentation [] results {id = "default", format = "json"} selected true

  ac.module @Top() parameters {} graph {
    ac.time_domain @core period 1 phase 0 scale 1
    ac.event_queue @dispatch payload !ac.event<i32> capacity 8
        ordering "time_then_sequence" domain @core id "dispatch" path "dispatch"
    ac.event_queue @complete payload !ac.event<i32> capacity 8
        ordering "time_then_sequence" domain @core id "complete" path "complete"
    ac.event_queue @ordered payload !ac.event<i32> capacity 16
        ordering "time_then_sequence" domain @core id "ordered" path "ordered"
    ac.queue @results payload i32 entries 1 bytes 4 ordering "fifo"
        protocol @fifo ownership "exclusive" id "results" path "results"

    ac.process @producer kind "workload" {
      %payload = arith.constant 7 : i32
      %delay = arith.constant 2 : i64
      %accepted = ac.schedule @dispatch %payload after %delay : i32
      // Both events have the same ready tick.  The consumer below checks that
      // insertion sequence breaks the tie deterministically.
      %first = arith.constant 70 : i32
      %first_ok = ac.schedule @ordered %first after %delay : i32
      %second = arith.constant 71 : i32
      %second_ok = ac.schedule @ordered %second after %delay : i32
      ac.yield_sim
    }

    ac.process @order_checker kind "control" {
      %first, %first_ready = ac.try_event @ordered : i32
      scf.if %first_ready {
        %expected_first = arith.constant 70 : i32
        %first_correct = arith.cmpi eq, %first, %expected_first : i32
        ac.assert %first_correct, "same-tick events must preserve insertion order"
      } else {
        ac.await_event @ordered
      }
      %second, %second_ready = ac.try_event @ordered : i32
      scf.if %second_ready {
        %expected_second = arith.constant 71 : i32
        %second_correct = arith.cmpi eq, %second, %expected_second : i32
        ac.assert %second_correct, "same-tick events must preserve insertion order"
      } else {
        ac.await_event @ordered
      }
      ac.yield_sim
    }

    ac.process @fu kind "control" {
      %value, %ready = ac.try_event @dispatch : i32
      scf.if %ready {
        %one = arith.constant 1 : i32
        %result = arith.addi %value, %one : i32
        %eight = arith.constant 8 : i32
        %correct = arith.cmpi eq, %result, %eight : i32
        ac.assert %correct, "FU result must equal 8"
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
        ac.assert %correct, "sink must receive the FU result"
      } else {
        ac.await_queue @results until "readable"
      }
      ac.yield_sim
    }

    ac.return
  }
}
