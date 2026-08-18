// RUN: %split_file %s %t
// RUN: %not %acir_opt_public %t/inline.mlir 2>&1 | %FileCheck %s --check-prefix=INLINE
// RUN: %not %acir_opt_public %t/missing-dispatch.mlir 2>&1 | %FileCheck %s --check-prefix=DISPATCH
// RUN: %not %acir_opt_public %t/bad-static-args.mlir 2>&1 | %FileCheck %s --check-prefix=ARGS
// RUN: %not %acir_opt_public %t/implementation-owned.mlir 2>&1 | %FileCheck %s --check-prefix=IMPLEMENTATION

// INLINE: C++ type reference '@queue' has incompatible acsim.type kind 'runtime_object'
// DISPATCH: every runtime object requires exactly one typed dispatch row
// ARGS: runtime_object static arguments require entry capacity and an optional byte capacity
// IMPLEMENTATION: ownership expansion permits only runtime_object acsim.type targets

//--- inline.mlir
builtin.module attributes {ac.contract_epoch = "0.2"} {
  acsim.model @m epoch "0.2" root @Top construction [] destruction [] fingerprints {
    frozen_acir = "sha256:0000000000000000000000000000000000000000000000000000000000000000",
    binding_lock = "sha256:0000000000000000000000000000000000000000000000000000000000000000",
    provider = "sha256:0000000000000000000000000000000000000000000000000000000000000000",
    profile = "sha256:0000000000000000000000000000000000000000000000000000000000000000",
    toolchain = "sha256:0000000000000000000000000000000000000000000000000000000000000000",
    schema_set = "sha256:0000000000000000000000000000000000000000000000000000000000000000"
  } {
    acsim.type @queue cpp "gfsim::Queue<std::int32_t>" kind "runtime_object"
        fingerprint "sha256:1000000000000000000000000000000000000000000000000000000000000000"
    acsim.module @Top interface {ports = [], resources = [], results = []}
        static [] specialization "sha256:2000000000000000000000000000000000000000000000000000000000000000"
        exports [] {
      %value = acsim.inline @queue() : () -> !acsim.expr<@queue>
      acsim.return
    }
  }
}

//--- missing-dispatch.mlir
builtin.module attributes {ac.contract_epoch = "0.2"} {
  acsim.model @m epoch "0.2" root @Top construction ["Top.queue"]
      destruction ["Top.queue"] fingerprints {
    frozen_acir = "sha256:0000000000000000000000000000000000000000000000000000000000000000",
    binding_lock = "sha256:0000000000000000000000000000000000000000000000000000000000000000",
    provider = "sha256:0000000000000000000000000000000000000000000000000000000000000000",
    profile = "sha256:0000000000000000000000000000000000000000000000000000000000000000",
    toolchain = "sha256:0000000000000000000000000000000000000000000000000000000000000000",
    schema_set = "sha256:0000000000000000000000000000000000000000000000000000000000000000"
  } {
    acsim.type @queue_type cpp "gfsim::Queue<std::int32_t>" kind "runtime_object"
        fingerprint "sha256:1000000000000000000000000000000000000000000000000000000000000000"
    acsim.module @Top interface {ports = [], resources = [], results = []}
        static [] specialization "sha256:2000000000000000000000000000000000000000000000000000000000000000"
        exports [] {
      %queue = acsim.instance @queue target @queue_type args [1]
          specialization "sha256:3000000000000000000000000000000000000000000000000000000000000000"
          : !acsim.owner<@queue_type>
      acsim.return
    }
  }
}

//--- bad-static-args.mlir
builtin.module attributes {ac.contract_epoch = "0.2"} {
  acsim.model @m epoch "0.2" root @Top construction ["Top.queue"]
      destruction ["Top.queue"] fingerprints {
    frozen_acir = "sha256:0000000000000000000000000000000000000000000000000000000000000000",
    binding_lock = "sha256:0000000000000000000000000000000000000000000000000000000000000000",
    provider = "sha256:0000000000000000000000000000000000000000000000000000000000000000",
    profile = "sha256:0000000000000000000000000000000000000000000000000000000000000000",
    toolchain = "sha256:0000000000000000000000000000000000000000000000000000000000000000",
    schema_set = "sha256:0000000000000000000000000000000000000000000000000000000000000000"
  } {
    acsim.type @queue_type cpp "gfsim::Queue<std::int32_t>" kind "runtime_object"
        fingerprint "sha256:1000000000000000000000000000000000000000000000000000000000000000"
    acsim.module @Top interface {ports = [], resources = [], results = []}
        static [] specialization "sha256:2000000000000000000000000000000000000000000000000000000000000000"
        exports [] {
      %queue = acsim.instance @queue target @queue_type args []
          specialization "sha256:3000000000000000000000000000000000000000000000000000000000000000"
          : !acsim.owner<@queue_type>
      acsim.return
    }
  }
}

//--- implementation-owned.mlir
builtin.module attributes {ac.contract_epoch = "0.2"} {
  acsim.model @m epoch "0.2" root @Top construction ["Top.helper"]
      destruction ["Top.helper"] fingerprints {
    frozen_acir = "sha256:0000000000000000000000000000000000000000000000000000000000000000",
    binding_lock = "sha256:0000000000000000000000000000000000000000000000000000000000000000",
    provider = "sha256:0000000000000000000000000000000000000000000000000000000000000000",
    profile = "sha256:0000000000000000000000000000000000000000000000000000000000000000",
    toolchain = "sha256:0000000000000000000000000000000000000000000000000000000000000000",
    schema_set = "sha256:0000000000000000000000000000000000000000000000000000000000000000"
  } {
    acsim.type @helper_type cpp "acir::generated::helper" kind "implementation"
        fingerprint "sha256:1000000000000000000000000000000000000000000000000000000000000000"
    acsim.module @Top interface {ports = [], resources = [], results = []}
        static [] specialization "sha256:2000000000000000000000000000000000000000000000000000000000000000"
        exports [] {
      %helper = acsim.instance @helper target @helper_type args [1]
          specialization "sha256:3000000000000000000000000000000000000000000000000000000000000000"
          : !acsim.owner<@helper_type>
      acsim.return
    }
  }
}
