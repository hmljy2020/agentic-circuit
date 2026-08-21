// RUN: %acir_opt --verify-each=false --pass-pipeline='builtin.module(ac-freeze-topology)' %s -o %t.frozen
// RUN: %acir_opt --ac-lower-to-acsim --ac-binding-profile=fast --ac-binding-target=arm64-apple-darwin %t.frozen | %FileCheck %s

builtin.module attributes {ac.contract_epoch = "0.2"} {
  "ac.type_scope"() <{sym_name = "types"}> ({
    "ac.packet"() <{sym_name = "Request", fields = [
      {name = "opcode", type = i8}, {name = "payload", type = i32}
    ]}> : () -> ()
  }) {dlti.dl_spec = #dlti.dl_spec<
    !ac.packet<@types::@Request> = {
      abi_alignment = 4 : i64, endianness = "little",
      preferred_alignment = 4 : i64, serialization_width = 8 : i64,
      size = 8 : i64
    }
  >} : () -> ()
  ac.protocol @ready_valid {
    ac.role @sender dual @receiver cardinality "exclusive"
    ac.role @receiver dual @sender cardinality "exclusive"
    ac.state @idle initial true terminal false
    ac.state @done initial false terminal true
    ac.event @push from @sender to @receiver payload !ac.packet<@types::@Request>
        action "offer"
    ac.transition from @idle to @done on @push transfer true retain false guard {}
  }
  ac.system @soc root @Top as "root" tick 0 "cycle"
      workload @Top::@worker seed {kind = "fixed", value = 7 : i64}
      instrumentation [] results {id = "default", format = "json"} selected true
  ac.module @Top() parameters {} graph {
    ac.queue @packets payload !ac.packet<@types::@Request> entries 2 bytes 16
        ordering "fifo" protocol @ready_valid ownership "exclusive"
        id "packets" path "packets" {ac.host_input = "packet",
                                      ac.host_output = "packet"}
    ac.process @worker kind "workload" {
      %seed_opcode = arith.constant 1 : i8
      %seed_payload = arith.constant 7 : i32
      %created = "ac.record.create"(%seed_opcode, %seed_payload)
          <{field_names = ["opcode", "payload"]}> :
          (i8, i32) -> !ac.packet<@types::@Request>
      %created_opcode = "ac.record.get"(%created) <{field = "opcode"}> :
          (!ac.packet<@types::@Request>) -> i8
      %value, %valid = ac.peek @packets : !ac.packet<@types::@Request>
      %opcode = "ac.record.get"(%value) <{field = "opcode"}> :
          (!ac.packet<@types::@Request>) -> i8
      %next_opcode = arith.addi %opcode, %created_opcode : i8
      %updated = "ac.record.with"(%value, %next_opcode) <{field = "opcode"}> :
          (!ac.packet<@types::@Request>, i8) -> !ac.packet<@types::@Request>
      %bytes = "ac.packet.serialize"(%updated) <{packet = @types::@Request}> :
          (!ac.packet<@types::@Request>) -> !ac.vector<8 x i8>
      %copy = "ac.packet.deserialize"(%bytes) <{packet = @types::@Request}> :
          (!ac.vector<8 x i8>) -> !ac.packet<@types::@Request>
      %accepted = ac.try_send @packets %copy : !ac.packet<@types::@Request>
      scf.if %valid {
      } else {
        ac.await_queue @packets until "readable"
      }
      ac.yield_sim
    }
    ac.return
  }
}

// CHECK: acsim.type @acir_packet_{{[0-9a-f]+}} cpp "gfsim::AtomicPacket<8, {{.+}}>" kind "packet"
// CHECK: acsim.type @acir_queue_{{[0-9a-f]+}} cpp "gfsim::Queue<gfsim::AtomicPacket<8, {{.+}}>>" kind "runtime_object"
// CHECK-NOT: acsim.binding
// CHECK: acsim.instance @packets target @acir_queue_{{[0-9a-f]+}} args [2, 16]
// CHECK: acsim.process @worker captures(%{{.+}} : !acsim.owner<@acir_queue_{{[0-9a-f]+}}>) names ["queue_packets"]
// CHECK: acsim.inline @acir_impl_record_create_{{[0-9a-f]+}}
// CHECK: acsim.inline @acir_impl_record_get_{{[0-9a-f]+}}
// CHECK: acsim.invoke @acir_impl_queue_peek_{{[0-9a-f]+}}(%{{.+}}) : (!acsim.owner<@acir_queue_{{[0-9a-f]+}}>) -> (!acsim.value<@acir_packet_{{[0-9a-f]+}}>, i1)
// CHECK: acsim.inline @acir_impl_record_get_{{[0-9a-f]+}}
// CHECK: acsim.inline @acir_impl_record_with_{{[0-9a-f]+}}
// CHECK: acsim.inline @acir_impl_packet_serialize_{{[0-9a-f]+}}
// CHECK: acsim.inline @acir_impl_packet_deserialize_{{[0-9a-f]+}}
// CHECK: acsim.invoke @acir_impl_queue_try_send_{{[0-9a-f]+}}
