// RUN: %acir_cxxgen %s --stop-after=model-plan | %FileCheck %s --check-prefix=PLAN
// PLAN: stage=model-plan status=passed

builtin.module attributes {ac.contract_epoch = "0.2"} {
  acsim.model @packet_queue_model epoch "0.2" root @Top
      construction ["Top.packets"] destruction ["Top.packets"] fingerprints {
        frozen_acir = "sha256:0000000000000000000000000000000000000000000000000000000000000000",
        binding_lock = "sha256:0000000000000000000000000000000000000000000000000000000000000000",
        provider = "sha256:0000000000000000000000000000000000000000000000000000000000000000",
        profile = "sha256:0000000000000000000000000000000000000000000000000000000000000000",
        toolchain = "sha256:0000000000000000000000000000000000000000000000000000000000000000",
        schema_set = "sha256:0000000000000000000000000000000000000000000000000000000000000000"
      } {
    acsim.type @queue_packet cpp "gfsim::Queue<std::array<std::byte, 8>>"
        kind "runtime_object"
        fingerprint "sha256:1000000000000000000000000000000000000000000000000000000000000000"
    acsim.module @Top interface {ports = [], resources = [], results = []}
        static [] specialization "sha256:2000000000000000000000000000000000000000000000000000000000000000"
        exports [] {
      %packets = acsim.instance @packets target @queue_packet args [2, 16]
          specialization "sha256:3000000000000000000000000000000000000000000000000000000000000000"
          : !acsim.owner<@queue_packet>
      acsim.return
    }
    %object, %activation = acsim.dispatch @Top::@packets path "Top.packets"
        indices [] object 0 activation 0 work "gfsim::QueueRuntime::work"
        xfer "gfsim::QueueRuntime::xfer" reset "gfsim::QueueRuntime::reset"
        validate "gfsim::QueueRuntime::validate"
        : !acsim.object_id, !acsim.activation_id
    acsim.activate %activation to %object
        : !acsim.activation_id to !acsim.object_id
  }
}
