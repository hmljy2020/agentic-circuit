module attributes {ac.contract_epoch = "0.2"} {
  acsim.model @router2x2_demo epoch "0.2" root @Top construction ["root.in0", "root.in1", "root.out0", "root.out1", "root.arbiter", "root.producer0", "root.producer1", "root.sink0", "root.sink1"] destruction ["root.sink1", "root.sink0", "root.producer1", "root.producer0", "root.arbiter", "root.out1", "root.out0", "root.in1", "root.in0"] fingerprints {binding_lock = "sha256:4f53cda18c2baa0c0354bb5f9a3ecbe5ed12ab4d8e11ba873c2f11161202b945", frozen_acir = "sha256:858d0d26f9e05ba19327a7659934da8ce9988d367f671205610c67270ceec9ce", profile = "sha256:079c9d12005aad817f722d2f0a34ccc3185b5ec0ce06ee243f945e4e1bb7b4c7", provider = "sha256:4f53cda18c2baa0c0354bb5f9a3ecbe5ed12ab4d8e11ba873c2f11161202b945", schema_set = "sha256:4f53cda18c2baa0c0354bb5f9a3ecbe5ed12ab4d8e11ba873c2f11161202b945", toolchain = "sha256:bd7deae3fdf722776d18998ce9b58d48bb1c2b195a6b2a3e32c9f60bf0ae557b"} {
    acsim.type @acir_impl_contract_assert_23e22ef018e990817d91280d4edfe40b3bc98c984067c2244df086b13f76af5c cpp "acir::generated::impl_contract_assert_23e22ef018e990817d91280d4edfe40b3bc98c984067c2244df086b13f76af5c" kind "implementation" fingerprint "sha256:23e22ef018e990817d91280d4edfe40b3bc98c984067c2244df086b13f76af5c"
    acsim.type @acir_impl_contract_assert_2d666e299b26d0732ee517d191ed21fd2340e632727d6173b03cf87eafc12a63 cpp "acir::generated::impl_contract_assert_2d666e299b26d0732ee517d191ed21fd2340e632727d6173b03cf87eafc12a63" kind "implementation" fingerprint "sha256:2d666e299b26d0732ee517d191ed21fd2340e632727d6173b03cf87eafc12a63"
    acsim.type @acir_impl_contract_assert_78028a2a15273482761948460d6bc9e7941edf3c6ba37a4bad14db78f79293c6 cpp "acir::generated::impl_contract_assert_78028a2a15273482761948460d6bc9e7941edf3c6ba37a4bad14db78f79293c6" kind "implementation" fingerprint "sha256:78028a2a15273482761948460d6bc9e7941edf3c6ba37a4bad14db78f79293c6"
    acsim.type @acir_impl_contract_assert_9b5eef0fb7e52f816bdcb999aba9897a8ff413fc43d86338bd1ce15f4d2e3f70 cpp "acir::generated::impl_contract_assert_9b5eef0fb7e52f816bdcb999aba9897a8ff413fc43d86338bd1ce15f4d2e3f70" kind "implementation" fingerprint "sha256:9b5eef0fb7e52f816bdcb999aba9897a8ff413fc43d86338bd1ce15f4d2e3f70"
    acsim.type @acir_impl_contract_assert_a7f04fc1fac43b39f1236483cf41bc26764144a48cccc7ead3692984ee1c54b5 cpp "acir::generated::impl_contract_assert_a7f04fc1fac43b39f1236483cf41bc26764144a48cccc7ead3692984ee1c54b5" kind "implementation" fingerprint "sha256:a7f04fc1fac43b39f1236483cf41bc26764144a48cccc7ead3692984ee1c54b5"
    acsim.type @acir_impl_contract_assert_af028d399dddeaeda959b8741ea8e87019af94c75785ac2af22b94932b96975d cpp "acir::generated::impl_contract_assert_af028d399dddeaeda959b8741ea8e87019af94c75785ac2af22b94932b96975d" kind "implementation" fingerprint "sha256:af028d399dddeaeda959b8741ea8e87019af94c75785ac2af22b94932b96975d"
    acsim.type @acir_impl_contract_assert_b0547553ec5c7c36f1267767f8063f1a077a242aa30eae8fbde32d79ce8560f6 cpp "acir::generated::impl_contract_assert_b0547553ec5c7c36f1267767f8063f1a077a242aa30eae8fbde32d79ce8560f6" kind "implementation" fingerprint "sha256:b0547553ec5c7c36f1267767f8063f1a077a242aa30eae8fbde32d79ce8560f6"
    acsim.type @acir_impl_contract_assert_e774a4acf731ab8eef2aba4d46656c93fa79843dce69ca8a06ed1f369b727089 cpp "acir::generated::impl_contract_assert_e774a4acf731ab8eef2aba4d46656c93fa79843dce69ca8a06ed1f369b727089" kind "implementation" fingerprint "sha256:e774a4acf731ab8eef2aba4d46656c93fa79843dce69ca8a06ed1f369b727089"
    acsim.type @acir_impl_queue_peek_86c269d7078a19cbc3d6beb632ecb8bfd8c0fabeeff9548290d6c411d59ce832 cpp "acir::generated::impl_queue_peek_86c269d7078a19cbc3d6beb632ecb8bfd8c0fabeeff9548290d6c411d59ce832" kind "implementation" fingerprint "sha256:86c269d7078a19cbc3d6beb632ecb8bfd8c0fabeeff9548290d6c411d59ce832"
    acsim.type @acir_impl_queue_try_recv_dbd808e8a08c9d172873993a800a4c3544ea0bf8a0ed73a33ca5723dbfb2a14f cpp "acir::generated::impl_queue_try_recv_dbd808e8a08c9d172873993a800a4c3544ea0bf8a0ed73a33ca5723dbfb2a14f" kind "implementation" fingerprint "sha256:dbd808e8a08c9d172873993a800a4c3544ea0bf8a0ed73a33ca5723dbfb2a14f"
    acsim.type @acir_impl_queue_try_send_e6032c4723da335240b746d3be2b749bd47c74ad843ff77e8ff6ed7ec94fea65 cpp "acir::generated::impl_queue_try_send_e6032c4723da335240b746d3be2b749bd47c74ad843ff77e8ff6ed7ec94fea65" kind "implementation" fingerprint "sha256:e6032c4723da335240b746d3be2b749bd47c74ad843ff77e8ff6ed7ec94fea65"
    acsim.type @acir_impl_scalar_unwrap_ff9a680faa57c70912aa78f48e6e6a7c8e1d68ee2c73b2ec59e1db39b804ff76 cpp "acir::generated::impl_scalar_unwrap_ff9a680faa57c70912aa78f48e6e6a7c8e1d68ee2c73b2ec59e1db39b804ff76" kind "implementation" fingerprint "sha256:ff9a680faa57c70912aa78f48e6e6a7c8e1d68ee2c73b2ec59e1db39b804ff76"
    acsim.type @acir_impl_scalar_wrap_973ddda5db5ff882c81ec29f3a1984a9dc63b3bac3c38e3e2036995c135bfbc6 cpp "acir::generated::impl_scalar_wrap_973ddda5db5ff882c81ec29f3a1984a9dc63b3bac3c38e3e2036995c135bfbc6" kind "implementation" fingerprint "sha256:973ddda5db5ff882c81ec29f3a1984a9dc63b3bac3c38e3e2036995c135bfbc6"
    acsim.type @acir_impl_wake_next_delta_27cb4376e0c3f696c7a3d65ba8612843ec70b21d944add7d0b26efb005a04d8c cpp "acir::generated::impl_wake_next_delta_27cb4376e0c3f696c7a3d65ba8612843ec70b21d944add7d0b26efb005a04d8c" kind "implementation" fingerprint "sha256:27cb4376e0c3f696c7a3d65ba8612843ec70b21d944add7d0b26efb005a04d8c"
    acsim.type @acir_impl_wake_queue_readable_ef2bf2cff9aa2130207f640ff7425779e60c6e95346c73ae138dcac696f7e917 cpp "acir::generated::impl_wake_queue_readable_ef2bf2cff9aa2130207f640ff7425779e60c6e95346c73ae138dcac696f7e917" kind "implementation" fingerprint "sha256:ef2bf2cff9aa2130207f640ff7425779e60c6e95346c73ae138dcac696f7e917"
    acsim.type @acir_impl_wake_queue_writable_da1dabd0494cae8ff77a429dc12b26411a9de3ff68a505fd402a75decfcae4a4 cpp "acir::generated::impl_wake_queue_writable_da1dabd0494cae8ff77a429dc12b26411a9de3ff68a505fd402a75decfcae4a4" kind "implementation" fingerprint "sha256:da1dabd0494cae8ff77a429dc12b26411a9de3ff68a505fd402a75decfcae4a4"
    acsim.type @acir_queue_25d96b515101c39468cc7c64b72583e92f965f22f4c3ad7ad8ddabaf8d1574d1 cpp "gfsim::Queue<std::int32_t>" kind "runtime_object" fingerprint "sha256:25d96b515101c39468cc7c64b72583e92f965f22f4c3ad7ad8ddabaf8d1574d1"
    acsim.type @acir_value_4382085a956d169d939be08807ee71613c27a4a4a6c990a02ca53c7421550c3a cpp "std::int32_t" kind "value" fingerprint "sha256:4382085a956d169d939be08807ee71613c27a4a4a6c990a02ca53c7421550c3a"
    acsim.type @acir_wake_next_delta cpp "acir::generated::wake_next_delta" kind "wake" fingerprint "sha256:8cf214054e3ad1f49ca7091e040092971fe7dec32ccfd59554fdef160e889c2a"
    acsim.type @acir_wake_queue_readable cpp "acir::generated::wake_queue_readable" kind "wake" fingerprint "sha256:6440dbe429f3db95b3a4530f2a7e2b4660295c97a8a1af79ba0a7dfe3c4a8a0b"
    acsim.type @acir_wake_queue_writable cpp "acir::generated::wake_queue_writable" kind "wake" fingerprint "sha256:9b3448c249d4e00eeb840b4c73e8cd5996334ea43d4ab8c37350c1bc2503a505"
    acsim.module @Top interface {ports = [], resources = [], results = []} static [] specialization "sha256:db3b621e1e2c4cfba2df7a41cefb947e2c3f202c365c91fc87a697b229b32b40" exports [] {
      %0 = acsim.instance @in0 target @acir_queue_25d96b515101c39468cc7c64b72583e92f965f22f4c3ad7ad8ddabaf8d1574d1 args [16, 64] specialization "sha256:c51a130ffc15b9dfd29a175434d754a3c50ac999d093f36263e65d251e334b2d" : !acsim.owner<@acir_queue_25d96b515101c39468cc7c64b72583e92f965f22f4c3ad7ad8ddabaf8d1574d1>
      %1 = acsim.instance @in1 target @acir_queue_25d96b515101c39468cc7c64b72583e92f965f22f4c3ad7ad8ddabaf8d1574d1 args [16, 64] specialization "sha256:c51a130ffc15b9dfd29a175434d754a3c50ac999d093f36263e65d251e334b2d" : !acsim.owner<@acir_queue_25d96b515101c39468cc7c64b72583e92f965f22f4c3ad7ad8ddabaf8d1574d1>
      %2 = acsim.instance @out0 target @acir_queue_25d96b515101c39468cc7c64b72583e92f965f22f4c3ad7ad8ddabaf8d1574d1 args [16, 64] specialization "sha256:c51a130ffc15b9dfd29a175434d754a3c50ac999d093f36263e65d251e334b2d" : !acsim.owner<@acir_queue_25d96b515101c39468cc7c64b72583e92f965f22f4c3ad7ad8ddabaf8d1574d1>
      %3 = acsim.instance @out1 target @acir_queue_25d96b515101c39468cc7c64b72583e92f965f22f4c3ad7ad8ddabaf8d1574d1 args [16, 64] specialization "sha256:c51a130ffc15b9dfd29a175434d754a3c50ac999d093f36263e65d251e334b2d" : !acsim.owner<@acir_queue_25d96b515101c39468cc7c64b72583e92f965f22f4c3ad7ad8ddabaf8d1574d1>
      acsim.process @arbiter captures(%0 : !acsim.owner<@acir_queue_25d96b515101c39468cc7c64b72583e92f965f22f4c3ad7ad8ddabaf8d1574d1>, %1 : !acsim.owner<@acir_queue_25d96b515101c39468cc7c64b72583e92f965f22f4c3ad7ad8ddabaf8d1574d1>, %2 : !acsim.owner<@acir_queue_25d96b515101c39468cc7c64b72583e92f965f22f4c3ad7ad8ddabaf8d1574d1>, %3 : !acsim.owner<@acir_queue_25d96b515101c39468cc7c64b72583e92f965f22f4c3ad7ad8ddabaf8d1574d1>) names ["queue_in0", "queue_in1", "queue_out0", "queue_out1"] entry @entry pcs [@entry, @pc00000001, @pc00000002, @pc00000003, @pc00000004] live [{name = "live00000000", type = !acsim.value<@acir_value_4382085a956d169d939be08807ee71613c27a4a4a6c990a02ca53c7421550c3a>}, {name = "live00000001", type = !acsim.value<@acir_value_4382085a956d169d939be08807ee71613c27a4a4a6c990a02ca53c7421550c3a>}] fairness 19 specialization "sha256:c61813baded3cb0be13b890ad2cddbcf220f2621b00602bb4f45c26ba3367fe3" {
state @entry {
      ^bb0(%arg0: !acsim.owner<@acir_queue_25d96b515101c39468cc7c64b72583e92f965f22f4c3ad7ad8ddabaf8d1574d1>, %arg1: !acsim.owner<@acir_queue_25d96b515101c39468cc7c64b72583e92f965f22f4c3ad7ad8ddabaf8d1574d1>, %arg2: !acsim.owner<@acir_queue_25d96b515101c39468cc7c64b72583e92f965f22f4c3ad7ad8ddabaf8d1574d1>, %arg3: !acsim.owner<@acir_queue_25d96b515101c39468cc7c64b72583e92f965f22f4c3ad7ad8ddabaf8d1574d1>):
        %4:2 = acsim.invoke @acir_impl_queue_peek_86c269d7078a19cbc3d6beb632ecb8bfd8c0fabeeff9548290d6c411d59ce832(%arg0) : (!acsim.owner<@acir_queue_25d96b515101c39468cc7c64b72583e92f965f22f4c3ad7ad8ddabaf8d1574d1>) -> (i32, i1)
        cf.cond_br %4#1, ^bb1(%4#0 : i32), ^bb6
      ^bb1(%5: i32):  // pred: ^bb0
        %6:2 = acsim.invoke @acir_impl_queue_try_recv_dbd808e8a08c9d172873993a800a4c3544ea0bf8a0ed73a33ca5723dbfb2a14f(%arg0) : (!acsim.owner<@acir_queue_25d96b515101c39468cc7c64b72583e92f965f22f4c3ad7ad8ddabaf8d1574d1>) -> (i32, i1)
        acsim.invoke @acir_impl_contract_assert_b0547553ec5c7c36f1267767f8063f1a077a242aa30eae8fbde32d79ce8560f6(%6#1) : (i1) -> ()
        %7 = arith.cmpi eq, %6#0, %5 : i32
        acsim.invoke @acir_impl_contract_assert_e774a4acf731ab8eef2aba4d46656c93fa79843dce69ca8a06ed1f369b727089(%7) : (i1) -> ()
        %c3_i32 = arith.constant 3 : i32
        %c0_i32 = arith.constant 0 : i32
        %8 = arith.andi %6#0, %c3_i32 : i32
        %9 = arith.cmpi eq, %8, %c0_i32 : i32
        cf.cond_br %9, ^bb2(%6#0 : i32), ^bb4(%6#0 : i32)
      ^bb2(%10: i32):  // pred: ^bb1
        %11 = acsim.invoke @acir_impl_queue_try_send_e6032c4723da335240b746d3be2b749bd47c74ad843ff77e8ff6ed7ec94fea65(%arg2, %10) : (!acsim.owner<@acir_queue_25d96b515101c39468cc7c64b72583e92f965f22f4c3ad7ad8ddabaf8d1574d1>, i32) -> i1
        cf.cond_br %11, ^bb11, ^bb3(%10 : i32)
      ^bb3(%12: i32):  // pred: ^bb2
        %13 = acsim.inline @acir_impl_scalar_wrap_973ddda5db5ff882c81ec29f3a1984a9dc63b3bac3c38e3e2036995c135bfbc6(%12) : (i32) -> !acsim.value<@acir_value_4382085a956d169d939be08807ee71613c27a4a4a6c990a02ca53c7421550c3a>
        acsim.live.store %13 in @arbiter slot "live00000000" : !acsim.value<@acir_value_4382085a956d169d939be08807ee71613c27a4a4a6c990a02ca53c7421550c3a>
        %14 = acsim.invoke @acir_impl_wake_queue_writable_da1dabd0494cae8ff77a429dc12b26411a9de3ff68a505fd402a75decfcae4a4(%arg2) : (!acsim.owner<@acir_queue_25d96b515101c39468cc7c64b72583e92f965f22f4c3ad7ad8ddabaf8d1574d1>) -> !acsim.wake<@acir_wake_queue_writable>
        acsim.suspend @pc00000001 on %14 : !acsim.wake<@acir_wake_queue_writable>
      ^bb4(%15: i32):  // pred: ^bb1
        %16 = acsim.invoke @acir_impl_queue_try_send_e6032c4723da335240b746d3be2b749bd47c74ad843ff77e8ff6ed7ec94fea65(%arg3, %15) : (!acsim.owner<@acir_queue_25d96b515101c39468cc7c64b72583e92f965f22f4c3ad7ad8ddabaf8d1574d1>, i32) -> i1
        cf.cond_br %16, ^bb11, ^bb5(%15 : i32)
      ^bb5(%17: i32):  // pred: ^bb4
        %18 = acsim.inline @acir_impl_scalar_wrap_973ddda5db5ff882c81ec29f3a1984a9dc63b3bac3c38e3e2036995c135bfbc6(%17) : (i32) -> !acsim.value<@acir_value_4382085a956d169d939be08807ee71613c27a4a4a6c990a02ca53c7421550c3a>
        acsim.live.store %18 in @arbiter slot "live00000000" : !acsim.value<@acir_value_4382085a956d169d939be08807ee71613c27a4a4a6c990a02ca53c7421550c3a>
        %19 = acsim.invoke @acir_impl_wake_queue_writable_da1dabd0494cae8ff77a429dc12b26411a9de3ff68a505fd402a75decfcae4a4(%arg3) : (!acsim.owner<@acir_queue_25d96b515101c39468cc7c64b72583e92f965f22f4c3ad7ad8ddabaf8d1574d1>) -> !acsim.wake<@acir_wake_queue_writable>
        acsim.suspend @pc00000002 on %19 : !acsim.wake<@acir_wake_queue_writable>
      ^bb6:  // pred: ^bb0
        %20:2 = acsim.invoke @acir_impl_queue_peek_86c269d7078a19cbc3d6beb632ecb8bfd8c0fabeeff9548290d6c411d59ce832(%arg1) : (!acsim.owner<@acir_queue_25d96b515101c39468cc7c64b72583e92f965f22f4c3ad7ad8ddabaf8d1574d1>) -> (i32, i1)
        cf.cond_br %20#1, ^bb7(%20#0 : i32), ^bb11
      ^bb7(%21: i32):  // pred: ^bb6
        %22:2 = acsim.invoke @acir_impl_queue_try_recv_dbd808e8a08c9d172873993a800a4c3544ea0bf8a0ed73a33ca5723dbfb2a14f(%arg1) : (!acsim.owner<@acir_queue_25d96b515101c39468cc7c64b72583e92f965f22f4c3ad7ad8ddabaf8d1574d1>) -> (i32, i1)
        acsim.invoke @acir_impl_contract_assert_2d666e299b26d0732ee517d191ed21fd2340e632727d6173b03cf87eafc12a63(%22#1) : (i1) -> ()
        %23 = arith.cmpi eq, %22#0, %21 : i32
        acsim.invoke @acir_impl_contract_assert_a7f04fc1fac43b39f1236483cf41bc26764144a48cccc7ead3692984ee1c54b5(%23) : (i1) -> ()
        %c3_i32_16 = arith.constant 3 : i32
        %c0_i32_17 = arith.constant 0 : i32
        %24 = arith.andi %22#0, %c3_i32_16 : i32
        %25 = arith.cmpi eq, %24, %c0_i32_17 : i32
        cf.cond_br %25, ^bb8(%22#0 : i32), ^bb10(%22#0 : i32)
      ^bb8(%26: i32):  // pred: ^bb7
        %27 = acsim.invoke @acir_impl_queue_try_send_e6032c4723da335240b746d3be2b749bd47c74ad843ff77e8ff6ed7ec94fea65(%arg2, %26) : (!acsim.owner<@acir_queue_25d96b515101c39468cc7c64b72583e92f965f22f4c3ad7ad8ddabaf8d1574d1>, i32) -> i1
        cf.cond_br %27, ^bb11, ^bb9(%26 : i32)
      ^bb9(%28: i32):  // pred: ^bb8
        %29 = acsim.inline @acir_impl_scalar_wrap_973ddda5db5ff882c81ec29f3a1984a9dc63b3bac3c38e3e2036995c135bfbc6(%28) : (i32) -> !acsim.value<@acir_value_4382085a956d169d939be08807ee71613c27a4a4a6c990a02ca53c7421550c3a>
        acsim.live.store %29 in @arbiter slot "live00000001" : !acsim.value<@acir_value_4382085a956d169d939be08807ee71613c27a4a4a6c990a02ca53c7421550c3a>
        %30 = acsim.invoke @acir_impl_wake_queue_writable_da1dabd0494cae8ff77a429dc12b26411a9de3ff68a505fd402a75decfcae4a4(%arg2) : (!acsim.owner<@acir_queue_25d96b515101c39468cc7c64b72583e92f965f22f4c3ad7ad8ddabaf8d1574d1>) -> !acsim.wake<@acir_wake_queue_writable>
        acsim.suspend @pc00000003 on %30 : !acsim.wake<@acir_wake_queue_writable>
      ^bb10(%31: i32):  // pred: ^bb7
        %32 = acsim.invoke @acir_impl_queue_try_send_e6032c4723da335240b746d3be2b749bd47c74ad843ff77e8ff6ed7ec94fea65(%arg3, %31) : (!acsim.owner<@acir_queue_25d96b515101c39468cc7c64b72583e92f965f22f4c3ad7ad8ddabaf8d1574d1>, i32) -> i1
        cf.cond_br %32, ^bb11, ^bb12(%31 : i32)
      ^bb11:  // 5 preds: ^bb2, ^bb4, ^bb6, ^bb8, ^bb10
        %33 = acsim.invoke @acir_impl_wake_next_delta_27cb4376e0c3f696c7a3d65ba8612843ec70b21d944add7d0b26efb005a04d8c() : () -> !acsim.wake<@acir_wake_next_delta>
        acsim.suspend @entry on %33 : !acsim.wake<@acir_wake_next_delta>
      ^bb12(%34: i32):  // pred: ^bb10
        %35 = acsim.inline @acir_impl_scalar_wrap_973ddda5db5ff882c81ec29f3a1984a9dc63b3bac3c38e3e2036995c135bfbc6(%34) : (i32) -> !acsim.value<@acir_value_4382085a956d169d939be08807ee71613c27a4a4a6c990a02ca53c7421550c3a>
        acsim.live.store %35 in @arbiter slot "live00000001" : !acsim.value<@acir_value_4382085a956d169d939be08807ee71613c27a4a4a6c990a02ca53c7421550c3a>
        %36 = acsim.invoke @acir_impl_wake_queue_writable_da1dabd0494cae8ff77a429dc12b26411a9de3ff68a505fd402a75decfcae4a4(%arg3) : (!acsim.owner<@acir_queue_25d96b515101c39468cc7c64b72583e92f965f22f4c3ad7ad8ddabaf8d1574d1>) -> !acsim.wake<@acir_wake_queue_writable>
        acsim.suspend @pc00000004 on %36 : !acsim.wake<@acir_wake_queue_writable>
      }
state @pc00000001 {
      ^bb0(%arg0: !acsim.owner<@acir_queue_25d96b515101c39468cc7c64b72583e92f965f22f4c3ad7ad8ddabaf8d1574d1>, %arg1: !acsim.owner<@acir_queue_25d96b515101c39468cc7c64b72583e92f965f22f4c3ad7ad8ddabaf8d1574d1>, %arg2: !acsim.owner<@acir_queue_25d96b515101c39468cc7c64b72583e92f965f22f4c3ad7ad8ddabaf8d1574d1>, %arg3: !acsim.owner<@acir_queue_25d96b515101c39468cc7c64b72583e92f965f22f4c3ad7ad8ddabaf8d1574d1>):
        %4 = acsim.live.load @arbiter slot "live00000000" : !acsim.value<@acir_value_4382085a956d169d939be08807ee71613c27a4a4a6c990a02ca53c7421550c3a>
        %5 = acsim.inline @acir_impl_scalar_unwrap_ff9a680faa57c70912aa78f48e6e6a7c8e1d68ee2c73b2ec59e1db39b804ff76(%4) : (!acsim.value<@acir_value_4382085a956d169d939be08807ee71613c27a4a4a6c990a02ca53c7421550c3a>) -> i32
        %6 = acsim.invoke @acir_impl_queue_try_send_e6032c4723da335240b746d3be2b749bd47c74ad843ff77e8ff6ed7ec94fea65(%arg2, %5) : (!acsim.owner<@acir_queue_25d96b515101c39468cc7c64b72583e92f965f22f4c3ad7ad8ddabaf8d1574d1>, i32) -> i1
        cf.cond_br %6, ^bb1, ^bb2
      ^bb1:  // pred: ^bb0
        %7 = acsim.invoke @acir_impl_wake_next_delta_27cb4376e0c3f696c7a3d65ba8612843ec70b21d944add7d0b26efb005a04d8c() : () -> !acsim.wake<@acir_wake_next_delta>
        acsim.suspend @entry on %7 : !acsim.wake<@acir_wake_next_delta>
      ^bb2:  // pred: ^bb0
        %8 = acsim.invoke @acir_impl_wake_queue_writable_da1dabd0494cae8ff77a429dc12b26411a9de3ff68a505fd402a75decfcae4a4(%arg2) : (!acsim.owner<@acir_queue_25d96b515101c39468cc7c64b72583e92f965f22f4c3ad7ad8ddabaf8d1574d1>) -> !acsim.wake<@acir_wake_queue_writable>
        acsim.suspend @pc00000001 on %8 : !acsim.wake<@acir_wake_queue_writable>
      }
state @pc00000002 {
      ^bb0(%arg0: !acsim.owner<@acir_queue_25d96b515101c39468cc7c64b72583e92f965f22f4c3ad7ad8ddabaf8d1574d1>, %arg1: !acsim.owner<@acir_queue_25d96b515101c39468cc7c64b72583e92f965f22f4c3ad7ad8ddabaf8d1574d1>, %arg2: !acsim.owner<@acir_queue_25d96b515101c39468cc7c64b72583e92f965f22f4c3ad7ad8ddabaf8d1574d1>, %arg3: !acsim.owner<@acir_queue_25d96b515101c39468cc7c64b72583e92f965f22f4c3ad7ad8ddabaf8d1574d1>):
        %4 = acsim.live.load @arbiter slot "live00000000" : !acsim.value<@acir_value_4382085a956d169d939be08807ee71613c27a4a4a6c990a02ca53c7421550c3a>
        %5 = acsim.inline @acir_impl_scalar_unwrap_ff9a680faa57c70912aa78f48e6e6a7c8e1d68ee2c73b2ec59e1db39b804ff76(%4) : (!acsim.value<@acir_value_4382085a956d169d939be08807ee71613c27a4a4a6c990a02ca53c7421550c3a>) -> i32
        %6 = acsim.invoke @acir_impl_queue_try_send_e6032c4723da335240b746d3be2b749bd47c74ad843ff77e8ff6ed7ec94fea65(%arg3, %5) : (!acsim.owner<@acir_queue_25d96b515101c39468cc7c64b72583e92f965f22f4c3ad7ad8ddabaf8d1574d1>, i32) -> i1
        cf.cond_br %6, ^bb1, ^bb2
      ^bb1:  // pred: ^bb0
        %7 = acsim.invoke @acir_impl_wake_next_delta_27cb4376e0c3f696c7a3d65ba8612843ec70b21d944add7d0b26efb005a04d8c() : () -> !acsim.wake<@acir_wake_next_delta>
        acsim.suspend @entry on %7 : !acsim.wake<@acir_wake_next_delta>
      ^bb2:  // pred: ^bb0
        %8 = acsim.invoke @acir_impl_wake_queue_writable_da1dabd0494cae8ff77a429dc12b26411a9de3ff68a505fd402a75decfcae4a4(%arg3) : (!acsim.owner<@acir_queue_25d96b515101c39468cc7c64b72583e92f965f22f4c3ad7ad8ddabaf8d1574d1>) -> !acsim.wake<@acir_wake_queue_writable>
        acsim.suspend @pc00000002 on %8 : !acsim.wake<@acir_wake_queue_writable>
      }
state @pc00000003 {
      ^bb0(%arg0: !acsim.owner<@acir_queue_25d96b515101c39468cc7c64b72583e92f965f22f4c3ad7ad8ddabaf8d1574d1>, %arg1: !acsim.owner<@acir_queue_25d96b515101c39468cc7c64b72583e92f965f22f4c3ad7ad8ddabaf8d1574d1>, %arg2: !acsim.owner<@acir_queue_25d96b515101c39468cc7c64b72583e92f965f22f4c3ad7ad8ddabaf8d1574d1>, %arg3: !acsim.owner<@acir_queue_25d96b515101c39468cc7c64b72583e92f965f22f4c3ad7ad8ddabaf8d1574d1>):
        %4 = acsim.live.load @arbiter slot "live00000001" : !acsim.value<@acir_value_4382085a956d169d939be08807ee71613c27a4a4a6c990a02ca53c7421550c3a>
        %5 = acsim.inline @acir_impl_scalar_unwrap_ff9a680faa57c70912aa78f48e6e6a7c8e1d68ee2c73b2ec59e1db39b804ff76(%4) : (!acsim.value<@acir_value_4382085a956d169d939be08807ee71613c27a4a4a6c990a02ca53c7421550c3a>) -> i32
        %6 = acsim.invoke @acir_impl_queue_try_send_e6032c4723da335240b746d3be2b749bd47c74ad843ff77e8ff6ed7ec94fea65(%arg2, %5) : (!acsim.owner<@acir_queue_25d96b515101c39468cc7c64b72583e92f965f22f4c3ad7ad8ddabaf8d1574d1>, i32) -> i1
        cf.cond_br %6, ^bb1, ^bb2
      ^bb1:  // pred: ^bb0
        %7 = acsim.invoke @acir_impl_wake_next_delta_27cb4376e0c3f696c7a3d65ba8612843ec70b21d944add7d0b26efb005a04d8c() : () -> !acsim.wake<@acir_wake_next_delta>
        acsim.suspend @entry on %7 : !acsim.wake<@acir_wake_next_delta>
      ^bb2:  // pred: ^bb0
        %8 = acsim.invoke @acir_impl_wake_queue_writable_da1dabd0494cae8ff77a429dc12b26411a9de3ff68a505fd402a75decfcae4a4(%arg2) : (!acsim.owner<@acir_queue_25d96b515101c39468cc7c64b72583e92f965f22f4c3ad7ad8ddabaf8d1574d1>) -> !acsim.wake<@acir_wake_queue_writable>
        acsim.suspend @pc00000003 on %8 : !acsim.wake<@acir_wake_queue_writable>
      }
state @pc00000004 {
      ^bb0(%arg0: !acsim.owner<@acir_queue_25d96b515101c39468cc7c64b72583e92f965f22f4c3ad7ad8ddabaf8d1574d1>, %arg1: !acsim.owner<@acir_queue_25d96b515101c39468cc7c64b72583e92f965f22f4c3ad7ad8ddabaf8d1574d1>, %arg2: !acsim.owner<@acir_queue_25d96b515101c39468cc7c64b72583e92f965f22f4c3ad7ad8ddabaf8d1574d1>, %arg3: !acsim.owner<@acir_queue_25d96b515101c39468cc7c64b72583e92f965f22f4c3ad7ad8ddabaf8d1574d1>):
        %4 = acsim.live.load @arbiter slot "live00000001" : !acsim.value<@acir_value_4382085a956d169d939be08807ee71613c27a4a4a6c990a02ca53c7421550c3a>
        %5 = acsim.inline @acir_impl_scalar_unwrap_ff9a680faa57c70912aa78f48e6e6a7c8e1d68ee2c73b2ec59e1db39b804ff76(%4) : (!acsim.value<@acir_value_4382085a956d169d939be08807ee71613c27a4a4a6c990a02ca53c7421550c3a>) -> i32
        %6 = acsim.invoke @acir_impl_queue_try_send_e6032c4723da335240b746d3be2b749bd47c74ad843ff77e8ff6ed7ec94fea65(%arg3, %5) : (!acsim.owner<@acir_queue_25d96b515101c39468cc7c64b72583e92f965f22f4c3ad7ad8ddabaf8d1574d1>, i32) -> i1
        cf.cond_br %6, ^bb1, ^bb2
      ^bb1:  // pred: ^bb0
        %7 = acsim.invoke @acir_impl_wake_next_delta_27cb4376e0c3f696c7a3d65ba8612843ec70b21d944add7d0b26efb005a04d8c() : () -> !acsim.wake<@acir_wake_next_delta>
        acsim.suspend @entry on %7 : !acsim.wake<@acir_wake_next_delta>
      ^bb2:  // pred: ^bb0
        %8 = acsim.invoke @acir_impl_wake_queue_writable_da1dabd0494cae8ff77a429dc12b26411a9de3ff68a505fd402a75decfcae4a4(%arg3) : (!acsim.owner<@acir_queue_25d96b515101c39468cc7c64b72583e92f965f22f4c3ad7ad8ddabaf8d1574d1>) -> !acsim.wake<@acir_wake_queue_writable>
        acsim.suspend @pc00000004 on %8 : !acsim.wake<@acir_wake_queue_writable>
      }
}
      acsim.process @producer0 captures(%0 : !acsim.owner<@acir_queue_25d96b515101c39468cc7c64b72583e92f965f22f4c3ad7ad8ddabaf8d1574d1>) names ["queue_in0"] entry @entry pcs [@entry] live [] fairness 18 specialization "sha256:7e888de8e519b758355c10ccbeeba09af5173b95e17963cb09bc210b9d0c9103" {
state @entry {
      ^bb0(%arg0: !acsim.owner<@acir_queue_25d96b515101c39468cc7c64b72583e92f965f22f4c3ad7ad8ddabaf8d1574d1>):
        %c0_i32 = arith.constant 0 : i32
        %4 = acsim.invoke @acir_impl_queue_try_send_e6032c4723da335240b746d3be2b749bd47c74ad843ff77e8ff6ed7ec94fea65(%arg0, %c0_i32) : (!acsim.owner<@acir_queue_25d96b515101c39468cc7c64b72583e92f965f22f4c3ad7ad8ddabaf8d1574d1>, i32) -> i1
        %c24849_i32 = arith.constant 24849 : i32
        %5 = acsim.invoke @acir_impl_queue_try_send_e6032c4723da335240b746d3be2b749bd47c74ad843ff77e8ff6ed7ec94fea65(%arg0, %c24849_i32) : (!acsim.owner<@acir_queue_25d96b515101c39468cc7c64b72583e92f965f22f4c3ad7ad8ddabaf8d1574d1>, i32) -> i1
        %c49696_i32 = arith.constant 49696 : i32
        %6 = acsim.invoke @acir_impl_queue_try_send_e6032c4723da335240b746d3be2b749bd47c74ad843ff77e8ff6ed7ec94fea65(%arg0, %c49696_i32) : (!acsim.owner<@acir_queue_25d96b515101c39468cc7c64b72583e92f965f22f4c3ad7ad8ddabaf8d1574d1>, i32) -> i1
        %c74545_i32 = arith.constant 74545 : i32
        %7 = acsim.invoke @acir_impl_queue_try_send_e6032c4723da335240b746d3be2b749bd47c74ad843ff77e8ff6ed7ec94fea65(%arg0, %c74545_i32) : (!acsim.owner<@acir_queue_25d96b515101c39468cc7c64b72583e92f965f22f4c3ad7ad8ddabaf8d1574d1>, i32) -> i1
        %c99392_i32 = arith.constant 99392 : i32
        %8 = acsim.invoke @acir_impl_queue_try_send_e6032c4723da335240b746d3be2b749bd47c74ad843ff77e8ff6ed7ec94fea65(%arg0, %c99392_i32) : (!acsim.owner<@acir_queue_25d96b515101c39468cc7c64b72583e92f965f22f4c3ad7ad8ddabaf8d1574d1>, i32) -> i1
        %c124241_i32 = arith.constant 124241 : i32
        %9 = acsim.invoke @acir_impl_queue_try_send_e6032c4723da335240b746d3be2b749bd47c74ad843ff77e8ff6ed7ec94fea65(%arg0, %c124241_i32) : (!acsim.owner<@acir_queue_25d96b515101c39468cc7c64b72583e92f965f22f4c3ad7ad8ddabaf8d1574d1>, i32) -> i1
        %c149088_i32 = arith.constant 149088 : i32
        %10 = acsim.invoke @acir_impl_queue_try_send_e6032c4723da335240b746d3be2b749bd47c74ad843ff77e8ff6ed7ec94fea65(%arg0, %c149088_i32) : (!acsim.owner<@acir_queue_25d96b515101c39468cc7c64b72583e92f965f22f4c3ad7ad8ddabaf8d1574d1>, i32) -> i1
        %c173937_i32 = arith.constant 173937 : i32
        %11 = acsim.invoke @acir_impl_queue_try_send_e6032c4723da335240b746d3be2b749bd47c74ad843ff77e8ff6ed7ec94fea65(%arg0, %c173937_i32) : (!acsim.owner<@acir_queue_25d96b515101c39468cc7c64b72583e92f965f22f4c3ad7ad8ddabaf8d1574d1>, i32) -> i1
        %12 = acsim.invoke @acir_impl_wake_next_delta_27cb4376e0c3f696c7a3d65ba8612843ec70b21d944add7d0b26efb005a04d8c() : () -> !acsim.wake<@acir_wake_next_delta>
        acsim.suspend @entry on %12 : !acsim.wake<@acir_wake_next_delta>
      }
}
      acsim.process @producer1 captures(%1 : !acsim.owner<@acir_queue_25d96b515101c39468cc7c64b72583e92f965f22f4c3ad7ad8ddabaf8d1574d1>) names ["queue_in1"] entry @entry pcs [@entry] live [] fairness 18 specialization "sha256:c507c970d950f8a1e6fc0814914f98c9131b1ccf72414bd47b6c7e6403c65469" {
state @entry {
      ^bb0(%arg0: !acsim.owner<@acir_queue_25d96b515101c39468cc7c64b72583e92f965f22f4c3ad7ad8ddabaf8d1574d1>):
        %c261_i32 = arith.constant 261 : i32
        %4 = acsim.invoke @acir_impl_queue_try_send_e6032c4723da335240b746d3be2b749bd47c74ad843ff77e8ff6ed7ec94fea65(%arg0, %c261_i32) : (!acsim.owner<@acir_queue_25d96b515101c39468cc7c64b72583e92f965f22f4c3ad7ad8ddabaf8d1574d1>, i32) -> i1
        %c25108_i32 = arith.constant 25108 : i32
        %5 = acsim.invoke @acir_impl_queue_try_send_e6032c4723da335240b746d3be2b749bd47c74ad843ff77e8ff6ed7ec94fea65(%arg0, %c25108_i32) : (!acsim.owner<@acir_queue_25d96b515101c39468cc7c64b72583e92f965f22f4c3ad7ad8ddabaf8d1574d1>, i32) -> i1
        %c49957_i32 = arith.constant 49957 : i32
        %6 = acsim.invoke @acir_impl_queue_try_send_e6032c4723da335240b746d3be2b749bd47c74ad843ff77e8ff6ed7ec94fea65(%arg0, %c49957_i32) : (!acsim.owner<@acir_queue_25d96b515101c39468cc7c64b72583e92f965f22f4c3ad7ad8ddabaf8d1574d1>, i32) -> i1
        %c74804_i32 = arith.constant 74804 : i32
        %7 = acsim.invoke @acir_impl_queue_try_send_e6032c4723da335240b746d3be2b749bd47c74ad843ff77e8ff6ed7ec94fea65(%arg0, %c74804_i32) : (!acsim.owner<@acir_queue_25d96b515101c39468cc7c64b72583e92f965f22f4c3ad7ad8ddabaf8d1574d1>, i32) -> i1
        %c99653_i32 = arith.constant 99653 : i32
        %8 = acsim.invoke @acir_impl_queue_try_send_e6032c4723da335240b746d3be2b749bd47c74ad843ff77e8ff6ed7ec94fea65(%arg0, %c99653_i32) : (!acsim.owner<@acir_queue_25d96b515101c39468cc7c64b72583e92f965f22f4c3ad7ad8ddabaf8d1574d1>, i32) -> i1
        %c124500_i32 = arith.constant 124500 : i32
        %9 = acsim.invoke @acir_impl_queue_try_send_e6032c4723da335240b746d3be2b749bd47c74ad843ff77e8ff6ed7ec94fea65(%arg0, %c124500_i32) : (!acsim.owner<@acir_queue_25d96b515101c39468cc7c64b72583e92f965f22f4c3ad7ad8ddabaf8d1574d1>, i32) -> i1
        %c149349_i32 = arith.constant 149349 : i32
        %10 = acsim.invoke @acir_impl_queue_try_send_e6032c4723da335240b746d3be2b749bd47c74ad843ff77e8ff6ed7ec94fea65(%arg0, %c149349_i32) : (!acsim.owner<@acir_queue_25d96b515101c39468cc7c64b72583e92f965f22f4c3ad7ad8ddabaf8d1574d1>, i32) -> i1
        %c174196_i32 = arith.constant 174196 : i32
        %11 = acsim.invoke @acir_impl_queue_try_send_e6032c4723da335240b746d3be2b749bd47c74ad843ff77e8ff6ed7ec94fea65(%arg0, %c174196_i32) : (!acsim.owner<@acir_queue_25d96b515101c39468cc7c64b72583e92f965f22f4c3ad7ad8ddabaf8d1574d1>, i32) -> i1
        %12 = acsim.invoke @acir_impl_wake_next_delta_27cb4376e0c3f696c7a3d65ba8612843ec70b21d944add7d0b26efb005a04d8c() : () -> !acsim.wake<@acir_wake_next_delta>
        acsim.suspend @entry on %12 : !acsim.wake<@acir_wake_next_delta>
      }
}
      acsim.process @sink0 captures(%2 : !acsim.owner<@acir_queue_25d96b515101c39468cc7c64b72583e92f965f22f4c3ad7ad8ddabaf8d1574d1>) names ["queue_out0"] entry @entry pcs [@entry] live [] fairness 23 specialization "sha256:8537f8dacf5e6889590f3aa6c664e88ae2e1016d77b44d1f5bd4a004ea3739d5" {
state @entry {
      ^bb0(%arg0: !acsim.owner<@acir_queue_25d96b515101c39468cc7c64b72583e92f965f22f4c3ad7ad8ddabaf8d1574d1>):
        %4:2 = acsim.invoke @acir_impl_queue_try_recv_dbd808e8a08c9d172873993a800a4c3544ea0bf8a0ed73a33ca5723dbfb2a14f(%arg0) : (!acsim.owner<@acir_queue_25d96b515101c39468cc7c64b72583e92f965f22f4c3ad7ad8ddabaf8d1574d1>) -> (i32, i1)
        cf.cond_br %4#1, ^bb1(%4#0 : i32), ^bb2
      ^bb1(%5: i32):  // pred: ^bb0
        %c0_i32 = arith.constant 0 : i32
        %c2_i32 = arith.constant 2 : i32
        %c3_i32 = arith.constant 3 : i32
        %c4_i32 = arith.constant 4 : i32
        %c8_i32 = arith.constant 8 : i32
        %c15_i32 = arith.constant 15 : i32
        %c97_i32 = arith.constant 97 : i32
        %6 = arith.andi %5, %c3_i32 : i32
        %7 = arith.cmpi eq, %6, %c0_i32 : i32
        acsim.invoke @acir_impl_contract_assert_23e22ef018e990817d91280d4edfe40b3bc98c984067c2244df086b13f76af5c(%7) : (i1) -> ()
        %8 = arith.shrui %5, %c2_i32 : i32
        %9 = arith.andi %8, %c3_i32 : i32
        %10 = arith.shrui %5, %c4_i32 : i32
        %11 = arith.andi %10, %c15_i32 : i32
        %12 = arith.shrui %5, %c8_i32 : i32
        %13 = arith.muli %11, %c97_i32 : i32
        %14 = arith.addi %13, %9 : i32
        %15 = arith.cmpi eq, %12, %14 : i32
        acsim.invoke @acir_impl_contract_assert_9b5eef0fb7e52f816bdcb999aba9897a8ff413fc43d86338bd1ce15f4d2e3f70(%15) : (i1) -> ()
        %16 = acsim.invoke @acir_impl_wake_next_delta_27cb4376e0c3f696c7a3d65ba8612843ec70b21d944add7d0b26efb005a04d8c() : () -> !acsim.wake<@acir_wake_next_delta>
        acsim.suspend @entry on %16 : !acsim.wake<@acir_wake_next_delta>
      ^bb2:  // pred: ^bb0
        %17 = acsim.invoke @acir_impl_wake_queue_readable_ef2bf2cff9aa2130207f640ff7425779e60c6e95346c73ae138dcac696f7e917(%arg0) : (!acsim.owner<@acir_queue_25d96b515101c39468cc7c64b72583e92f965f22f4c3ad7ad8ddabaf8d1574d1>) -> !acsim.wake<@acir_wake_queue_readable>
        acsim.suspend @entry on %17 : !acsim.wake<@acir_wake_queue_readable>
      }
}
      acsim.process @sink1 captures(%3 : !acsim.owner<@acir_queue_25d96b515101c39468cc7c64b72583e92f965f22f4c3ad7ad8ddabaf8d1574d1>) names ["queue_out1"] entry @entry pcs [@entry] live [] fairness 23 specialization "sha256:8a255d3eb9eaec9f8338ab64ddbbec6d394d0be38a2de1f5c49c0ea0e801d3ac" {
state @entry {
      ^bb0(%arg0: !acsim.owner<@acir_queue_25d96b515101c39468cc7c64b72583e92f965f22f4c3ad7ad8ddabaf8d1574d1>):
        %4:2 = acsim.invoke @acir_impl_queue_try_recv_dbd808e8a08c9d172873993a800a4c3544ea0bf8a0ed73a33ca5723dbfb2a14f(%arg0) : (!acsim.owner<@acir_queue_25d96b515101c39468cc7c64b72583e92f965f22f4c3ad7ad8ddabaf8d1574d1>) -> (i32, i1)
        cf.cond_br %4#1, ^bb1(%4#0 : i32), ^bb2
      ^bb1(%5: i32):  // pred: ^bb0
        %c1_i32 = arith.constant 1 : i32
        %c2_i32 = arith.constant 2 : i32
        %c3_i32 = arith.constant 3 : i32
        %c4_i32 = arith.constant 4 : i32
        %c8_i32 = arith.constant 8 : i32
        %c15_i32 = arith.constant 15 : i32
        %c97_i32 = arith.constant 97 : i32
        %6 = arith.andi %5, %c3_i32 : i32
        %7 = arith.cmpi eq, %6, %c1_i32 : i32
        acsim.invoke @acir_impl_contract_assert_78028a2a15273482761948460d6bc9e7941edf3c6ba37a4bad14db78f79293c6(%7) : (i1) -> ()
        %8 = arith.shrui %5, %c2_i32 : i32
        %9 = arith.andi %8, %c3_i32 : i32
        %10 = arith.shrui %5, %c4_i32 : i32
        %11 = arith.andi %10, %c15_i32 : i32
        %12 = arith.shrui %5, %c8_i32 : i32
        %13 = arith.muli %11, %c97_i32 : i32
        %14 = arith.addi %13, %9 : i32
        %15 = arith.cmpi eq, %12, %14 : i32
        acsim.invoke @acir_impl_contract_assert_af028d399dddeaeda959b8741ea8e87019af94c75785ac2af22b94932b96975d(%15) : (i1) -> ()
        %16 = acsim.invoke @acir_impl_wake_next_delta_27cb4376e0c3f696c7a3d65ba8612843ec70b21d944add7d0b26efb005a04d8c() : () -> !acsim.wake<@acir_wake_next_delta>
        acsim.suspend @entry on %16 : !acsim.wake<@acir_wake_next_delta>
      ^bb2:  // pred: ^bb0
        %17 = acsim.invoke @acir_impl_wake_queue_readable_ef2bf2cff9aa2130207f640ff7425779e60c6e95346c73ae138dcac696f7e917(%arg0) : (!acsim.owner<@acir_queue_25d96b515101c39468cc7c64b72583e92f965f22f4c3ad7ad8ddabaf8d1574d1>) -> !acsim.wake<@acir_wake_queue_readable>
        acsim.suspend @entry on %17 : !acsim.wake<@acir_wake_queue_readable>
      }
}
      acsim.return
    }
    %object, %activation = acsim.dispatch @Top::@in0 path "root.in0" indices [] object 0 activation 0 work "gfsim::QueueRuntime::work" xfer "gfsim::QueueRuntime::xfer" reset "gfsim::QueueRuntime::reset" validate "gfsim::QueueRuntime::validate" : !acsim.object_id, !acsim.activation_id
    %object_0, %activation_1 = acsim.dispatch @Top::@in1 path "root.in1" indices [] object 1 activation 1 work "gfsim::QueueRuntime::work" xfer "gfsim::QueueRuntime::xfer" reset "gfsim::QueueRuntime::reset" validate "gfsim::QueueRuntime::validate" : !acsim.object_id, !acsim.activation_id
    %object_2, %activation_3 = acsim.dispatch @Top::@out0 path "root.out0" indices [] object 2 activation 2 work "gfsim::QueueRuntime::work" xfer "gfsim::QueueRuntime::xfer" reset "gfsim::QueueRuntime::reset" validate "gfsim::QueueRuntime::validate" : !acsim.object_id, !acsim.activation_id
    %object_4, %activation_5 = acsim.dispatch @Top::@out1 path "root.out1" indices [] object 3 activation 3 work "gfsim::QueueRuntime::work" xfer "gfsim::QueueRuntime::xfer" reset "gfsim::QueueRuntime::reset" validate "gfsim::QueueRuntime::validate" : !acsim.object_id, !acsim.activation_id
    %object_6, %activation_7 = acsim.dispatch @Top::@arbiter path "root.arbiter" indices [] object 4 activation 4 work "acsim_generated::Top::sdb3b621e1e2c4cfba2df7a41cefb947e2c3f202c365c91fc87a697b229b32b40::arbiter::pc61813baded3cb0be13b890ad2cddbcf220f2621b00602bb4f45c26ba3367fe3::work" xfer "acsim_generated::Top::sdb3b621e1e2c4cfba2df7a41cefb947e2c3f202c365c91fc87a697b229b32b40::arbiter::pc61813baded3cb0be13b890ad2cddbcf220f2621b00602bb4f45c26ba3367fe3::xfer" reset "acsim_generated::Top::sdb3b621e1e2c4cfba2df7a41cefb947e2c3f202c365c91fc87a697b229b32b40::arbiter::pc61813baded3cb0be13b890ad2cddbcf220f2621b00602bb4f45c26ba3367fe3::reset" validate "acsim_generated::Top::sdb3b621e1e2c4cfba2df7a41cefb947e2c3f202c365c91fc87a697b229b32b40::arbiter::pc61813baded3cb0be13b890ad2cddbcf220f2621b00602bb4f45c26ba3367fe3::validate" : !acsim.object_id, !acsim.activation_id
    %object_8, %activation_9 = acsim.dispatch @Top::@producer0 path "root.producer0" indices [] object 5 activation 5 work "acsim_generated::Top::sdb3b621e1e2c4cfba2df7a41cefb947e2c3f202c365c91fc87a697b229b32b40::producer0::p7e888de8e519b758355c10ccbeeba09af5173b95e17963cb09bc210b9d0c9103::work" xfer "acsim_generated::Top::sdb3b621e1e2c4cfba2df7a41cefb947e2c3f202c365c91fc87a697b229b32b40::producer0::p7e888de8e519b758355c10ccbeeba09af5173b95e17963cb09bc210b9d0c9103::xfer" reset "acsim_generated::Top::sdb3b621e1e2c4cfba2df7a41cefb947e2c3f202c365c91fc87a697b229b32b40::producer0::p7e888de8e519b758355c10ccbeeba09af5173b95e17963cb09bc210b9d0c9103::reset" validate "acsim_generated::Top::sdb3b621e1e2c4cfba2df7a41cefb947e2c3f202c365c91fc87a697b229b32b40::producer0::p7e888de8e519b758355c10ccbeeba09af5173b95e17963cb09bc210b9d0c9103::validate" : !acsim.object_id, !acsim.activation_id
    %object_10, %activation_11 = acsim.dispatch @Top::@producer1 path "root.producer1" indices [] object 6 activation 6 work "acsim_generated::Top::sdb3b621e1e2c4cfba2df7a41cefb947e2c3f202c365c91fc87a697b229b32b40::producer1::pc507c970d950f8a1e6fc0814914f98c9131b1ccf72414bd47b6c7e6403c65469::work" xfer "acsim_generated::Top::sdb3b621e1e2c4cfba2df7a41cefb947e2c3f202c365c91fc87a697b229b32b40::producer1::pc507c970d950f8a1e6fc0814914f98c9131b1ccf72414bd47b6c7e6403c65469::xfer" reset "acsim_generated::Top::sdb3b621e1e2c4cfba2df7a41cefb947e2c3f202c365c91fc87a697b229b32b40::producer1::pc507c970d950f8a1e6fc0814914f98c9131b1ccf72414bd47b6c7e6403c65469::reset" validate "acsim_generated::Top::sdb3b621e1e2c4cfba2df7a41cefb947e2c3f202c365c91fc87a697b229b32b40::producer1::pc507c970d950f8a1e6fc0814914f98c9131b1ccf72414bd47b6c7e6403c65469::validate" : !acsim.object_id, !acsim.activation_id
    %object_12, %activation_13 = acsim.dispatch @Top::@sink0 path "root.sink0" indices [] object 7 activation 7 work "acsim_generated::Top::sdb3b621e1e2c4cfba2df7a41cefb947e2c3f202c365c91fc87a697b229b32b40::sink0::p8537f8dacf5e6889590f3aa6c664e88ae2e1016d77b44d1f5bd4a004ea3739d5::work" xfer "acsim_generated::Top::sdb3b621e1e2c4cfba2df7a41cefb947e2c3f202c365c91fc87a697b229b32b40::sink0::p8537f8dacf5e6889590f3aa6c664e88ae2e1016d77b44d1f5bd4a004ea3739d5::xfer" reset "acsim_generated::Top::sdb3b621e1e2c4cfba2df7a41cefb947e2c3f202c365c91fc87a697b229b32b40::sink0::p8537f8dacf5e6889590f3aa6c664e88ae2e1016d77b44d1f5bd4a004ea3739d5::reset" validate "acsim_generated::Top::sdb3b621e1e2c4cfba2df7a41cefb947e2c3f202c365c91fc87a697b229b32b40::sink0::p8537f8dacf5e6889590f3aa6c664e88ae2e1016d77b44d1f5bd4a004ea3739d5::validate" : !acsim.object_id, !acsim.activation_id
    %object_14, %activation_15 = acsim.dispatch @Top::@sink1 path "root.sink1" indices [] object 8 activation 8 work "acsim_generated::Top::sdb3b621e1e2c4cfba2df7a41cefb947e2c3f202c365c91fc87a697b229b32b40::sink1::p8a255d3eb9eaec9f8338ab64ddbbec6d394d0be38a2de1f5c49c0ea0e801d3ac::work" xfer "acsim_generated::Top::sdb3b621e1e2c4cfba2df7a41cefb947e2c3f202c365c91fc87a697b229b32b40::sink1::p8a255d3eb9eaec9f8338ab64ddbbec6d394d0be38a2de1f5c49c0ea0e801d3ac::xfer" reset "acsim_generated::Top::sdb3b621e1e2c4cfba2df7a41cefb947e2c3f202c365c91fc87a697b229b32b40::sink1::p8a255d3eb9eaec9f8338ab64ddbbec6d394d0be38a2de1f5c49c0ea0e801d3ac::reset" validate "acsim_generated::Top::sdb3b621e1e2c4cfba2df7a41cefb947e2c3f202c365c91fc87a697b229b32b40::sink1::p8a255d3eb9eaec9f8338ab64ddbbec6d394d0be38a2de1f5c49c0ea0e801d3ac::validate" : !acsim.object_id, !acsim.activation_id
    acsim.activate %activation to %object : !acsim.activation_id to !acsim.object_id
    acsim.activate %activation to %object_6 : !acsim.activation_id to !acsim.object_id
    acsim.activate %activation to %object_8 : !acsim.activation_id to !acsim.object_id
    acsim.activate %activation_1 to %object_0 : !acsim.activation_id to !acsim.object_id
    acsim.activate %activation_1 to %object_6 : !acsim.activation_id to !acsim.object_id
    acsim.activate %activation_1 to %object_10 : !acsim.activation_id to !acsim.object_id
    acsim.activate %activation_3 to %object_2 : !acsim.activation_id to !acsim.object_id
    acsim.activate %activation_3 to %object_6 : !acsim.activation_id to !acsim.object_id
    acsim.activate %activation_3 to %object_12 : !acsim.activation_id to !acsim.object_id
    acsim.activate %activation_5 to %object_4 : !acsim.activation_id to !acsim.object_id
    acsim.activate %activation_5 to %object_6 : !acsim.activation_id to !acsim.object_id
    acsim.activate %activation_5 to %object_14 : !acsim.activation_id to !acsim.object_id
    acsim.activate %activation_7 to %object_6 : !acsim.activation_id to !acsim.object_id
    acsim.activate %activation_9 to %object_8 : !acsim.activation_id to !acsim.object_id
    acsim.activate %activation_11 to %object_10 : !acsim.activation_id to !acsim.object_id
    acsim.activate %activation_13 to %object_12 : !acsim.activation_id to !acsim.object_id
    acsim.activate %activation_15 to %object_14 : !acsim.activation_id to !acsim.object_id
  }
}
