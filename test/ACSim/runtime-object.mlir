// RUN: %acir_opt_public %s | %FileCheck %s

builtin.module attributes {ac.contract_epoch = "0.2"} {
  acsim.model @runtime_objects epoch "0.2" root @Top
      construction ["Top.queues[0]", "Top.queues[1]"]
      destruction ["Top.queues[1]", "Top.queues[0]"] fingerprints {
        frozen_acir = "sha256:0000000000000000000000000000000000000000000000000000000000000000",
        binding_lock = "sha256:0000000000000000000000000000000000000000000000000000000000000000",
        provider = "sha256:0000000000000000000000000000000000000000000000000000000000000000",
        profile = "sha256:0000000000000000000000000000000000000000000000000000000000000000",
        toolchain = "sha256:0000000000000000000000000000000000000000000000000000000000000000",
        schema_set = "sha256:0000000000000000000000000000000000000000000000000000000000000000"
      } {
    acsim.type @queue_i32 cpp "gfsim::Queue<std::int32_t>"
        kind "runtime_object"
        fingerprint "sha256:1000000000000000000000000000000000000000000000000000000000000000"
    acsim.module @Top interface {ports = [], resources = [], results = []}
        static [] specialization "sha256:2000000000000000000000000000000000000000000000000000000000000000"
        exports [] {
      %queues = acsim.array @queues target @queue_i32 args [1, 4]
          specialization "sha256:3000000000000000000000000000000000000000000000000000000000000000"
          shape [2] : !acsim.array<[2], !acsim.owner<@queue_i32>>
      %queue0 = acsim.element %queues indices [0]
          : !acsim.array<[2], !acsim.owner<@queue_i32>> -> !acsim.ref<@queue_i32>
      %queue1 = acsim.element %queues indices [1]
          : !acsim.array<[2], !acsim.owner<@queue_i32>> -> !acsim.ref<@queue_i32>
      acsim.return
    }
    %object0, %activation0 = acsim.dispatch @Top::@queues path "Top.queues[0]"
        indices [0] object 0 activation 0 work "gfsim::QueueRuntime::work"
        xfer "gfsim::QueueRuntime::xfer" reset "gfsim::QueueRuntime::reset"
        validate "gfsim::QueueRuntime::validate"
        : !acsim.object_id, !acsim.activation_id
    %object1, %activation1 = acsim.dispatch @Top::@queues path "Top.queues[1]"
        indices [1] object 1 activation 1 work "gfsim::QueueRuntime::work"
        xfer "gfsim::QueueRuntime::xfer" reset "gfsim::QueueRuntime::reset"
        validate "gfsim::QueueRuntime::validate"
        : !acsim.object_id, !acsim.activation_id
    acsim.activate %activation0 to %object0
        : !acsim.activation_id to !acsim.object_id
    acsim.activate %activation1 to %object1
        : !acsim.activation_id to !acsim.object_id
  }
}

// CHECK: acsim.type @queue_i32 cpp "gfsim::Queue<std::int32_t>" kind "runtime_object"
// CHECK: acsim.array @queues target @queue_i32 args [1, 4]
// CHECK: !acsim.array<[2], !acsim.owner<@queue_i32>>
// CHECK: !acsim.ref<@queue_i32>
// CHECK: acsim.dispatch @Top::@queues path "Top.queues[0]"
// CHECK: acsim.dispatch @Top::@queues path "Top.queues[1]"
