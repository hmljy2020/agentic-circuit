// Contract 0.2 streaming adder example.
//
// A three-queue streaming adder. Every queue has the same specialization;
// stable paths distinguish instances without changing their implementation
// fingerprint.

builtin.module attributes {ac.contract_epoch = "0.2"} {
  ac.protocol @fifo {
    ac.role @sender dual @receiver cardinality "exclusive"
    ac.role @receiver dual @sender cardinality "exclusive"
    ac.state @idle initial true terminal false
    ac.state @done initial false terminal true
    ac.event @push from @sender to @receiver payload i32 action "offer"
    ac.transition from @idle to @done on @push transfer true retain false guard {}
  }

  ac.system @adder_demo root @Adder as "root" tick 0 "cycle"
      workload @Adder::@source seed {kind = "fixed", value = 0 : i64}
      instrumentation [] results {id = "default", format = "json"} selected true

  ac.module @Adder() parameters {} graph {
    ac.queue @op_a payload i32 entries 1 bytes 4 ordering "fifo"
        protocol @fifo ownership "exclusive" id "op_a" path "op_a"
    ac.queue @op_b payload i32 entries 1 bytes 4 ordering "fifo"
        protocol @fifo ownership "exclusive" id "op_b" path "op_b"
    ac.queue @result payload i32 entries 1 bytes 4 ordering "fifo"
        protocol @fifo ownership "exclusive" id "result" path "result"

    ac.process @source kind "workload" {
      %two = arith.constant 2 : i32
      %accepted_a = ac.try_send @op_a %two : i32
      scf.if %accepted_a {
      } else {
        ac.await_queue @op_a until "writable"
      }
      %three = arith.constant 3 : i32
      %accepted_b = ac.try_send @op_b %three : i32
      scf.if %accepted_b {
      } else {
        ac.await_queue @op_b until "writable"
      }
      ac.yield_sim
    }

    ac.process @adder kind "control" {
      %lhs, %received_a = ac.try_recv @op_a : i32
      scf.if %received_a {
      } else {
        ac.await_queue @op_a until "readable"
      }
      %rhs, %received_b = ac.try_recv @op_b : i32
      scf.if %received_b {
      } else {
        ac.await_queue @op_b until "readable"
      }
      %sum = arith.addi %lhs, %rhs : i32
      %five = arith.constant 5 : i32
      %correct = arith.cmpi eq, %sum, %five : i32
      ac.assert %correct, "adder result must equal 5"
      %accepted = ac.try_send @result %sum : i32
      scf.if %accepted {
      } else {
        ac.await_queue @result until "writable"
      }
      ac.yield_sim
    }

    ac.process @sink kind "control" {
      %value, %received = ac.try_recv @result : i32
      scf.if %received {
      } else {
        ac.await_queue @result until "readable"
      }
      ac.yield_sim
    }

    ac.return
  }
}
