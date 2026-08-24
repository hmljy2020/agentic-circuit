// RUN: rm -rf %t.generated %t.frozen %t.acsim
// RUN: %acir_opt --verify-each=false --pass-pipeline='builtin.module(ac-freeze-topology)' %s -o %t.frozen
// RUN: %acir_opt --ac-lower-to-acsim --ac-binding-profile=fast --ac-binding-target=x86_64-linux-gnu %t.frozen -o %t.acsim
// RUN: %FileCheck %s < %t.acsim
// RUN: %acir_cxxgen %t.acsim --frozen-acir=%t.frozen --stop-after=compile --output-root=%t.generated --project-name=compact-loop-scale --project-identity=project.compact-loop-scale --system-name=compact_loop_scale --system-identity=system.compact-loop-scale --profile=fast --compiler=%cxx --standard-library=libstdc++ --abi-mode=default --object-format=elf --contract-flag=-std=c++20 --include-root=%source_root/include
// RUN: test "$(grep -R -h -c -F '.read(' %t.generated/src/generated/processes)" -eq 4

builtin.module attributes {ac.contract_epoch = "0.2"} {
  ac.system @compact_loop_scale root @Top as "root" tick 0 "cycle"
      workload @Top::@worker seed {kind = "fixed", value = 7 : i64}
      instrumentation [] results {id = "default", format = "json"} selected true
  ac.module @Top() parameters {} graph {
    ac.state_array @a4 element i32 entries 4 read_ports 4 write_ports 1 ownership "exclusive" init "zero" id "a4" path "a4"
    ac.state_array @a16 element i32 entries 16 read_ports 16 write_ports 1 ownership "exclusive" init "zero" id "a16" path "a16"
    ac.state_array @a64 element i32 entries 64 read_ports 64 write_ports 1 ownership "exclusive" init "zero" id "a64" path "a64"
    ac.state_array @a256 element i32 entries 256 read_ports 256 write_ports 1 ownership "exclusive" init "zero" id "a256" path "a256"
    ac.process @worker kind "workload" {
      %lb = arith.constant 0 : index
      %step = arith.constant 1 : index
      %u4 = arith.constant 4 : index
      %u16 = arith.constant 16 : index
      %u64 = arith.constant 64 : index
      %u256 = arith.constant 256 : index
      scf.for %i = %lb to %u4 step %step {
        %p = arith.index_cast %i : index to i32
        %v = ac.state_read @a4[%p] port %p : i32
      }
      scf.for %i = %lb to %u16 step %step {
        %p = arith.index_cast %i : index to i32
        %v = ac.state_read @a16[%p] port %p : i32
      }
      scf.for %i = %lb to %u64 step %step {
        %p = arith.index_cast %i : index to i32
        %v = ac.state_read @a64[%p] port %p : i32
      }
      scf.for %i = %lb to %u256 step %step {
        %p = arith.index_cast %i : index to i32
        %v = ac.state_read @a256[%p] port %p : i32
      }
      ac.yield_sim
    }
    ac.return
  }
}

// CHECK: bounded_local_backedges = array<i64:
// CHECK-COUNT-4: acsim.invoke @acir_impl_state_read_
