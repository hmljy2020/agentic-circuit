// RUN: %split_file %s %t
// RUN: %not %acir_opt %t/multiple-consumers.mlir 2>&1 | %FileCheck %s --check-prefix=MULTIPLE
// RUN: %not %acir_opt %t/wrong-epoch.mlir 2>&1 | %FileCheck %s --check-prefix=EPOCH
// RUN: %not %acir_opt %t/argument-type.mlir 2>&1 | %FileCheck %s --check-prefix=ARGUMENT
// RUN: %not %acir_opt %t/non-var-op.mlir 2>&1 | %FileCheck %s --check-prefix=NON-VAR
// RUN: %not %acir_opt %t/yield-type.mlir 2>&1 | %FileCheck %s --check-prefix=YIELD

// MULTIPLE: Queue result has 2 consuming uses; insert ac.v03.fork
// EPOCH: is only legal in an ACIR contract_epoch 0.3 file
// ARGUMENT: compute body argument must match input Queue payload
// NON-VAR: operation is outside the canonical ac.var family
// YIELD: yield element type must match compute output 'i32'

//--- multiple-consumers.mlir
builtin.module attributes {ac.contract_epoch = "0.3"} {
  ac.system @s root @m as "m" tick 0 "cycle" seed {kind = "fixed", value = 0 : i64} instrumentation [] results {id = "default", format = "json"} selected true
  ac.module @m() parameters {} graph {
    %source = ac.v03.source "input" : !ac.queue_v03<i16, #ac.queue_contract<depth = 1, latency = 1, rate = 1, domain = @core, ordering = fifo>>
    %left = ac.compute %source {
    ^bb0(%value: !ac.var<i16>):
      ac.var.yield %value : !ac.var<i16>
    } : (!ac.queue_v03<i16, #ac.queue_contract<depth = 1, latency = 1, rate = 1, domain = @core, ordering = fifo>>) -> !ac.queue_v03<i16, #ac.queue_contract<depth = 1, latency = 1, rate = 1, domain = @core, ordering = fifo>>
    %right = ac.compute %source {
    ^bb0(%value: !ac.var<i16>):
      ac.var.yield %value : !ac.var<i16>
    } : (!ac.queue_v03<i16, #ac.queue_contract<depth = 1, latency = 1, rate = 1, domain = @core, ordering = fifo>>) -> !ac.queue_v03<i16, #ac.queue_contract<depth = 1, latency = 1, rate = 1, domain = @core, ordering = fifo>>
    ac.return
  }
}

//--- wrong-epoch.mlir
builtin.module attributes {ac.contract_epoch = "0.1"} {
  ac.system @s root @m as "m" tick 0 "cycle" seed {kind = "fixed", value = 0 : i64} instrumentation [] results {id = "default", format = "json"} selected true
  ac.module @m() parameters {} graph {
    %source = ac.v03.source "input" : !ac.queue_v03<i16, #ac.queue_contract<depth = 1, latency = 1, rate = 1, domain = @core, ordering = fifo>>
    ac.return
  }
}

//--- argument-type.mlir
builtin.module attributes {ac.contract_epoch = "0.3"} {
  ac.system @s root @m as "m" tick 0 "cycle" seed {kind = "fixed", value = 0 : i64} instrumentation [] results {id = "default", format = "json"} selected true
  ac.module @m() parameters {} graph {
    %source = ac.v03.source "input" : !ac.queue_v03<i16, #ac.queue_contract<depth = 1, latency = 1, rate = 1, domain = @core, ordering = fifo>>
    %result = ac.compute %source {
    ^bb0(%value: !ac.var<i32>):
      ac.var.yield %value : !ac.var<i32>
    } : (!ac.queue_v03<i16, #ac.queue_contract<depth = 1, latency = 1, rate = 1, domain = @core, ordering = fifo>>) -> !ac.queue_v03<i32, #ac.queue_contract<depth = 1, latency = 1, rate = 1, domain = @core, ordering = fifo>>
    ac.return
  }
}

//--- non-var-op.mlir
builtin.module attributes {ac.contract_epoch = "0.3"} {
  ac.system @s root @m as "m" tick 0 "cycle" seed {kind = "fixed", value = 0 : i64} instrumentation [] results {id = "default", format = "json"} selected true
  ac.module @m() parameters {} graph {
    %source = ac.v03.source "input" : !ac.queue_v03<i16, #ac.queue_contract<depth = 1, latency = 1, rate = 1, domain = @core, ordering = fifo>>
    %result = ac.compute %source {
    ^bb0(%value: !ac.var<i16>):
      %zero = arith.constant 0 : i16
      ac.var.yield %value : !ac.var<i16>
    } : (!ac.queue_v03<i16, #ac.queue_contract<depth = 1, latency = 1, rate = 1, domain = @core, ordering = fifo>>) -> !ac.queue_v03<i16, #ac.queue_contract<depth = 1, latency = 1, rate = 1, domain = @core, ordering = fifo>>
    ac.return
  }
}

//--- yield-type.mlir
builtin.module attributes {ac.contract_epoch = "0.3"} {
  ac.system @s root @m as "m" tick 0 "cycle" seed {kind = "fixed", value = 0 : i64} instrumentation [] results {id = "default", format = "json"} selected true
  ac.module @m() parameters {} graph {
    %source = ac.v03.source "input" : !ac.queue_v03<i16, #ac.queue_contract<depth = 1, latency = 1, rate = 1, domain = @core, ordering = fifo>>
    %result = ac.compute %source {
    ^bb0(%value: !ac.var<i16>):
      ac.var.yield %value : !ac.var<i16>
    } : (!ac.queue_v03<i16, #ac.queue_contract<depth = 1, latency = 1, rate = 1, domain = @core, ordering = fifo>>) -> !ac.queue_v03<i32, #ac.queue_contract<depth = 1, latency = 1, rate = 1, domain = @core, ordering = fifo>>
    ac.return
  }
}
