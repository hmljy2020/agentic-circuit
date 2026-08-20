module attributes {ac.contract_epoch = "0.2", ac.freeze_epoch = "0.2", ac.frozen_instrumentation = [], ac.frozen_owners = [{kind = "ac.system_root", owner = @Top, path = "root", stable_id = "root"}, {kind = "ac.process", owner = @Top::@arbiter, path = "root.arbiter", stable_id = "root/arbiter"}, {kind = "ac.queue", owner = @Top::@in0, path = "root.in0", stable_id = "root/in0"}, {kind = "ac.queue", owner = @Top::@in1, path = "root.in1", stable_id = "root/in1"}, {kind = "ac.queue", owner = @Top::@out0, path = "root.out0", stable_id = "root/out0"}, {kind = "ac.queue", owner = @Top::@out1, path = "root.out1", stable_id = "root/out1"}, {kind = "ac.process", owner = @Top::@producer0, path = "root.producer0", stable_id = "root/producer0"}, {kind = "ac.process", owner = @Top::@producer1, path = "root.producer1", stable_id = "root/producer1"}, {kind = "ac.process", owner = @Top::@sink0, path = "root.sink0", stable_id = "root/sink0"}, {kind = "ac.process", owner = @Top::@sink1, path = "root.sink1", stable_id = "root/sink1"}], ac.frozen_primary_workload = {path = "root.producer0", reference = @Top::@producer0, stable_id = "root/producer0"}, ac.frozen_system = @router2x2_demo, ac.topology_digest = "ef3f02ccf8fb575bf85aaed30e9b529308ccef3a67466d8fab3a820fecd7b1f8", ac.topology_frozen = true} {
  ac.system @router2x2_demo root @Top as "root" tick 0 "cycle" workload @Top::@producer0 seed {kind = "fixed", value = 0 : i64} instrumentation [] results {format = "json", id = "default"} selected true
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
    ac.queue @in0 payload i32 entries 16 bytes 64 ordering "fifo" protocol @fifo ownership "exclusive" id "in0" path "in0" {ac.frozen_owners = [{kind = "ac.queue", owner = @Top::@in0, path = "root.in0", stable_id = "root/in0"}]}
    ac.queue @in1 payload i32 entries 16 bytes 64 ordering "fifo" protocol @fifo ownership "exclusive" id "in1" path "in1" {ac.frozen_owners = [{kind = "ac.queue", owner = @Top::@in1, path = "root.in1", stable_id = "root/in1"}]}
    ac.queue @out0 payload i32 entries 16 bytes 64 ordering "fifo" protocol @fifo ownership "exclusive" id "out0" path "out0" {ac.frozen_owners = [{kind = "ac.queue", owner = @Top::@out0, path = "root.out0", stable_id = "root/out0"}]}
    ac.queue @out1 payload i32 entries 16 bytes 64 ordering "fifo" protocol @fifo ownership "exclusive" id "out1" path "out1" {ac.frozen_owners = [{kind = "ac.queue", owner = @Top::@out1, path = "root.out1", stable_id = "root/out1"}]}
    ac.process @arbiter kind "control" {
      %value, %valid = ac.peek @in0 : i32
      scf.if %valid {
        %value_0, %received = ac.try_recv @in0 : i32
        ac.assert %received, "peeked in0 flit must remain receivable"
        %0 = arith.cmpi eq, %value_0, %value : i32
        ac.assert %0, "in0 receive must match peek"
        %c3_i32 = arith.constant 3 : i32
        %c0_i32 = arith.constant 0 : i32
        %1 = arith.andi %value_0, %c3_i32 : i32
        %2 = arith.cmpi eq, %1, %c0_i32 : i32
        scf.if %2 {
          %3 = ac.try_send @out0 %value_0 : i32
          scf.if %3 {
          } else {
            ac.await_queue @out0 until "writable"
          }
        } else {
          %3 = ac.try_send @out1 %value_0 : i32
          scf.if %3 {
          } else {
            ac.await_queue @out1 until "writable"
          }
        }
      } else {
        %value_0, %valid_1 = ac.peek @in1 : i32
        scf.if %valid_1 {
          %value_2, %received = ac.try_recv @in1 : i32
          ac.assert %received, "peeked in1 flit must remain receivable"
          %0 = arith.cmpi eq, %value_2, %value_0 : i32
          ac.assert %0, "in1 receive must match peek"
          %c3_i32 = arith.constant 3 : i32
          %c0_i32 = arith.constant 0 : i32
          %1 = arith.andi %value_2, %c3_i32 : i32
          %2 = arith.cmpi eq, %1, %c0_i32 : i32
          scf.if %2 {
            %3 = ac.try_send @out0 %value_2 : i32
            scf.if %3 {
            } else {
              ac.await_queue @out0 until "writable"
            }
          } else {
            %3 = ac.try_send @out1 %value_2 : i32
            scf.if %3 {
            } else {
              ac.await_queue @out1 until "writable"
            }
          }
        }
      }
      ac.yield_sim
    } {ac.frozen_owners = [{kind = "ac.process", owner = @Top::@arbiter, path = "root.arbiter", stable_id = "root/arbiter"}], ac.frozen_process_skeleton = ["process/r0/b0/o0 ac.peek{queue=@in0;}props={queue = @in0} operands= results=process/r0/b0/o0/v0:i32,process/r0/b0/o0/v1:i1, regions=", "process/r0/b0/o1 scf.if{}props=<<NULL ATTRIBUTE>> operands=process/r0/b0/o0/v1:i1, results= regions=[()][()]", "process/r0/b0/o1/r0/b0/o0 ac.try_recv{queue=@in0;}props={queue = @in0} operands= results=process/r0/b0/o1/r0/b0/o0/v0:i32,process/r0/b0/o1/r0/b0/o0/v1:i1, regions=", "process/r0/b0/o1/r0/b0/o1 ac.assert{message=\22peeked in0 flit must remain receivable\22;}props={message = \22peeked in0 flit must remain receivable\22} operands=process/r0/b0/o1/r0/b0/o0/v1:i1, results= regions=", "process/r0/b0/o1/r0/b0/o2 arith.cmpi{predicate=0 : i64;}props={predicate = 0 : i64} operands=process/r0/b0/o1/r0/b0/o0/v0:i32,process/r0/b0/o0/v0:i32, results=process/r0/b0/o1/r0/b0/o2/v0:i1, regions=", "process/r0/b0/o1/r0/b0/o3 ac.assert{message=\22in0 receive must match peek\22;}props={message = \22in0 receive must match peek\22} operands=process/r0/b0/o1/r0/b0/o2/v0:i1, results= regions=", "process/r0/b0/o1/r0/b0/o4 arith.constant{value=3 : i32;}props={value = 3 : i32} operands= results=process/r0/b0/o1/r0/b0/o4/v0:i32, regions=", "process/r0/b0/o1/r0/b0/o5 arith.constant{value=0 : i32;}props={value = 0 : i32} operands= results=process/r0/b0/o1/r0/b0/o5/v0:i32, regions=", "process/r0/b0/o1/r0/b0/o6 arith.andi{}props=<<NULL ATTRIBUTE>> operands=process/r0/b0/o1/r0/b0/o0/v0:i32,process/r0/b0/o1/r0/b0/o4/v0:i32, results=process/r0/b0/o1/r0/b0/o6/v0:i32, regions=", "process/r0/b0/o1/r0/b0/o7 arith.cmpi{predicate=0 : i64;}props={predicate = 0 : i64} operands=process/r0/b0/o1/r0/b0/o6/v0:i32,process/r0/b0/o1/r0/b0/o5/v0:i32, results=process/r0/b0/o1/r0/b0/o7/v0:i1, regions=", "process/r0/b0/o1/r0/b0/o8 scf.if{}props=<<NULL ATTRIBUTE>> operands=process/r0/b0/o1/r0/b0/o7/v0:i1, results= regions=[()][()]", "process/r0/b0/o1/r0/b0/o8/r0/b0/o0 ac.try_send{queue=@out0;}props={queue = @out0} operands=process/r0/b0/o1/r0/b0/o0/v0:i32, results=process/r0/b0/o1/r0/b0/o8/r0/b0/o0/v0:i1, regions=", "process/r0/b0/o1/r0/b0/o8/r0/b0/o1 scf.if{}props=<<NULL ATTRIBUTE>> operands=process/r0/b0/o1/r0/b0/o8/r0/b0/o0/v0:i1, results= regions=[()][()]", "process/r0/b0/o1/r0/b0/o8/r0/b0/o1/r0/b0/o0 scf.yield{}props=<<NULL ATTRIBUTE>> operands= results= regions=", "process/r0/b0/o1/r0/b0/o8/r0/b0/o1/r1/b0/o0 ac.await_queue{queue=@out0;until=\22writable\22;}props={queue = @out0, until = \22writable\22} operands= results= regions=", "process/r0/b0/o1/r0/b0/o8/r0/b0/o1/r1/b0/o1 scf.yield{}props=<<NULL ATTRIBUTE>> operands= results= regions=", "process/r0/b0/o1/r0/b0/o8/r0/b0/o2 scf.yield{}props=<<NULL ATTRIBUTE>> operands= results= regions=", "process/r0/b0/o1/r0/b0/o8/r1/b0/o0 ac.try_send{queue=@out1;}props={queue = @out1} operands=process/r0/b0/o1/r0/b0/o0/v0:i32, results=process/r0/b0/o1/r0/b0/o8/r1/b0/o0/v0:i1, regions=", "process/r0/b0/o1/r0/b0/o8/r1/b0/o1 scf.if{}props=<<NULL ATTRIBUTE>> operands=process/r0/b0/o1/r0/b0/o8/r1/b0/o0/v0:i1, results= regions=[()][()]", "process/r0/b0/o1/r0/b0/o8/r1/b0/o1/r0/b0/o0 scf.yield{}props=<<NULL ATTRIBUTE>> operands= results= regions=", "process/r0/b0/o1/r0/b0/o8/r1/b0/o1/r1/b0/o0 ac.await_queue{queue=@out1;until=\22writable\22;}props={queue = @out1, until = \22writable\22} operands= results= regions=", "process/r0/b0/o1/r0/b0/o8/r1/b0/o1/r1/b0/o1 scf.yield{}props=<<NULL ATTRIBUTE>> operands= results= regions=", "process/r0/b0/o1/r0/b0/o8/r1/b0/o2 scf.yield{}props=<<NULL ATTRIBUTE>> operands= results= regions=", "process/r0/b0/o1/r0/b0/o9 scf.yield{}props=<<NULL ATTRIBUTE>> operands= results= regions=", "process/r0/b0/o1/r1/b0/o0 ac.peek{queue=@in1;}props={queue = @in1} operands= results=process/r0/b0/o1/r1/b0/o0/v0:i32,process/r0/b0/o1/r1/b0/o0/v1:i1, regions=", "process/r0/b0/o1/r1/b0/o1 scf.if{}props=<<NULL ATTRIBUTE>> operands=process/r0/b0/o1/r1/b0/o0/v1:i1, results= regions=[()][]", "process/r0/b0/o1/r1/b0/o1/r0/b0/o0 ac.try_recv{queue=@in1;}props={queue = @in1} operands= results=process/r0/b0/o1/r1/b0/o1/r0/b0/o0/v0:i32,process/r0/b0/o1/r1/b0/o1/r0/b0/o0/v1:i1, regions=", "process/r0/b0/o1/r1/b0/o1/r0/b0/o1 ac.assert{message=\22peeked in1 flit must remain receivable\22;}props={message = \22peeked in1 flit must remain receivable\22} operands=process/r0/b0/o1/r1/b0/o1/r0/b0/o0/v1:i1, results= regions=", "process/r0/b0/o1/r1/b0/o1/r0/b0/o2 arith.cmpi{predicate=0 : i64;}props={predicate = 0 : i64} operands=process/r0/b0/o1/r1/b0/o1/r0/b0/o0/v0:i32,process/r0/b0/o1/r1/b0/o0/v0:i32, results=process/r0/b0/o1/r1/b0/o1/r0/b0/o2/v0:i1, regions=", "process/r0/b0/o1/r1/b0/o1/r0/b0/o3 ac.assert{message=\22in1 receive must match peek\22;}props={message = \22in1 receive must match peek\22} operands=process/r0/b0/o1/r1/b0/o1/r0/b0/o2/v0:i1, results= regions=", "process/r0/b0/o1/r1/b0/o1/r0/b0/o4 arith.constant{value=3 : i32;}props={value = 3 : i32} operands= results=process/r0/b0/o1/r1/b0/o1/r0/b0/o4/v0:i32, regions=", "process/r0/b0/o1/r1/b0/o1/r0/b0/o5 arith.constant{value=0 : i32;}props={value = 0 : i32} operands= results=process/r0/b0/o1/r1/b0/o1/r0/b0/o5/v0:i32, regions=", "process/r0/b0/o1/r1/b0/o1/r0/b0/o6 arith.andi{}props=<<NULL ATTRIBUTE>> operands=process/r0/b0/o1/r1/b0/o1/r0/b0/o0/v0:i32,process/r0/b0/o1/r1/b0/o1/r0/b0/o4/v0:i32, results=process/r0/b0/o1/r1/b0/o1/r0/b0/o6/v0:i32, regions=", "process/r0/b0/o1/r1/b0/o1/r0/b0/o7 arith.cmpi{predicate=0 : i64;}props={predicate = 0 : i64} operands=process/r0/b0/o1/r1/b0/o1/r0/b0/o6/v0:i32,process/r0/b0/o1/r1/b0/o1/r0/b0/o5/v0:i32, results=process/r0/b0/o1/r1/b0/o1/r0/b0/o7/v0:i1, regions=", "process/r0/b0/o1/r1/b0/o1/r0/b0/o8 scf.if{}props=<<NULL ATTRIBUTE>> operands=process/r0/b0/o1/r1/b0/o1/r0/b0/o7/v0:i1, results= regions=[()][()]", "process/r0/b0/o1/r1/b0/o1/r0/b0/o8/r0/b0/o0 ac.try_send{queue=@out0;}props={queue = @out0} operands=process/r0/b0/o1/r1/b0/o1/r0/b0/o0/v0:i32, results=process/r0/b0/o1/r1/b0/o1/r0/b0/o8/r0/b0/o0/v0:i1, regions=", "process/r0/b0/o1/r1/b0/o1/r0/b0/o8/r0/b0/o1 scf.if{}props=<<NULL ATTRIBUTE>> operands=process/r0/b0/o1/r1/b0/o1/r0/b0/o8/r0/b0/o0/v0:i1, results= regions=[()][()]", "process/r0/b0/o1/r1/b0/o1/r0/b0/o8/r0/b0/o1/r0/b0/o0 scf.yield{}props=<<NULL ATTRIBUTE>> operands= results= regions=", "process/r0/b0/o1/r1/b0/o1/r0/b0/o8/r0/b0/o1/r1/b0/o0 ac.await_queue{queue=@out0;until=\22writable\22;}props={queue = @out0, until = \22writable\22} operands= results= regions=", "process/r0/b0/o1/r1/b0/o1/r0/b0/o8/r0/b0/o1/r1/b0/o1 scf.yield{}props=<<NULL ATTRIBUTE>> operands= results= regions=", "process/r0/b0/o1/r1/b0/o1/r0/b0/o8/r0/b0/o2 scf.yield{}props=<<NULL ATTRIBUTE>> operands= results= regions=", "process/r0/b0/o1/r1/b0/o1/r0/b0/o8/r1/b0/o0 ac.try_send{queue=@out1;}props={queue = @out1} operands=process/r0/b0/o1/r1/b0/o1/r0/b0/o0/v0:i32, results=process/r0/b0/o1/r1/b0/o1/r0/b0/o8/r1/b0/o0/v0:i1, regions=", "process/r0/b0/o1/r1/b0/o1/r0/b0/o8/r1/b0/o1 scf.if{}props=<<NULL ATTRIBUTE>> operands=process/r0/b0/o1/r1/b0/o1/r0/b0/o8/r1/b0/o0/v0:i1, results= regions=[()][()]", "process/r0/b0/o1/r1/b0/o1/r0/b0/o8/r1/b0/o1/r0/b0/o0 scf.yield{}props=<<NULL ATTRIBUTE>> operands= results= regions=", "process/r0/b0/o1/r1/b0/o1/r0/b0/o8/r1/b0/o1/r1/b0/o0 ac.await_queue{queue=@out1;until=\22writable\22;}props={queue = @out1, until = \22writable\22} operands= results= regions=", "process/r0/b0/o1/r1/b0/o1/r0/b0/o8/r1/b0/o1/r1/b0/o1 scf.yield{}props=<<NULL ATTRIBUTE>> operands= results= regions=", "process/r0/b0/o1/r1/b0/o1/r0/b0/o8/r1/b0/o2 scf.yield{}props=<<NULL ATTRIBUTE>> operands= results= regions=", "process/r0/b0/o1/r1/b0/o1/r0/b0/o9 scf.yield{}props=<<NULL ATTRIBUTE>> operands= results= regions=", "process/r0/b0/o1/r1/b0/o2 scf.yield{}props=<<NULL ATTRIBUTE>> operands= results= regions=", "process/r0/b0/o2 ac.yield_sim{}props=<<NULL ATTRIBUTE>> operands= results= regions="]}
    ac.process @producer0 kind "workload" {
      %c0_i32 = arith.constant 0 : i32
      %0 = ac.try_send @in0 %c0_i32 : i32
      %c24849_i32 = arith.constant 24849 : i32
      %1 = ac.try_send @in0 %c24849_i32 : i32
      %c49696_i32 = arith.constant 49696 : i32
      %2 = ac.try_send @in0 %c49696_i32 : i32
      %c74545_i32 = arith.constant 74545 : i32
      %3 = ac.try_send @in0 %c74545_i32 : i32
      %c99392_i32 = arith.constant 99392 : i32
      %4 = ac.try_send @in0 %c99392_i32 : i32
      %c124241_i32 = arith.constant 124241 : i32
      %5 = ac.try_send @in0 %c124241_i32 : i32
      %c149088_i32 = arith.constant 149088 : i32
      %6 = ac.try_send @in0 %c149088_i32 : i32
      %c173937_i32 = arith.constant 173937 : i32
      %7 = ac.try_send @in0 %c173937_i32 : i32
      ac.yield_sim
    } {ac.frozen_owners = [{kind = "ac.process", owner = @Top::@producer0, path = "root.producer0", stable_id = "root/producer0"}], ac.frozen_process_skeleton = ["process/r0/b0/o0 arith.constant{value=0 : i32;}props={value = 0 : i32} operands= results=process/r0/b0/o0/v0:i32, regions=", "process/r0/b0/o1 ac.try_send{queue=@in0;}props={queue = @in0} operands=process/r0/b0/o0/v0:i32, results=process/r0/b0/o1/v0:i1, regions=", "process/r0/b0/o2 arith.constant{value=24849 : i32;}props={value = 24849 : i32} operands= results=process/r0/b0/o2/v0:i32, regions=", "process/r0/b0/o3 ac.try_send{queue=@in0;}props={queue = @in0} operands=process/r0/b0/o2/v0:i32, results=process/r0/b0/o3/v0:i1, regions=", "process/r0/b0/o4 arith.constant{value=49696 : i32;}props={value = 49696 : i32} operands= results=process/r0/b0/o4/v0:i32, regions=", "process/r0/b0/o5 ac.try_send{queue=@in0;}props={queue = @in0} operands=process/r0/b0/o4/v0:i32, results=process/r0/b0/o5/v0:i1, regions=", "process/r0/b0/o6 arith.constant{value=74545 : i32;}props={value = 74545 : i32} operands= results=process/r0/b0/o6/v0:i32, regions=", "process/r0/b0/o7 ac.try_send{queue=@in0;}props={queue = @in0} operands=process/r0/b0/o6/v0:i32, results=process/r0/b0/o7/v0:i1, regions=", "process/r0/b0/o8 arith.constant{value=99392 : i32;}props={value = 99392 : i32} operands= results=process/r0/b0/o8/v0:i32, regions=", "process/r0/b0/o9 ac.try_send{queue=@in0;}props={queue = @in0} operands=process/r0/b0/o8/v0:i32, results=process/r0/b0/o9/v0:i1, regions=", "process/r0/b0/o10 arith.constant{value=124241 : i32;}props={value = 124241 : i32} operands= results=process/r0/b0/o10/v0:i32, regions=", "process/r0/b0/o11 ac.try_send{queue=@in0;}props={queue = @in0} operands=process/r0/b0/o10/v0:i32, results=process/r0/b0/o11/v0:i1, regions=", "process/r0/b0/o12 arith.constant{value=149088 : i32;}props={value = 149088 : i32} operands= results=process/r0/b0/o12/v0:i32, regions=", "process/r0/b0/o13 ac.try_send{queue=@in0;}props={queue = @in0} operands=process/r0/b0/o12/v0:i32, results=process/r0/b0/o13/v0:i1, regions=", "process/r0/b0/o14 arith.constant{value=173937 : i32;}props={value = 173937 : i32} operands= results=process/r0/b0/o14/v0:i32, regions=", "process/r0/b0/o15 ac.try_send{queue=@in0;}props={queue = @in0} operands=process/r0/b0/o14/v0:i32, results=process/r0/b0/o15/v0:i1, regions=", "process/r0/b0/o16 ac.yield_sim{}props=<<NULL ATTRIBUTE>> operands= results= regions="]}
    ac.process @producer1 kind "workload" {
      %c261_i32 = arith.constant 261 : i32
      %0 = ac.try_send @in1 %c261_i32 : i32
      %c25108_i32 = arith.constant 25108 : i32
      %1 = ac.try_send @in1 %c25108_i32 : i32
      %c49957_i32 = arith.constant 49957 : i32
      %2 = ac.try_send @in1 %c49957_i32 : i32
      %c74804_i32 = arith.constant 74804 : i32
      %3 = ac.try_send @in1 %c74804_i32 : i32
      %c99653_i32 = arith.constant 99653 : i32
      %4 = ac.try_send @in1 %c99653_i32 : i32
      %c124500_i32 = arith.constant 124500 : i32
      %5 = ac.try_send @in1 %c124500_i32 : i32
      %c149349_i32 = arith.constant 149349 : i32
      %6 = ac.try_send @in1 %c149349_i32 : i32
      %c174196_i32 = arith.constant 174196 : i32
      %7 = ac.try_send @in1 %c174196_i32 : i32
      ac.yield_sim
    } {ac.frozen_owners = [{kind = "ac.process", owner = @Top::@producer1, path = "root.producer1", stable_id = "root/producer1"}], ac.frozen_process_skeleton = ["process/r0/b0/o0 arith.constant{value=261 : i32;}props={value = 261 : i32} operands= results=process/r0/b0/o0/v0:i32, regions=", "process/r0/b0/o1 ac.try_send{queue=@in1;}props={queue = @in1} operands=process/r0/b0/o0/v0:i32, results=process/r0/b0/o1/v0:i1, regions=", "process/r0/b0/o2 arith.constant{value=25108 : i32;}props={value = 25108 : i32} operands= results=process/r0/b0/o2/v0:i32, regions=", "process/r0/b0/o3 ac.try_send{queue=@in1;}props={queue = @in1} operands=process/r0/b0/o2/v0:i32, results=process/r0/b0/o3/v0:i1, regions=", "process/r0/b0/o4 arith.constant{value=49957 : i32;}props={value = 49957 : i32} operands= results=process/r0/b0/o4/v0:i32, regions=", "process/r0/b0/o5 ac.try_send{queue=@in1;}props={queue = @in1} operands=process/r0/b0/o4/v0:i32, results=process/r0/b0/o5/v0:i1, regions=", "process/r0/b0/o6 arith.constant{value=74804 : i32;}props={value = 74804 : i32} operands= results=process/r0/b0/o6/v0:i32, regions=", "process/r0/b0/o7 ac.try_send{queue=@in1;}props={queue = @in1} operands=process/r0/b0/o6/v0:i32, results=process/r0/b0/o7/v0:i1, regions=", "process/r0/b0/o8 arith.constant{value=99653 : i32;}props={value = 99653 : i32} operands= results=process/r0/b0/o8/v0:i32, regions=", "process/r0/b0/o9 ac.try_send{queue=@in1;}props={queue = @in1} operands=process/r0/b0/o8/v0:i32, results=process/r0/b0/o9/v0:i1, regions=", "process/r0/b0/o10 arith.constant{value=124500 : i32;}props={value = 124500 : i32} operands= results=process/r0/b0/o10/v0:i32, regions=", "process/r0/b0/o11 ac.try_send{queue=@in1;}props={queue = @in1} operands=process/r0/b0/o10/v0:i32, results=process/r0/b0/o11/v0:i1, regions=", "process/r0/b0/o12 arith.constant{value=149349 : i32;}props={value = 149349 : i32} operands= results=process/r0/b0/o12/v0:i32, regions=", "process/r0/b0/o13 ac.try_send{queue=@in1;}props={queue = @in1} operands=process/r0/b0/o12/v0:i32, results=process/r0/b0/o13/v0:i1, regions=", "process/r0/b0/o14 arith.constant{value=174196 : i32;}props={value = 174196 : i32} operands= results=process/r0/b0/o14/v0:i32, regions=", "process/r0/b0/o15 ac.try_send{queue=@in1;}props={queue = @in1} operands=process/r0/b0/o14/v0:i32, results=process/r0/b0/o15/v0:i1, regions=", "process/r0/b0/o16 ac.yield_sim{}props=<<NULL ATTRIBUTE>> operands= results= regions="]}
    ac.process @sink0 kind "control" {
      %value, %received = ac.try_recv @out0 : i32
      scf.if %received {
        %c0_i32 = arith.constant 0 : i32
        %c2_i32 = arith.constant 2 : i32
        %c3_i32 = arith.constant 3 : i32
        %c4_i32 = arith.constant 4 : i32
        %c8_i32 = arith.constant 8 : i32
        %c15_i32 = arith.constant 15 : i32
        %c97_i32 = arith.constant 97 : i32
        %0 = arith.andi %value, %c3_i32 : i32
        %1 = arith.cmpi eq, %0, %c0_i32 : i32
        ac.assert %1, "out0 flit destination must be 0"
        %2 = arith.shrui %value, %c2_i32 : i32
        %3 = arith.andi %2, %c3_i32 : i32
        %4 = arith.shrui %value, %c4_i32 : i32
        %5 = arith.andi %4, %c15_i32 : i32
        %6 = arith.shrui %value, %c8_i32 : i32
        %7 = arith.muli %5, %c97_i32 : i32
        %8 = arith.addi %7, %3 : i32
        %9 = arith.cmpi eq, %6, %8 : i32
        ac.assert %9, "out0 flit payload must equal seq*97 + src"
      } else {
        ac.await_queue @out0 until "readable"
      }
      ac.yield_sim
    } {ac.frozen_owners = [{kind = "ac.process", owner = @Top::@sink0, path = "root.sink0", stable_id = "root/sink0"}], ac.frozen_process_skeleton = ["process/r0/b0/o0 ac.try_recv{queue=@out0;}props={queue = @out0} operands= results=process/r0/b0/o0/v0:i32,process/r0/b0/o0/v1:i1, regions=", "process/r0/b0/o1 scf.if{}props=<<NULL ATTRIBUTE>> operands=process/r0/b0/o0/v1:i1, results= regions=[()][()]", "process/r0/b0/o1/r0/b0/o0 arith.constant{value=0 : i32;}props={value = 0 : i32} operands= results=process/r0/b0/o1/r0/b0/o0/v0:i32, regions=", "process/r0/b0/o1/r0/b0/o1 arith.constant{value=2 : i32;}props={value = 2 : i32} operands= results=process/r0/b0/o1/r0/b0/o1/v0:i32, regions=", "process/r0/b0/o1/r0/b0/o2 arith.constant{value=3 : i32;}props={value = 3 : i32} operands= results=process/r0/b0/o1/r0/b0/o2/v0:i32, regions=", "process/r0/b0/o1/r0/b0/o3 arith.constant{value=4 : i32;}props={value = 4 : i32} operands= results=process/r0/b0/o1/r0/b0/o3/v0:i32, regions=", "process/r0/b0/o1/r0/b0/o4 arith.constant{value=8 : i32;}props={value = 8 : i32} operands= results=process/r0/b0/o1/r0/b0/o4/v0:i32, regions=", "process/r0/b0/o1/r0/b0/o5 arith.constant{value=15 : i32;}props={value = 15 : i32} operands= results=process/r0/b0/o1/r0/b0/o5/v0:i32, regions=", "process/r0/b0/o1/r0/b0/o6 arith.constant{value=97 : i32;}props={value = 97 : i32} operands= results=process/r0/b0/o1/r0/b0/o6/v0:i32, regions=", "process/r0/b0/o1/r0/b0/o7 arith.andi{}props=<<NULL ATTRIBUTE>> operands=process/r0/b0/o0/v0:i32,process/r0/b0/o1/r0/b0/o2/v0:i32, results=process/r0/b0/o1/r0/b0/o7/v0:i32, regions=", "process/r0/b0/o1/r0/b0/o8 arith.cmpi{predicate=0 : i64;}props={predicate = 0 : i64} operands=process/r0/b0/o1/r0/b0/o7/v0:i32,process/r0/b0/o1/r0/b0/o0/v0:i32, results=process/r0/b0/o1/r0/b0/o8/v0:i1, regions=", "process/r0/b0/o1/r0/b0/o9 ac.assert{message=\22out0 flit destination must be 0\22;}props={message = \22out0 flit destination must be 0\22} operands=process/r0/b0/o1/r0/b0/o8/v0:i1, results= regions=", "process/r0/b0/o1/r0/b0/o10 arith.shrui{}props=<<NULL ATTRIBUTE>> operands=process/r0/b0/o0/v0:i32,process/r0/b0/o1/r0/b0/o1/v0:i32, results=process/r0/b0/o1/r0/b0/o10/v0:i32, regions=", "process/r0/b0/o1/r0/b0/o11 arith.andi{}props=<<NULL ATTRIBUTE>> operands=process/r0/b0/o1/r0/b0/o10/v0:i32,process/r0/b0/o1/r0/b0/o2/v0:i32, results=process/r0/b0/o1/r0/b0/o11/v0:i32, regions=", "process/r0/b0/o1/r0/b0/o12 arith.shrui{}props=<<NULL ATTRIBUTE>> operands=process/r0/b0/o0/v0:i32,process/r0/b0/o1/r0/b0/o3/v0:i32, results=process/r0/b0/o1/r0/b0/o12/v0:i32, regions=", "process/r0/b0/o1/r0/b0/o13 arith.andi{}props=<<NULL ATTRIBUTE>> operands=process/r0/b0/o1/r0/b0/o12/v0:i32,process/r0/b0/o1/r0/b0/o5/v0:i32, results=process/r0/b0/o1/r0/b0/o13/v0:i32, regions=", "process/r0/b0/o1/r0/b0/o14 arith.shrui{}props=<<NULL ATTRIBUTE>> operands=process/r0/b0/o0/v0:i32,process/r0/b0/o1/r0/b0/o4/v0:i32, results=process/r0/b0/o1/r0/b0/o14/v0:i32, regions=", "process/r0/b0/o1/r0/b0/o15 arith.muli{overflowFlags=#arith.overflow<none>;}props={overflowFlags = #arith.overflow<none>} operands=process/r0/b0/o1/r0/b0/o13/v0:i32,process/r0/b0/o1/r0/b0/o6/v0:i32, results=process/r0/b0/o1/r0/b0/o15/v0:i32, regions=", "process/r0/b0/o1/r0/b0/o16 arith.addi{overflowFlags=#arith.overflow<none>;}props={overflowFlags = #arith.overflow<none>} operands=process/r0/b0/o1/r0/b0/o15/v0:i32,process/r0/b0/o1/r0/b0/o11/v0:i32, results=process/r0/b0/o1/r0/b0/o16/v0:i32, regions=", "process/r0/b0/o1/r0/b0/o17 arith.cmpi{predicate=0 : i64;}props={predicate = 0 : i64} operands=process/r0/b0/o1/r0/b0/o14/v0:i32,process/r0/b0/o1/r0/b0/o16/v0:i32, results=process/r0/b0/o1/r0/b0/o17/v0:i1, regions=", "process/r0/b0/o1/r0/b0/o18 ac.assert{message=\22out0 flit payload must equal seq*97 + src\22;}props={message = \22out0 flit payload must equal seq*97 + src\22} operands=process/r0/b0/o1/r0/b0/o17/v0:i1, results= regions=", "process/r0/b0/o1/r0/b0/o19 scf.yield{}props=<<NULL ATTRIBUTE>> operands= results= regions=", "process/r0/b0/o1/r1/b0/o0 ac.await_queue{queue=@out0;until=\22readable\22;}props={queue = @out0, until = \22readable\22} operands= results= regions=", "process/r0/b0/o1/r1/b0/o1 scf.yield{}props=<<NULL ATTRIBUTE>> operands= results= regions=", "process/r0/b0/o2 ac.yield_sim{}props=<<NULL ATTRIBUTE>> operands= results= regions="]}
    ac.process @sink1 kind "control" {
      %value, %received = ac.try_recv @out1 : i32
      scf.if %received {
        %c1_i32 = arith.constant 1 : i32
        %c2_i32 = arith.constant 2 : i32
        %c3_i32 = arith.constant 3 : i32
        %c4_i32 = arith.constant 4 : i32
        %c8_i32 = arith.constant 8 : i32
        %c15_i32 = arith.constant 15 : i32
        %c97_i32 = arith.constant 97 : i32
        %0 = arith.andi %value, %c3_i32 : i32
        %1 = arith.cmpi eq, %0, %c1_i32 : i32
        ac.assert %1, "out1 flit destination must be 1"
        %2 = arith.shrui %value, %c2_i32 : i32
        %3 = arith.andi %2, %c3_i32 : i32
        %4 = arith.shrui %value, %c4_i32 : i32
        %5 = arith.andi %4, %c15_i32 : i32
        %6 = arith.shrui %value, %c8_i32 : i32
        %7 = arith.muli %5, %c97_i32 : i32
        %8 = arith.addi %7, %3 : i32
        %9 = arith.cmpi eq, %6, %8 : i32
        ac.assert %9, "out1 flit payload must equal seq*97 + src"
      } else {
        ac.await_queue @out1 until "readable"
      }
      ac.yield_sim
    } {ac.frozen_owners = [{kind = "ac.process", owner = @Top::@sink1, path = "root.sink1", stable_id = "root/sink1"}], ac.frozen_process_skeleton = ["process/r0/b0/o0 ac.try_recv{queue=@out1;}props={queue = @out1} operands= results=process/r0/b0/o0/v0:i32,process/r0/b0/o0/v1:i1, regions=", "process/r0/b0/o1 scf.if{}props=<<NULL ATTRIBUTE>> operands=process/r0/b0/o0/v1:i1, results= regions=[()][()]", "process/r0/b0/o1/r0/b0/o0 arith.constant{value=1 : i32;}props={value = 1 : i32} operands= results=process/r0/b0/o1/r0/b0/o0/v0:i32, regions=", "process/r0/b0/o1/r0/b0/o1 arith.constant{value=2 : i32;}props={value = 2 : i32} operands= results=process/r0/b0/o1/r0/b0/o1/v0:i32, regions=", "process/r0/b0/o1/r0/b0/o2 arith.constant{value=3 : i32;}props={value = 3 : i32} operands= results=process/r0/b0/o1/r0/b0/o2/v0:i32, regions=", "process/r0/b0/o1/r0/b0/o3 arith.constant{value=4 : i32;}props={value = 4 : i32} operands= results=process/r0/b0/o1/r0/b0/o3/v0:i32, regions=", "process/r0/b0/o1/r0/b0/o4 arith.constant{value=8 : i32;}props={value = 8 : i32} operands= results=process/r0/b0/o1/r0/b0/o4/v0:i32, regions=", "process/r0/b0/o1/r0/b0/o5 arith.constant{value=15 : i32;}props={value = 15 : i32} operands= results=process/r0/b0/o1/r0/b0/o5/v0:i32, regions=", "process/r0/b0/o1/r0/b0/o6 arith.constant{value=97 : i32;}props={value = 97 : i32} operands= results=process/r0/b0/o1/r0/b0/o6/v0:i32, regions=", "process/r0/b0/o1/r0/b0/o7 arith.andi{}props=<<NULL ATTRIBUTE>> operands=process/r0/b0/o0/v0:i32,process/r0/b0/o1/r0/b0/o2/v0:i32, results=process/r0/b0/o1/r0/b0/o7/v0:i32, regions=", "process/r0/b0/o1/r0/b0/o8 arith.cmpi{predicate=0 : i64;}props={predicate = 0 : i64} operands=process/r0/b0/o1/r0/b0/o7/v0:i32,process/r0/b0/o1/r0/b0/o0/v0:i32, results=process/r0/b0/o1/r0/b0/o8/v0:i1, regions=", "process/r0/b0/o1/r0/b0/o9 ac.assert{message=\22out1 flit destination must be 1\22;}props={message = \22out1 flit destination must be 1\22} operands=process/r0/b0/o1/r0/b0/o8/v0:i1, results= regions=", "process/r0/b0/o1/r0/b0/o10 arith.shrui{}props=<<NULL ATTRIBUTE>> operands=process/r0/b0/o0/v0:i32,process/r0/b0/o1/r0/b0/o1/v0:i32, results=process/r0/b0/o1/r0/b0/o10/v0:i32, regions=", "process/r0/b0/o1/r0/b0/o11 arith.andi{}props=<<NULL ATTRIBUTE>> operands=process/r0/b0/o1/r0/b0/o10/v0:i32,process/r0/b0/o1/r0/b0/o2/v0:i32, results=process/r0/b0/o1/r0/b0/o11/v0:i32, regions=", "process/r0/b0/o1/r0/b0/o12 arith.shrui{}props=<<NULL ATTRIBUTE>> operands=process/r0/b0/o0/v0:i32,process/r0/b0/o1/r0/b0/o3/v0:i32, results=process/r0/b0/o1/r0/b0/o12/v0:i32, regions=", "process/r0/b0/o1/r0/b0/o13 arith.andi{}props=<<NULL ATTRIBUTE>> operands=process/r0/b0/o1/r0/b0/o12/v0:i32,process/r0/b0/o1/r0/b0/o5/v0:i32, results=process/r0/b0/o1/r0/b0/o13/v0:i32, regions=", "process/r0/b0/o1/r0/b0/o14 arith.shrui{}props=<<NULL ATTRIBUTE>> operands=process/r0/b0/o0/v0:i32,process/r0/b0/o1/r0/b0/o4/v0:i32, results=process/r0/b0/o1/r0/b0/o14/v0:i32, regions=", "process/r0/b0/o1/r0/b0/o15 arith.muli{overflowFlags=#arith.overflow<none>;}props={overflowFlags = #arith.overflow<none>} operands=process/r0/b0/o1/r0/b0/o13/v0:i32,process/r0/b0/o1/r0/b0/o6/v0:i32, results=process/r0/b0/o1/r0/b0/o15/v0:i32, regions=", "process/r0/b0/o1/r0/b0/o16 arith.addi{overflowFlags=#arith.overflow<none>;}props={overflowFlags = #arith.overflow<none>} operands=process/r0/b0/o1/r0/b0/o15/v0:i32,process/r0/b0/o1/r0/b0/o11/v0:i32, results=process/r0/b0/o1/r0/b0/o16/v0:i32, regions=", "process/r0/b0/o1/r0/b0/o17 arith.cmpi{predicate=0 : i64;}props={predicate = 0 : i64} operands=process/r0/b0/o1/r0/b0/o14/v0:i32,process/r0/b0/o1/r0/b0/o16/v0:i32, results=process/r0/b0/o1/r0/b0/o17/v0:i1, regions=", "process/r0/b0/o1/r0/b0/o18 ac.assert{message=\22out1 flit payload must equal seq*97 + src\22;}props={message = \22out1 flit payload must equal seq*97 + src\22} operands=process/r0/b0/o1/r0/b0/o17/v0:i1, results= regions=", "process/r0/b0/o1/r0/b0/o19 scf.yield{}props=<<NULL ATTRIBUTE>> operands= results= regions=", "process/r0/b0/o1/r1/b0/o0 ac.await_queue{queue=@out1;until=\22readable\22;}props={queue = @out1, until = \22readable\22} operands= results= regions=", "process/r0/b0/o1/r1/b0/o1 scf.yield{}props=<<NULL ATTRIBUTE>> operands= results= regions=", "process/r0/b0/o2 ac.yield_sim{}props=<<NULL ATTRIBUTE>> operands= results= regions="]}
    ac.return
  }
}
