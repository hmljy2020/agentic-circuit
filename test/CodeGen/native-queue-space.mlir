// RUN: rm -rf %t.out %t.frozen %t.acsim
// RUN: %acir_cxxgen %s --stop-after=model-plan | %FileCheck %s --check-prefix=PLAN
// RUN: %acir_opt --verify-each=false --pass-pipeline='builtin.module(ac-freeze-topology)' %source_root/test/Conversion/native-queue.mlir -o %t.frozen
// RUN: %acir_opt --ac-lower-to-acsim --ac-binding-profile=fast --ac-binding-target=x86_64-linux-gnu %t.frozen -o %t.acsim
// RUN: %acir_cxxgen %t.acsim --stop-after=compile --output-root=%t.out --project-name=queue-space --project-identity=project.queue-space --system-name=soc --system-identity=system.soc --profile=fast --compiler=%cxx --standard-library=libstdc++ --abi-mode=default --object-format=elf --contract-flag=-std=c++20 --include-root=%source_root/include
// RUN: grep -R "\.space()" %t.out/src/generated/processes
// PLAN: stage=model-plan status=passed

builtin.module attributes {ac.contract_epoch = "0.2"} {
  acsim.model @queue_space_model epoch "0.2" root @Top
      construction ["Top.queue", "Top.worker"]
      destruction ["Top.worker", "Top.queue"] fingerprints {
        frozen_acir = "sha256:0000000000000000000000000000000000000000000000000000000000000000",
        binding_lock = "sha256:0000000000000000000000000000000000000000000000000000000000000000",
        provider = "sha256:0000000000000000000000000000000000000000000000000000000000000000",
        profile = "sha256:0000000000000000000000000000000000000000000000000000000000000000",
        toolchain = "sha256:0000000000000000000000000000000000000000000000000000000000000000",
        schema_set = "sha256:0000000000000000000000000000000000000000000000000000000000000000"
      } {
    acsim.type @acir_impl_queue_space_test cpp "acir::generated::queue_space"
        kind "implementation"
        fingerprint "sha256:9000000000000000000000000000000000000000000000000000000000000000"
    acsim.type @queue_i32 cpp "gfsim::Queue<std::int32_t>" kind "runtime_object"
        fingerprint "sha256:1000000000000000000000000000000000000000000000000000000000000000"
    acsim.module @Top interface {ports = [], resources = [], results = []}
        static [] specialization "sha256:6000000000000000000000000000000000000000000000000000000000000000"
        exports [] {
      %queue = acsim.instance @queue target @queue_i32 args [1, 4]
          specialization "sha256:7000000000000000000000000000000000000000000000000000000000000000"
          : !acsim.owner<@queue_i32>
      acsim.process @worker captures(%queue : !acsim.owner<@queue_i32>)
          names ["queue"] entry @entry pcs [@entry] live [] fairness 5
          specialization "sha256:8000000000000000000000000000000000000000000000000000000000000000" {
state @entry {
        ^bb0(%arg0: !acsim.owner<@queue_i32>):
          %space = acsim.invoke @acir_impl_queue_space_test(%arg0)
              : (!acsim.owner<@queue_i32>) -> i32
          acsim.terminate "success"
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
