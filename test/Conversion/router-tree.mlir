// RUN: %acir_opt_public --verify-each=false --pass-pipeline='builtin.module(ac-verify-model,ac-canonicalize-model,ac-freeze-topology)' %source_root/examples/chao/router_tree/model.mlir -o %t.frozen
// RUN: %acir_opt_public --ac-lower-to-acsim --ac-binding-profile=fast --ac-binding-target=x86_64-linux-gnu %t.frozen | %FileCheck %s

// The seven homogeneous native queues share one closed runtime type.
// CHECK: acsim.type @acir_impl_queue_peek_{{[0-9a-f]+}}
// CHECK: acsim.type @acir_impl_queue_try_recv_{{[0-9a-f]+}}
// CHECK: acsim.type @acir_impl_queue_try_send_{{[0-9a-f]+}}
// CHECK: acsim.type @acir_impl_wake_queue_readable_{{[0-9a-f]+}}
// CHECK: acsim.type @acir_impl_wake_queue_writable_{{[0-9a-f]+}}
// CHECK: acsim.type @acir_queue_{{[0-9a-f]+}} cpp "gfsim::Queue<std::int32_t>" kind "runtime_object"
// CHECK-NOT: acsim.binding
// CHECK-COUNT-7: acsim.instance @{{(ingress|leaf[0-3]|trunk_left|trunk_right)}} target @acir_queue_

// Every process captures only the queues it references. Each router retains
// one flit across either blocked output and has two writable retry PCs.
// CHECK: acsim.process @left_router captures({{.*}}) names ["queue_leaf0", "queue_leaf1", "queue_trunk_left"] entry @entry pcs [@entry, @pc00000001, @pc00000002] live [{name = "live00000000", type = !acsim.value<@acir_value_{{[0-9a-f]+}}>}
// CHECK: acsim.invoke @acir_impl_queue_peek_
// CHECK: acsim.process @producer captures({{.*}}) names ["queue_ingress"]
// CHECK: acsim.process @right_router captures({{.*}}) names ["queue_leaf2", "queue_leaf3", "queue_trunk_right"] entry @entry pcs [@entry, @pc00000001, @pc00000002] live [{name = "live00000000", type = !acsim.value<@acir_value_{{[0-9a-f]+}}>}
// CHECK: acsim.invoke @acir_impl_queue_peek_
// CHECK: acsim.process @root_router captures({{.*}}) names ["queue_ingress", "queue_trunk_left", "queue_trunk_right"] entry @entry pcs [@entry, @pc00000001, @pc00000002] live [{name = "live00000000", type = !acsim.value<@acir_value_{{[0-9a-f]+}}>}
// CHECK: acsim.invoke @acir_impl_queue_peek_
// CHECK: acsim.process @sink0 captures({{.*}}) names ["queue_leaf0"]
// CHECK: acsim.process @sink1 captures({{.*}}) names ["queue_leaf1"]
// CHECK: acsim.process @sink2 captures({{.*}}) names ["queue_leaf2"]
// CHECK: acsim.process @sink3 captures({{.*}}) names ["queue_leaf3"]

// Dispatch and activation cover all 15 runtime objects. In addition to the 15
// self edges, the 14 queue-to-user edges wake producers, routers, and sinks.
// CHECK-COUNT-15: acsim.dispatch @Top::@
// CHECK-COUNT-29: acsim.activate
// CHECK-NOT: acsim.binding
