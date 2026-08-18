module attributes {ac.contract_epoch = "0.2"} {
  acsim.model @fu_demo epoch "0.2" root @Top construction ["root.complete", "root.dispatch", "root.results", "root.fu", "root.producer", "root.retire", "root.sink"] destruction ["root.sink", "root.retire", "root.producer", "root.fu", "root.results", "root.dispatch", "root.complete"] fingerprints {binding_lock = "sha256:4f53cda18c2baa0c0354bb5f9a3ecbe5ed12ab4d8e11ba873c2f11161202b945", frozen_acir = "sha256:3f73ed1a25ec65ef688306edce6ae40f279fadc29fe8847f03354e8d2ce5b3aa", profile = "sha256:079c9d12005aad817f722d2f0a34ccc3185b5ec0ce06ee243f945e4e1bb7b4c7", provider = "sha256:4f53cda18c2baa0c0354bb5f9a3ecbe5ed12ab4d8e11ba873c2f11161202b945", schema_set = "sha256:4f53cda18c2baa0c0354bb5f9a3ecbe5ed12ab4d8e11ba873c2f11161202b945", toolchain = "sha256:bd7deae3fdf722776d18998ce9b58d48bb1c2b195a6b2a3e32c9f60bf0ae557b"} {
    acsim.type @acir_event_queue_7ac3d0848553e44c4c657541a84fa75aa143d60afcad2ca1d5129f4b65fce118 cpp "gfsim::TimedEventQueue<std::int32_t>" kind "runtime_object" fingerprint "sha256:7ac3d0848553e44c4c657541a84fa75aa143d60afcad2ca1d5129f4b65fce118"
    acsim.type @acir_impl_contract_assert_bbf69ec1e0f9b5645aed96e1fc17f34245be11d475c6fbe443841a6f4e6fe659 cpp "acir::generated::impl_contract_assert_bbf69ec1e0f9b5645aed96e1fc17f34245be11d475c6fbe443841a6f4e6fe659" kind "implementation" fingerprint "sha256:bbf69ec1e0f9b5645aed96e1fc17f34245be11d475c6fbe443841a6f4e6fe659"
    acsim.type @acir_impl_contract_assert_c0524de6887e01cddf0eaf136814b6356f270a6efcfec24abcd160a7e65aa3a5 cpp "acir::generated::impl_contract_assert_c0524de6887e01cddf0eaf136814b6356f270a6efcfec24abcd160a7e65aa3a5" kind "implementation" fingerprint "sha256:c0524de6887e01cddf0eaf136814b6356f270a6efcfec24abcd160a7e65aa3a5"
    acsim.type @acir_impl_event_schedule_a6d783c1010d6b95345d530d7031669ca1e4b620b22aa330edc2e45c4c6e75e9 cpp "acir::generated::impl_event_schedule_a6d783c1010d6b95345d530d7031669ca1e4b620b22aa330edc2e45c4c6e75e9" kind "implementation" fingerprint "sha256:a6d783c1010d6b95345d530d7031669ca1e4b620b22aa330edc2e45c4c6e75e9"
    acsim.type @acir_impl_event_try_recv_77c4effd3d3a847e555aed204816ed4901c40e04fdc2b6dece62bdf5bba7e779 cpp "acir::generated::impl_event_try_recv_77c4effd3d3a847e555aed204816ed4901c40e04fdc2b6dece62bdf5bba7e779" kind "implementation" fingerprint "sha256:77c4effd3d3a847e555aed204816ed4901c40e04fdc2b6dece62bdf5bba7e779"
    acsim.type @acir_impl_queue_try_recv_26f27a93841d43ec1e98134716114cc07584123b647779fc0ffc9e6825ed3c10 cpp "acir::generated::impl_queue_try_recv_26f27a93841d43ec1e98134716114cc07584123b647779fc0ffc9e6825ed3c10" kind "implementation" fingerprint "sha256:26f27a93841d43ec1e98134716114cc07584123b647779fc0ffc9e6825ed3c10"
    acsim.type @acir_impl_queue_try_send_2a9d1d9ec9b5e8b8a91fb86a56e11395d583b17bb9efb1aa9d5a0a19cadfc82b cpp "acir::generated::impl_queue_try_send_2a9d1d9ec9b5e8b8a91fb86a56e11395d583b17bb9efb1aa9d5a0a19cadfc82b" kind "implementation" fingerprint "sha256:2a9d1d9ec9b5e8b8a91fb86a56e11395d583b17bb9efb1aa9d5a0a19cadfc82b"
    acsim.type @acir_impl_scalar_unwrap_ff9a680faa57c70912aa78f48e6e6a7c8e1d68ee2c73b2ec59e1db39b804ff76 cpp "acir::generated::impl_scalar_unwrap_ff9a680faa57c70912aa78f48e6e6a7c8e1d68ee2c73b2ec59e1db39b804ff76" kind "implementation" fingerprint "sha256:ff9a680faa57c70912aa78f48e6e6a7c8e1d68ee2c73b2ec59e1db39b804ff76"
    acsim.type @acir_impl_scalar_wrap_973ddda5db5ff882c81ec29f3a1984a9dc63b3bac3c38e3e2036995c135bfbc6 cpp "acir::generated::impl_scalar_wrap_973ddda5db5ff882c81ec29f3a1984a9dc63b3bac3c38e3e2036995c135bfbc6" kind "implementation" fingerprint "sha256:973ddda5db5ff882c81ec29f3a1984a9dc63b3bac3c38e3e2036995c135bfbc6"
    acsim.type @acir_impl_wake_event_queue_c59f2c6a5e1b0fbcc7424d79ef68f468c9dadc4aec014fd8d8c26757d74ef4ae cpp "acir::generated::impl_wake_event_queue_c59f2c6a5e1b0fbcc7424d79ef68f468c9dadc4aec014fd8d8c26757d74ef4ae" kind "implementation" fingerprint "sha256:c59f2c6a5e1b0fbcc7424d79ef68f468c9dadc4aec014fd8d8c26757d74ef4ae"
    acsim.type @acir_impl_wake_next_delta_27cb4376e0c3f696c7a3d65ba8612843ec70b21d944add7d0b26efb005a04d8c cpp "acir::generated::impl_wake_next_delta_27cb4376e0c3f696c7a3d65ba8612843ec70b21d944add7d0b26efb005a04d8c" kind "implementation" fingerprint "sha256:27cb4376e0c3f696c7a3d65ba8612843ec70b21d944add7d0b26efb005a04d8c"
    acsim.type @acir_impl_wake_queue_readable_2cd111eb101ea054702a990905a6f6db2eeedb01cca4ab4fd98cf4d743cf5262 cpp "acir::generated::impl_wake_queue_readable_2cd111eb101ea054702a990905a6f6db2eeedb01cca4ab4fd98cf4d743cf5262" kind "implementation" fingerprint "sha256:2cd111eb101ea054702a990905a6f6db2eeedb01cca4ab4fd98cf4d743cf5262"
    acsim.type @acir_impl_wake_queue_writable_f412d6539eb7581dbf079c506ab4585ff1944b1448931bbc8c4d02313ece3039 cpp "acir::generated::impl_wake_queue_writable_f412d6539eb7581dbf079c506ab4585ff1944b1448931bbc8c4d02313ece3039" kind "implementation" fingerprint "sha256:f412d6539eb7581dbf079c506ab4585ff1944b1448931bbc8c4d02313ece3039"
    acsim.type @acir_queue_25d96b515101c39468cc7c64b72583e92f965f22f4c3ad7ad8ddabaf8d1574d1 cpp "gfsim::Queue<std::int32_t>" kind "runtime_object" fingerprint "sha256:25d96b515101c39468cc7c64b72583e92f965f22f4c3ad7ad8ddabaf8d1574d1"
    acsim.type @acir_value_4382085a956d169d939be08807ee71613c27a4a4a6c990a02ca53c7421550c3a cpp "std::int32_t" kind "value" fingerprint "sha256:4382085a956d169d939be08807ee71613c27a4a4a6c990a02ca53c7421550c3a"
    acsim.type @acir_wake_event_queue cpp "acir::generated::wake_event_queue" kind "wake" fingerprint "sha256:330810728631406df44000847b67b6a82a855303a14d016b59a2c8231fb175f9"
    acsim.type @acir_wake_next_delta cpp "acir::generated::wake_next_delta" kind "wake" fingerprint "sha256:8cf214054e3ad1f49ca7091e040092971fe7dec32ccfd59554fdef160e889c2a"
    acsim.type @acir_wake_queue_readable cpp "acir::generated::wake_queue_readable" kind "wake" fingerprint "sha256:6440dbe429f3db95b3a4530f2a7e2b4660295c97a8a1af79ba0a7dfe3c4a8a0b"
    acsim.type @acir_wake_queue_writable cpp "acir::generated::wake_queue_writable" kind "wake" fingerprint "sha256:9b3448c249d4e00eeb840b4c73e8cd5996334ea43d4ab8c37350c1bc2503a505"
    acsim.type @core cpp "gfsim::TimeDomainRuntime" kind "time_domain" fingerprint "sha256:5cf0982f2181695b3b337696100cd0c0cf0744da07b359528aed1437b0c9e4d6" {period = 1 : i64, phase = 0 : i64, tick_scale = 1 : i64}
    acsim.module @Top interface {ports = [], resources = [], results = []} static [] specialization "sha256:06c139a44f1c7e9bbee6f5723e661a1f5bb33bb7655a622a5e44852381a5c5a5" exports [] {
      %0 = acsim.instance @complete target @acir_event_queue_7ac3d0848553e44c4c657541a84fa75aa143d60afcad2ca1d5129f4b65fce118 args [8] specialization "sha256:bafb8631e617ac1d6ec7b0fbd41d17a32f809d934775a107c71ca48fb25e2f6c" : !acsim.owner<@acir_event_queue_7ac3d0848553e44c4c657541a84fa75aa143d60afcad2ca1d5129f4b65fce118>
      %1 = acsim.instance @dispatch target @acir_event_queue_7ac3d0848553e44c4c657541a84fa75aa143d60afcad2ca1d5129f4b65fce118 args [8] specialization "sha256:bafb8631e617ac1d6ec7b0fbd41d17a32f809d934775a107c71ca48fb25e2f6c" : !acsim.owner<@acir_event_queue_7ac3d0848553e44c4c657541a84fa75aa143d60afcad2ca1d5129f4b65fce118>
      %2 = acsim.instance @results target @acir_queue_25d96b515101c39468cc7c64b72583e92f965f22f4c3ad7ad8ddabaf8d1574d1 args [1, 4] specialization "sha256:3337a401f2af29d76921744d74d9bb0a29ca420fe63a05304289dbb4700e4991" : !acsim.owner<@acir_queue_25d96b515101c39468cc7c64b72583e92f965f22f4c3ad7ad8ddabaf8d1574d1>
      acsim.process @fu captures(%0 : !acsim.owner<@acir_event_queue_7ac3d0848553e44c4c657541a84fa75aa143d60afcad2ca1d5129f4b65fce118>, %1 : !acsim.owner<@acir_event_queue_7ac3d0848553e44c4c657541a84fa75aa143d60afcad2ca1d5129f4b65fce118>) names ["queue_complete", "queue_dispatch"] entry @entry pcs [@entry] live [] fairness 11 specialization "sha256:cf3508f0d3c30395f0f6fb84a966074ba535830c4e163b481fe5048ff40ddfd9" {
state @entry {
      ^bb0(%arg0: !acsim.owner<@acir_event_queue_7ac3d0848553e44c4c657541a84fa75aa143d60afcad2ca1d5129f4b65fce118>, %arg1: !acsim.owner<@acir_event_queue_7ac3d0848553e44c4c657541a84fa75aa143d60afcad2ca1d5129f4b65fce118>):
        %3:2 = acsim.invoke @acir_impl_event_try_recv_77c4effd3d3a847e555aed204816ed4901c40e04fdc2b6dece62bdf5bba7e779(%arg1) : (!acsim.owner<@acir_event_queue_7ac3d0848553e44c4c657541a84fa75aa143d60afcad2ca1d5129f4b65fce118>) -> (i32, i1)
        cf.cond_br %3#1, ^bb1(%3#0 : i32), ^bb2
      ^bb1(%4: i32):  // pred: ^bb0
        %c1_i32 = arith.constant 1 : i32
        %5 = arith.addi %4, %c1_i32 : i32
        %c8_i32 = arith.constant 8 : i32
        %6 = arith.cmpi eq, %5, %c8_i32 : i32
        acsim.invoke @acir_impl_contract_assert_c0524de6887e01cddf0eaf136814b6356f270a6efcfec24abcd160a7e65aa3a5(%6) : (i1) -> ()
        %c1_i64 = arith.constant 1 : i64
        %7 = acsim.invoke @acir_impl_event_schedule_a6d783c1010d6b95345d530d7031669ca1e4b620b22aa330edc2e45c4c6e75e9(%arg0, %5, %c1_i64) : (!acsim.owner<@acir_event_queue_7ac3d0848553e44c4c657541a84fa75aa143d60afcad2ca1d5129f4b65fce118>, i32, i64) -> i1
        %8 = acsim.invoke @acir_impl_wake_next_delta_27cb4376e0c3f696c7a3d65ba8612843ec70b21d944add7d0b26efb005a04d8c() : () -> !acsim.wake<@acir_wake_next_delta>
        acsim.suspend @entry on %8 : !acsim.wake<@acir_wake_next_delta>
      ^bb2:  // pred: ^bb0
        %9 = acsim.invoke @acir_impl_wake_event_queue_c59f2c6a5e1b0fbcc7424d79ef68f468c9dadc4aec014fd8d8c26757d74ef4ae(%arg1) : (!acsim.owner<@acir_event_queue_7ac3d0848553e44c4c657541a84fa75aa143d60afcad2ca1d5129f4b65fce118>) -> !acsim.wake<@acir_wake_event_queue>
        acsim.suspend @entry on %9 : !acsim.wake<@acir_wake_event_queue>
      }
}
      acsim.process @producer captures(%1 : !acsim.owner<@acir_event_queue_7ac3d0848553e44c4c657541a84fa75aa143d60afcad2ca1d5129f4b65fce118>) names ["queue_dispatch"] entry @entry pcs [@entry] live [] fairness 5 specialization "sha256:66370ecb66ac0e8e5dda96b9af5154c0276216ddf96bcb1987295d10833803e5" {
state @entry {
      ^bb0(%arg0: !acsim.owner<@acir_event_queue_7ac3d0848553e44c4c657541a84fa75aa143d60afcad2ca1d5129f4b65fce118>):
        %c7_i32 = arith.constant 7 : i32
        %c2_i64 = arith.constant 2 : i64
        %3 = acsim.invoke @acir_impl_event_schedule_a6d783c1010d6b95345d530d7031669ca1e4b620b22aa330edc2e45c4c6e75e9(%arg0, %c7_i32, %c2_i64) : (!acsim.owner<@acir_event_queue_7ac3d0848553e44c4c657541a84fa75aa143d60afcad2ca1d5129f4b65fce118>, i32, i64) -> i1
        %4 = acsim.invoke @acir_impl_wake_next_delta_27cb4376e0c3f696c7a3d65ba8612843ec70b21d944add7d0b26efb005a04d8c() : () -> !acsim.wake<@acir_wake_next_delta>
        acsim.suspend @entry on %4 : !acsim.wake<@acir_wake_next_delta>
      }
}
      acsim.process @retire captures(%0 : !acsim.owner<@acir_event_queue_7ac3d0848553e44c4c657541a84fa75aa143d60afcad2ca1d5129f4b65fce118>, %2 : !acsim.owner<@acir_queue_25d96b515101c39468cc7c64b72583e92f965f22f4c3ad7ad8ddabaf8d1574d1>) names ["queue_complete", "queue_results"] entry @entry pcs [@entry, @pc00000001] live [{name = "live00000000", type = !acsim.value<@acir_value_4382085a956d169d939be08807ee71613c27a4a4a6c990a02ca53c7421550c3a>}] fairness 8 specialization "sha256:6847c7a335b4a9abc4419f3816f39b2c49373ccd83cf8b98bb1db29780a0e22a" {
state @entry {
      ^bb0(%arg0: !acsim.owner<@acir_event_queue_7ac3d0848553e44c4c657541a84fa75aa143d60afcad2ca1d5129f4b65fce118>, %arg1: !acsim.owner<@acir_queue_25d96b515101c39468cc7c64b72583e92f965f22f4c3ad7ad8ddabaf8d1574d1>):
        %3:2 = acsim.invoke @acir_impl_event_try_recv_77c4effd3d3a847e555aed204816ed4901c40e04fdc2b6dece62bdf5bba7e779(%arg0) : (!acsim.owner<@acir_event_queue_7ac3d0848553e44c4c657541a84fa75aa143d60afcad2ca1d5129f4b65fce118>) -> (i32, i1)
        cf.cond_br %3#1, ^bb1(%3#0 : i32), ^bb4
      ^bb1(%4: i32):  // pred: ^bb0
        %5 = acsim.invoke @acir_impl_queue_try_send_2a9d1d9ec9b5e8b8a91fb86a56e11395d583b17bb9efb1aa9d5a0a19cadfc82b(%arg1, %4) : (!acsim.owner<@acir_queue_25d96b515101c39468cc7c64b72583e92f965f22f4c3ad7ad8ddabaf8d1574d1>, i32) -> i1
        cf.cond_br %5, ^bb2, ^bb3(%4 : i32)
      ^bb2:  // pred: ^bb1
        %6 = acsim.invoke @acir_impl_wake_next_delta_27cb4376e0c3f696c7a3d65ba8612843ec70b21d944add7d0b26efb005a04d8c() : () -> !acsim.wake<@acir_wake_next_delta>
        acsim.suspend @entry on %6 : !acsim.wake<@acir_wake_next_delta>
      ^bb3(%7: i32):  // pred: ^bb1
        %8 = acsim.inline @acir_impl_scalar_wrap_973ddda5db5ff882c81ec29f3a1984a9dc63b3bac3c38e3e2036995c135bfbc6(%7) : (i32) -> !acsim.value<@acir_value_4382085a956d169d939be08807ee71613c27a4a4a6c990a02ca53c7421550c3a>
        acsim.live.store %8 in @retire slot "live00000000" : !acsim.value<@acir_value_4382085a956d169d939be08807ee71613c27a4a4a6c990a02ca53c7421550c3a>
        %9 = acsim.invoke @acir_impl_wake_queue_writable_f412d6539eb7581dbf079c506ab4585ff1944b1448931bbc8c4d02313ece3039(%arg1) : (!acsim.owner<@acir_queue_25d96b515101c39468cc7c64b72583e92f965f22f4c3ad7ad8ddabaf8d1574d1>) -> !acsim.wake<@acir_wake_queue_writable>
        acsim.suspend @pc00000001 on %9 : !acsim.wake<@acir_wake_queue_writable>
      ^bb4:  // pred: ^bb0
        %10 = acsim.invoke @acir_impl_wake_event_queue_c59f2c6a5e1b0fbcc7424d79ef68f468c9dadc4aec014fd8d8c26757d74ef4ae(%arg0) : (!acsim.owner<@acir_event_queue_7ac3d0848553e44c4c657541a84fa75aa143d60afcad2ca1d5129f4b65fce118>) -> !acsim.wake<@acir_wake_event_queue>
        acsim.suspend @entry on %10 : !acsim.wake<@acir_wake_event_queue>
      }
state @pc00000001 {
      ^bb0(%arg0: !acsim.owner<@acir_event_queue_7ac3d0848553e44c4c657541a84fa75aa143d60afcad2ca1d5129f4b65fce118>, %arg1: !acsim.owner<@acir_queue_25d96b515101c39468cc7c64b72583e92f965f22f4c3ad7ad8ddabaf8d1574d1>):
        %3 = acsim.live.load @retire slot "live00000000" : !acsim.value<@acir_value_4382085a956d169d939be08807ee71613c27a4a4a6c990a02ca53c7421550c3a>
        %4 = acsim.inline @acir_impl_scalar_unwrap_ff9a680faa57c70912aa78f48e6e6a7c8e1d68ee2c73b2ec59e1db39b804ff76(%3) : (!acsim.value<@acir_value_4382085a956d169d939be08807ee71613c27a4a4a6c990a02ca53c7421550c3a>) -> i32
        %5 = acsim.invoke @acir_impl_queue_try_send_2a9d1d9ec9b5e8b8a91fb86a56e11395d583b17bb9efb1aa9d5a0a19cadfc82b(%arg1, %4) : (!acsim.owner<@acir_queue_25d96b515101c39468cc7c64b72583e92f965f22f4c3ad7ad8ddabaf8d1574d1>, i32) -> i1
        cf.cond_br %5, ^bb1, ^bb2
      ^bb1:  // pred: ^bb0
        %6 = acsim.invoke @acir_impl_wake_next_delta_27cb4376e0c3f696c7a3d65ba8612843ec70b21d944add7d0b26efb005a04d8c() : () -> !acsim.wake<@acir_wake_next_delta>
        acsim.suspend @entry on %6 : !acsim.wake<@acir_wake_next_delta>
      ^bb2:  // pred: ^bb0
        %7 = acsim.invoke @acir_impl_wake_queue_writable_f412d6539eb7581dbf079c506ab4585ff1944b1448931bbc8c4d02313ece3039(%arg1) : (!acsim.owner<@acir_queue_25d96b515101c39468cc7c64b72583e92f965f22f4c3ad7ad8ddabaf8d1574d1>) -> !acsim.wake<@acir_wake_queue_writable>
        acsim.suspend @pc00000001 on %7 : !acsim.wake<@acir_wake_queue_writable>
      }
}
      acsim.process @sink captures(%2 : !acsim.owner<@acir_queue_25d96b515101c39468cc7c64b72583e92f965f22f4c3ad7ad8ddabaf8d1574d1>) names ["queue_results"] entry @entry pcs [@entry] live [] fairness 7 specialization "sha256:1b3cd480dc542430f8b0f4a3e2fb9d8789562879aaaaea22c0440f1c3a397f9e" {
state @entry {
      ^bb0(%arg0: !acsim.owner<@acir_queue_25d96b515101c39468cc7c64b72583e92f965f22f4c3ad7ad8ddabaf8d1574d1>):
        %3:2 = acsim.invoke @acir_impl_queue_try_recv_26f27a93841d43ec1e98134716114cc07584123b647779fc0ffc9e6825ed3c10(%arg0) : (!acsim.owner<@acir_queue_25d96b515101c39468cc7c64b72583e92f965f22f4c3ad7ad8ddabaf8d1574d1>) -> (i32, i1)
        cf.cond_br %3#1, ^bb1(%3#0 : i32), ^bb2
      ^bb1(%4: i32):  // pred: ^bb0
        %c8_i32 = arith.constant 8 : i32
        %5 = arith.cmpi eq, %4, %c8_i32 : i32
        acsim.invoke @acir_impl_contract_assert_bbf69ec1e0f9b5645aed96e1fc17f34245be11d475c6fbe443841a6f4e6fe659(%5) : (i1) -> ()
        %6 = acsim.invoke @acir_impl_wake_next_delta_27cb4376e0c3f696c7a3d65ba8612843ec70b21d944add7d0b26efb005a04d8c() : () -> !acsim.wake<@acir_wake_next_delta>
        acsim.suspend @entry on %6 : !acsim.wake<@acir_wake_next_delta>
      ^bb2:  // pred: ^bb0
        %7 = acsim.invoke @acir_impl_wake_queue_readable_2cd111eb101ea054702a990905a6f6db2eeedb01cca4ab4fd98cf4d743cf5262(%arg0) : (!acsim.owner<@acir_queue_25d96b515101c39468cc7c64b72583e92f965f22f4c3ad7ad8ddabaf8d1574d1>) -> !acsim.wake<@acir_wake_queue_readable>
        acsim.suspend @entry on %7 : !acsim.wake<@acir_wake_queue_readable>
      }
}
      acsim.return
    }
    %object, %activation = acsim.dispatch @Top::@complete path "root.complete" indices [] object 0 activation 0 work "gfsim::QueueRuntime::work" xfer "gfsim::QueueRuntime::xfer" reset "gfsim::QueueRuntime::reset" validate "gfsim::QueueRuntime::validate" : !acsim.object_id, !acsim.activation_id
    %object_0, %activation_1 = acsim.dispatch @Top::@dispatch path "root.dispatch" indices [] object 1 activation 1 work "gfsim::QueueRuntime::work" xfer "gfsim::QueueRuntime::xfer" reset "gfsim::QueueRuntime::reset" validate "gfsim::QueueRuntime::validate" : !acsim.object_id, !acsim.activation_id
    %object_2, %activation_3 = acsim.dispatch @Top::@results path "root.results" indices [] object 2 activation 2 work "gfsim::QueueRuntime::work" xfer "gfsim::QueueRuntime::xfer" reset "gfsim::QueueRuntime::reset" validate "gfsim::QueueRuntime::validate" : !acsim.object_id, !acsim.activation_id
    %object_4, %activation_5 = acsim.dispatch @Top::@fu path "root.fu" indices [] object 3 activation 3 work "acsim_generated::Top::s06c139a44f1c7e9bbee6f5723e661a1f5bb33bb7655a622a5e44852381a5c5a5::fu::pcf3508f0d3c30395f0f6fb84a966074ba535830c4e163b481fe5048ff40ddfd9::work" xfer "acsim_generated::Top::s06c139a44f1c7e9bbee6f5723e661a1f5bb33bb7655a622a5e44852381a5c5a5::fu::pcf3508f0d3c30395f0f6fb84a966074ba535830c4e163b481fe5048ff40ddfd9::xfer" reset "acsim_generated::Top::s06c139a44f1c7e9bbee6f5723e661a1f5bb33bb7655a622a5e44852381a5c5a5::fu::pcf3508f0d3c30395f0f6fb84a966074ba535830c4e163b481fe5048ff40ddfd9::reset" validate "acsim_generated::Top::s06c139a44f1c7e9bbee6f5723e661a1f5bb33bb7655a622a5e44852381a5c5a5::fu::pcf3508f0d3c30395f0f6fb84a966074ba535830c4e163b481fe5048ff40ddfd9::validate" : !acsim.object_id, !acsim.activation_id
    %object_6, %activation_7 = acsim.dispatch @Top::@producer path "root.producer" indices [] object 4 activation 4 work "acsim_generated::Top::s06c139a44f1c7e9bbee6f5723e661a1f5bb33bb7655a622a5e44852381a5c5a5::producer::p66370ecb66ac0e8e5dda96b9af5154c0276216ddf96bcb1987295d10833803e5::work" xfer "acsim_generated::Top::s06c139a44f1c7e9bbee6f5723e661a1f5bb33bb7655a622a5e44852381a5c5a5::producer::p66370ecb66ac0e8e5dda96b9af5154c0276216ddf96bcb1987295d10833803e5::xfer" reset "acsim_generated::Top::s06c139a44f1c7e9bbee6f5723e661a1f5bb33bb7655a622a5e44852381a5c5a5::producer::p66370ecb66ac0e8e5dda96b9af5154c0276216ddf96bcb1987295d10833803e5::reset" validate "acsim_generated::Top::s06c139a44f1c7e9bbee6f5723e661a1f5bb33bb7655a622a5e44852381a5c5a5::producer::p66370ecb66ac0e8e5dda96b9af5154c0276216ddf96bcb1987295d10833803e5::validate" : !acsim.object_id, !acsim.activation_id
    %object_8, %activation_9 = acsim.dispatch @Top::@retire path "root.retire" indices [] object 5 activation 5 work "acsim_generated::Top::s06c139a44f1c7e9bbee6f5723e661a1f5bb33bb7655a622a5e44852381a5c5a5::retire::p6847c7a335b4a9abc4419f3816f39b2c49373ccd83cf8b98bb1db29780a0e22a::work" xfer "acsim_generated::Top::s06c139a44f1c7e9bbee6f5723e661a1f5bb33bb7655a622a5e44852381a5c5a5::retire::p6847c7a335b4a9abc4419f3816f39b2c49373ccd83cf8b98bb1db29780a0e22a::xfer" reset "acsim_generated::Top::s06c139a44f1c7e9bbee6f5723e661a1f5bb33bb7655a622a5e44852381a5c5a5::retire::p6847c7a335b4a9abc4419f3816f39b2c49373ccd83cf8b98bb1db29780a0e22a::reset" validate "acsim_generated::Top::s06c139a44f1c7e9bbee6f5723e661a1f5bb33bb7655a622a5e44852381a5c5a5::retire::p6847c7a335b4a9abc4419f3816f39b2c49373ccd83cf8b98bb1db29780a0e22a::validate" : !acsim.object_id, !acsim.activation_id
    %object_10, %activation_11 = acsim.dispatch @Top::@sink path "root.sink" indices [] object 6 activation 6 work "acsim_generated::Top::s06c139a44f1c7e9bbee6f5723e661a1f5bb33bb7655a622a5e44852381a5c5a5::sink::p1b3cd480dc542430f8b0f4a3e2fb9d8789562879aaaaea22c0440f1c3a397f9e::work" xfer "acsim_generated::Top::s06c139a44f1c7e9bbee6f5723e661a1f5bb33bb7655a622a5e44852381a5c5a5::sink::p1b3cd480dc542430f8b0f4a3e2fb9d8789562879aaaaea22c0440f1c3a397f9e::xfer" reset "acsim_generated::Top::s06c139a44f1c7e9bbee6f5723e661a1f5bb33bb7655a622a5e44852381a5c5a5::sink::p1b3cd480dc542430f8b0f4a3e2fb9d8789562879aaaaea22c0440f1c3a397f9e::reset" validate "acsim_generated::Top::s06c139a44f1c7e9bbee6f5723e661a1f5bb33bb7655a622a5e44852381a5c5a5::sink::p1b3cd480dc542430f8b0f4a3e2fb9d8789562879aaaaea22c0440f1c3a397f9e::validate" : !acsim.object_id, !acsim.activation_id
    acsim.activate %activation to %object_8 : !acsim.activation_id to !acsim.object_id
    acsim.activate %activation_1 to %object_4 : !acsim.activation_id to !acsim.object_id
    acsim.activate %activation_3 to %object_2 : !acsim.activation_id to !acsim.object_id
    acsim.activate %activation_3 to %object_8 : !acsim.activation_id to !acsim.object_id
    acsim.activate %activation_3 to %object_10 : !acsim.activation_id to !acsim.object_id
    acsim.activate %activation_5 to %object_4 : !acsim.activation_id to !acsim.object_id
    acsim.activate %activation_7 to %object_6 : !acsim.activation_id to !acsim.object_id
    acsim.activate %activation_9 to %object_8 : !acsim.activation_id to !acsim.object_id
    acsim.activate %activation_11 to %object_10 : !acsim.activation_id to !acsim.object_id
  }
}

