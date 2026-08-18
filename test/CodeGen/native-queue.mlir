// RUN: %acir_cxxgen %s --stop-after=model-plan | %FileCheck %s --check-prefix=PLAN
// PLAN: stage=model-plan status=passed

builtin.module attributes {ac.contract_epoch = "0.2"} {
  acsim.model @queue_model epoch "0.2" root @Top
      construction ["Top.queue", "Top.worker"]
      destruction ["Top.worker", "Top.queue"] fingerprints {
        frozen_acir = "sha256:0000000000000000000000000000000000000000000000000000000000000000",
        binding_lock = "sha256:0000000000000000000000000000000000000000000000000000000000000000",
        provider = "sha256:0000000000000000000000000000000000000000000000000000000000000000",
        profile = "sha256:0000000000000000000000000000000000000000000000000000000000000000",
        toolchain = "sha256:0000000000000000000000000000000000000000000000000000000000000000",
        schema_set = "sha256:0000000000000000000000000000000000000000000000000000000000000000"
      } {
    acsim.type @acir_impl_queue_try_recv_test cpp "acir::generated::queue_recv"
        kind "implementation"
        fingerprint "sha256:3000000000000000000000000000000000000000000000000000000000000000"
    acsim.type @acir_impl_queue_try_send_test cpp "acir::generated::queue_send"
        kind "implementation"
        fingerprint "sha256:2000000000000000000000000000000000000000000000000000000000000000"
    acsim.type @acir_impl_wake_queue_readable_test cpp "acir::generated::queue_readable_wake"
        kind "implementation"
        fingerprint "sha256:5000000000000000000000000000000000000000000000000000000000000000"
    acsim.type @queue_i32 cpp "gfsim::Queue<std::int32_t>" kind "runtime_object"
        fingerprint "sha256:1000000000000000000000000000000000000000000000000000000000000000"
    acsim.type @queue_readable cpp "acir::generated::queue_readable" kind "wake"
        fingerprint "sha256:4000000000000000000000000000000000000000000000000000000000000000"
    acsim.module @Top interface {ports = [], resources = [], results = []}
        static [] specialization "sha256:6000000000000000000000000000000000000000000000000000000000000000"
        exports [] {
      %queue = acsim.instance @queue target @queue_i32 args [1, 4]
          specialization "sha256:7000000000000000000000000000000000000000000000000000000000000000"
          : !acsim.owner<@queue_i32>
      acsim.process @worker captures(%queue : !acsim.owner<@queue_i32>)
          names ["queue"] entry @entry pcs [@entry, @wait] live [] fairness 5
          specialization "sha256:8000000000000000000000000000000000000000000000000000000000000000" {
state @entry {
        ^bb0(%arg0: !acsim.owner<@queue_i32>):
          %value = arith.constant 10 : i32
          %accepted = acsim.invoke @acir_impl_queue_try_send_test(%arg0, %value)
              : (!acsim.owner<@queue_i32>, i32) -> i1
          %received_value, %received = acsim.invoke @acir_impl_queue_try_recv_test(%arg0)
              : (!acsim.owner<@queue_i32>) -> (i32, i1)
          acsim.terminate "success"
        }
state @wait {
        ^bb0(%arg0: !acsim.owner<@queue_i32>):
          %wake = acsim.invoke @acir_impl_wake_queue_readable_test(%arg0)
              : (!acsim.owner<@queue_i32>) -> !acsim.wake<@queue_readable>
          acsim.suspend @wait on %wake : !acsim.wake<@queue_readable>
        }
      }
      acsim.return
    }
    %queue_object, %queue_activation = acsim.dispatch @Top::@queue path "Top.queue"
        indices [] object 0 activation 0 work "gfsim::QueueRuntime::work"
        xfer "gfsim::QueueRuntime::xfer" reset "gfsim::QueueRuntime::reset"
        validate "gfsim::QueueRuntime::validate"
        : !acsim.object_id, !acsim.activation_id
    %worker_object, %worker_activation = acsim.dispatch @Top::@worker path "Top.worker"
        indices [] object 1 activation 1
        work "acsim_generated::Top::s6000000000000000000000000000000000000000000000000000000000000000::worker::p8000000000000000000000000000000000000000000000000000000000000000::work"
        xfer "acsim_generated::Top::s6000000000000000000000000000000000000000000000000000000000000000::worker::p8000000000000000000000000000000000000000000000000000000000000000::xfer"
        reset "acsim_generated::Top::s6000000000000000000000000000000000000000000000000000000000000000::worker::p8000000000000000000000000000000000000000000000000000000000000000::reset"
        validate "acsim_generated::Top::s6000000000000000000000000000000000000000000000000000000000000000::worker::p8000000000000000000000000000000000000000000000000000000000000000::validate"
        : !acsim.object_id, !acsim.activation_id
    acsim.activate %queue_activation to %queue_object
        : !acsim.activation_id to !acsim.object_id
    acsim.activate %queue_activation to %worker_object
        : !acsim.activation_id to !acsim.object_id
    acsim.activate %worker_activation to %worker_object
        : !acsim.activation_id to !acsim.object_id
  }
}
