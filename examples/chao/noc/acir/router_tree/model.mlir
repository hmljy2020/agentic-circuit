// Three 1x2 routers arranged as a two-level tree. Flit bits [1:0] select
// leaf0..leaf3 and bits [31:2] carry the payload.

builtin.module attributes {ac.contract_epoch = "0.2"} {
  ac.protocol @fifo {
    ac.role @sender dual @receiver cardinality "exclusive"
    ac.role @receiver dual @sender cardinality "exclusive"
    ac.state @idle initial true terminal false
    ac.state @done initial false terminal true
    ac.event @push from @sender to @receiver payload i32 action "offer"
    ac.transition from @idle to @done on @push transfer true retain false guard {}
  }

  ac.system @router_tree_demo root @Top as "root" tick 0 "cycle"
      workload @Top::@producer seed {kind = "fixed", value = 0 : i64}
      instrumentation [] results {id = "default", format = "json"} selected true

  ac.module @Top() parameters {} graph {
    ac.queue @ingress payload i32 entries 1 bytes 4 ordering "fifo"
        protocol @fifo ownership "exclusive" id "ingress" path "ingress"
    ac.queue @trunk_left payload i32 entries 1 bytes 4 ordering "fifo"
        protocol @fifo ownership "exclusive" id "trunk_left" path "trunk_left"
    ac.queue @trunk_right payload i32 entries 1 bytes 4 ordering "fifo"
        protocol @fifo ownership "exclusive" id "trunk_right" path "trunk_right"
    ac.queue @leaf0 payload i32 entries 1 bytes 4 ordering "fifo"
        protocol @fifo ownership "exclusive" id "leaf0" path "leaf0"
    ac.queue @leaf1 payload i32 entries 1 bytes 4 ordering "fifo"
        protocol @fifo ownership "exclusive" id "leaf1" path "leaf1"
    ac.queue @leaf2 payload i32 entries 1 bytes 4 ordering "fifo"
        protocol @fifo ownership "exclusive" id "leaf2" path "leaf2"
    ac.queue @leaf3 payload i32 entries 1 bytes 4 ordering "fifo"
        protocol @fifo ownership "exclusive" id "leaf3" path "leaf3"

    ac.process @producer kind "workload" {
      %flit0 = arith.constant 4 : i32
      %sent0 = ac.try_send @ingress %flit0 : i32
      scf.if %sent0 {
      } else {
        ac.await_queue @ingress until "writable"
      }
      %flit1 = arith.constant 9 : i32
      %sent1 = ac.try_send @ingress %flit1 : i32
      scf.if %sent1 {
      } else {
        ac.await_queue @ingress until "writable"
      }
      %flit2 = arith.constant 14 : i32
      %sent2 = ac.try_send @ingress %flit2 : i32
      scf.if %sent2 {
      } else {
        ac.await_queue @ingress until "writable"
      }
      %flit3 = arith.constant 19 : i32
      %sent3 = ac.try_send @ingress %flit3 : i32
      scf.if %sent3 {
      } else {
        ac.await_queue @ingress until "writable"
      }
      %flit4 = arith.constant 20 : i32
      %sent4 = ac.try_send @ingress %flit4 : i32
      scf.if %sent4 {
      } else {
        ac.await_queue @ingress until "writable"
      }
      %flit5 = arith.constant 25 : i32
      %sent5 = ac.try_send @ingress %flit5 : i32
      scf.if %sent5 {
      } else {
        ac.await_queue @ingress until "writable"
      }
      %flit6 = arith.constant 30 : i32
      %sent6 = ac.try_send @ingress %flit6 : i32
      scf.if %sent6 {
      } else {
        ac.await_queue @ingress until "writable"
      }
      %flit7 = arith.constant 35 : i32
      %sent7 = ac.try_send @ingress %flit7 : i32
      scf.if %sent7 {
      } else {
        ac.await_queue @ingress until "writable"
      }
      ac.yield_sim
    }

    ac.process @root_router kind "control" {
      %flit, %valid = ac.peek @ingress : i32
      scf.if %valid {
      } else {
        ac.await_queue @ingress until "readable"
      }
      %received_flit, %received = ac.try_recv @ingress : i32
      ac.assert %received, "peeked ingress flit must remain receivable"
      %same_flit = arith.cmpi eq, %received_flit, %flit : i32
      ac.assert %same_flit, "received ingress flit must match peek"
      %one = arith.constant 1 : i32
      %route = arith.shrui %flit, %one : i32
      %branch = arith.andi %route, %one : i32
      %zero = arith.constant 0 : i32
      %go_right = arith.cmpi ne, %branch, %zero : i32
      scf.if %go_right {
        %sent = ac.try_send @trunk_right %flit : i32
        scf.if %sent {
        } else {
          ac.await_queue @trunk_right until "writable"
        }
      } else {
        %sent = ac.try_send @trunk_left %flit : i32
        scf.if %sent {
        } else {
          ac.await_queue @trunk_left until "writable"
        }
      }
      ac.yield_sim
    }

    ac.process @left_router kind "control" {
      %flit, %valid = ac.peek @trunk_left : i32
      scf.if %valid {
      } else {
        ac.await_queue @trunk_left until "readable"
      }
      %received_flit, %received = ac.try_recv @trunk_left : i32
      ac.assert %received, "peeked left flit must remain receivable"
      %same_flit = arith.cmpi eq, %received_flit, %flit : i32
      ac.assert %same_flit, "received left flit must match peek"
      %one = arith.constant 1 : i32
      %branch = arith.andi %flit, %one : i32
      %zero = arith.constant 0 : i32
      %go_high = arith.cmpi ne, %branch, %zero : i32
      scf.if %go_high {
        %sent = ac.try_send @leaf1 %flit : i32
        scf.if %sent {
        } else {
          ac.await_queue @leaf1 until "writable"
        }
      } else {
        %sent = ac.try_send @leaf0 %flit : i32
        scf.if %sent {
        } else {
          ac.await_queue @leaf0 until "writable"
        }
      }
      ac.yield_sim
    }

    ac.process @right_router kind "control" {
      %flit, %valid = ac.peek @trunk_right : i32
      scf.if %valid {
      } else {
        ac.await_queue @trunk_right until "readable"
      }
      %received_flit, %received = ac.try_recv @trunk_right : i32
      ac.assert %received, "peeked right flit must remain receivable"
      %same_flit = arith.cmpi eq, %received_flit, %flit : i32
      ac.assert %same_flit, "received right flit must match peek"
      %one = arith.constant 1 : i32
      %branch = arith.andi %flit, %one : i32
      %zero = arith.constant 0 : i32
      %go_high = arith.cmpi ne, %branch, %zero : i32
      scf.if %go_high {
        %sent = ac.try_send @leaf3 %flit : i32
        scf.if %sent {
        } else {
          ac.await_queue @leaf3 until "writable"
        }
      } else {
        %sent = ac.try_send @leaf2 %flit : i32
        scf.if %sent {
        } else {
          ac.await_queue @leaf2 until "writable"
        }
      }
      ac.yield_sim
    }

    ac.process @sink0 kind "control" {
      %first, %received0 = ac.try_recv @leaf0 : i32
      scf.if %received0 {
      } else {
        ac.await_queue @leaf0 until "readable"
      }
      %expected0 = arith.constant 4 : i32
      %correct0 = arith.cmpi eq, %first, %expected0 : i32
      ac.assert %correct0, "leaf0 first flit must be 4"
      %second, %received1 = ac.try_recv @leaf0 : i32
      scf.if %received1 {
      } else {
        ac.await_queue @leaf0 until "readable"
      }
      %expected1 = arith.constant 20 : i32
      %correct1 = arith.cmpi eq, %second, %expected1 : i32
      ac.assert %correct1, "leaf0 second flit must be 20"
      ac.yield_sim
    }

    ac.process @sink1 kind "control" {
      %first, %received0 = ac.try_recv @leaf1 : i32
      scf.if %received0 {
      } else {
        ac.await_queue @leaf1 until "readable"
      }
      %expected0 = arith.constant 9 : i32
      %correct0 = arith.cmpi eq, %first, %expected0 : i32
      ac.assert %correct0, "leaf1 first flit must be 9"
      %second, %received1 = ac.try_recv @leaf1 : i32
      scf.if %received1 {
      } else {
        ac.await_queue @leaf1 until "readable"
      }
      %expected1 = arith.constant 25 : i32
      %correct1 = arith.cmpi eq, %second, %expected1 : i32
      ac.assert %correct1, "leaf1 second flit must be 25"
      ac.yield_sim
    }

    ac.process @sink2 kind "control" {
      %first, %received0 = ac.try_recv @leaf2 : i32
      scf.if %received0 {
      } else {
        ac.await_queue @leaf2 until "readable"
      }
      %expected0 = arith.constant 14 : i32
      %correct0 = arith.cmpi eq, %first, %expected0 : i32
      ac.assert %correct0, "leaf2 first flit must be 14"
      %second, %received1 = ac.try_recv @leaf2 : i32
      scf.if %received1 {
      } else {
        ac.await_queue @leaf2 until "readable"
      }
      %expected1 = arith.constant 30 : i32
      %correct1 = arith.cmpi eq, %second, %expected1 : i32
      ac.assert %correct1, "leaf2 second flit must be 30"
      ac.yield_sim
    }

    ac.process @sink3 kind "control" {
      %first, %received0 = ac.try_recv @leaf3 : i32
      scf.if %received0 {
      } else {
        ac.await_queue @leaf3 until "readable"
      }
      %expected0 = arith.constant 19 : i32
      %correct0 = arith.cmpi eq, %first, %expected0 : i32
      ac.assert %correct0, "leaf3 first flit must be 19"
      %second, %received1 = ac.try_recv @leaf3 : i32
      scf.if %received1 {
      } else {
        ac.await_queue @leaf3 until "readable"
      }
      %expected1 = arith.constant 35 : i32
      %correct1 = arith.cmpi eq, %second, %expected1 : i32
      ac.assert %correct1, "leaf3 second flit must be 35"
      ac.yield_sim
    }

    ac.return
  }
}
