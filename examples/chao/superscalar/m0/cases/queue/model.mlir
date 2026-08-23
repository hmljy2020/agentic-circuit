builtin.module attributes {ac.contract_epoch = "0.2"} {
  ac.protocol @fifo {
    ac.role @sender dual @receiver cardinality "exclusive"
    ac.role @receiver dual @sender cardinality "exclusive"
    ac.state @idle initial true terminal false
    ac.state @done initial false terminal true
    ac.event @push from @sender to @receiver payload i32 action "offer"
    ac.transition from @idle to @done on @push transfer true retain false guard {}
  }

  ac.system @m0_queue root @Top as "root" tick 0 "cycle"
      workload @Top::@producer seed {kind = "fixed", value = 7 : i64}
      instrumentation [] results {id = "default", format = "json"} selected true

  ac.module @Top() parameters {} graph {
    ac.queue @messages payload i32 entries 1 bytes 4 ordering "fifo"
        protocol @fifo ownership "exclusive" id "messages" path "messages"

    ac.process @producer kind "workload" {
      %value = arith.constant 10 : i32
      %accepted = ac.try_send @messages %value : i32
      scf.if %accepted {
      } else {
        ac.await_queue @messages until "writable"
      }
      ac.yield_sim
    }

    ac.process @consumer kind "control" {
      %head, %valid = ac.peek @messages : i32
      scf.if %valid {
        %ten = arith.constant 10 : i32
        %head_ok = arith.cmpi eq, %head, %ten : i32
        ac.assert %head_ok, "queue head must preserve the sent value"
      } else {
        ac.await_queue @messages until "readable"
      }
      %value, %received = ac.try_recv @messages : i32
      scf.if %received {
        %ten = arith.constant 10 : i32
        %value_ok = arith.cmpi eq, %value, %ten : i32
        ac.assert %value_ok, "queue receive must preserve the sent value"
      } else {
        ac.await_queue @messages until "readable"
      }
      ac.yield_sim
    }

    ac.return
  }
}
