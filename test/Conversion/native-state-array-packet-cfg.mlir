// RUN: %acir_opt --verify-each=false --pass-pipeline='builtin.module(ac-freeze-topology)' %s -o %t.frozen
// RUN: %acir_opt --ac-lower-to-acsim --ac-binding-profile=fast --ac-binding-target=x86_64-linux-gnu %t.frozen | %FileCheck %s

builtin.module attributes {ac.contract_epoch = "0.2"} {
  "ac.type_scope"() <{sym_name = "types"}> ({
    "ac.packet"() <{sym_name = "State", fields = [
      {name = "value", type = i32}
    ]}> : () -> ()
  }) {dlti.dl_spec = #dlti.dl_spec<
    !ac.packet<@types::@State> = {abi_alignment = 4 : i64,
      endianness = "little", preferred_alignment = 4 : i64,
      serialization_width = 4 : i64, size = 4 : i64}
  >} : () -> ()
  ac.system @native_state_array_packet_cfg root @Top as "root" tick 0 "cycle"
      workload @Top::@worker seed {kind = "fixed", value = 7 : i64}
      instrumentation [] results {id = "default", format = "json"} selected true
  ac.module @Top() parameters {} graph {
    ac.state_array @state element !ac.packet<@types::@State> entries 1
        read_ports 1 write_ports 1 ownership "exclusive" init "zero"
        id "state" path "state"
    ac.process @worker kind "workload" {
      %index = arith.constant 0 : i32
      %record = ac.state_read @state[%index] port %index
          : !ac.packet<@types::@State>
      %condition = arith.constant true
      scf.if %condition {
        ac.assert %condition, "exercise packet live range across CFG"
      }
      %one = arith.constant 1 : i32
      %next = "ac.record.with"(%record, %one) <{field = "value"}>
          : (!ac.packet<@types::@State>, i32) -> !ac.packet<@types::@State>
      ac.state_write @state[%index] %next when %condition port %index
          : !ac.packet<@types::@State>
      ac.yield_sim
    }
    ac.return
  }
}

// CHECK: acsim.process @worker
// CHECK: ^bb{{[0-9]+}}(%{{.*}}: !acsim.value<@acir_packet_{{[0-9a-f]+}}>
// CHECK: acsim.inline @acir_impl_record_with_{{[0-9a-f]+}}
// CHECK-NOT: !ac.packet<@types::@State>
