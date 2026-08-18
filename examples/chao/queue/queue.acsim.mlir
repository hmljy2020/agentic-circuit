module attributes {ac.contract_epoch = "0.2"} {
  acsim.model @queue_demo epoch "0.2" root @Top construction ["root.messages", "root.consumer", "root.producer"] destruction ["root.producer", "root.consumer", "root.messages"] fingerprints {binding_lock = "sha256:4f53cda18c2baa0c0354bb5f9a3ecbe5ed12ab4d8e11ba873c2f11161202b945", frozen_acir = "sha256:8d0efe0aa605ec663f2a8f737a0c0069eeeb507c1df4602acca41f65414504cf", profile = "sha256:079c9d12005aad817f722d2f0a34ccc3185b5ec0ce06ee243f945e4e1bb7b4c7", provider = "sha256:4f53cda18c2baa0c0354bb5f9a3ecbe5ed12ab4d8e11ba873c2f11161202b945", schema_set = "sha256:4f53cda18c2baa0c0354bb5f9a3ecbe5ed12ab4d8e11ba873c2f11161202b945", toolchain = "sha256:bd7deae3fdf722776d18998ce9b58d48bb1c2b195a6b2a3e32c9f60bf0ae557b"} {
    acsim.type @acir_impl_queue_try_recv_0554c86ca00ced2dbb445d3a1be6d8475b87fe85b054fa2c2ac413e10293ddbb cpp "acir::generated::impl_queue_try_recv_0554c86ca00ced2dbb445d3a1be6d8475b87fe85b054fa2c2ac413e10293ddbb" kind "implementation" fingerprint "sha256:0554c86ca00ced2dbb445d3a1be6d8475b87fe85b054fa2c2ac413e10293ddbb"
    acsim.type @acir_impl_queue_try_send_28a3546b0024ef4bb526e4dec38fb22d62da86f57ff9eb5d5326e382a7c835c2 cpp "acir::generated::impl_queue_try_send_28a3546b0024ef4bb526e4dec38fb22d62da86f57ff9eb5d5326e382a7c835c2" kind "implementation" fingerprint "sha256:28a3546b0024ef4bb526e4dec38fb22d62da86f57ff9eb5d5326e382a7c835c2"
    acsim.type @acir_impl_wake_next_delta_27cb4376e0c3f696c7a3d65ba8612843ec70b21d944add7d0b26efb005a04d8c cpp "acir::generated::impl_wake_next_delta_27cb4376e0c3f696c7a3d65ba8612843ec70b21d944add7d0b26efb005a04d8c" kind "implementation" fingerprint "sha256:27cb4376e0c3f696c7a3d65ba8612843ec70b21d944add7d0b26efb005a04d8c"
    acsim.type @acir_impl_wake_queue_readable_cc29d0a00ffca97e55ebe7219f44e30e0b9416d5ac2763157bc8e69059c3f96d cpp "acir::generated::impl_wake_queue_readable_cc29d0a00ffca97e55ebe7219f44e30e0b9416d5ac2763157bc8e69059c3f96d" kind "implementation" fingerprint "sha256:cc29d0a00ffca97e55ebe7219f44e30e0b9416d5ac2763157bc8e69059c3f96d"
    acsim.type @acir_impl_wake_queue_writable_f16092a6c77e82bbbef505d2e0d679ae325b702a7d202514218c75dca65875b8 cpp "acir::generated::impl_wake_queue_writable_f16092a6c77e82bbbef505d2e0d679ae325b702a7d202514218c75dca65875b8" kind "implementation" fingerprint "sha256:f16092a6c77e82bbbef505d2e0d679ae325b702a7d202514218c75dca65875b8"
    acsim.type @acir_queue_25d96b515101c39468cc7c64b72583e92f965f22f4c3ad7ad8ddabaf8d1574d1 cpp "gfsim::Queue<std::int32_t>" kind "runtime_object" fingerprint "sha256:25d96b515101c39468cc7c64b72583e92f965f22f4c3ad7ad8ddabaf8d1574d1"
    acsim.type @acir_wake_next_delta cpp "acir::generated::wake_next_delta" kind "wake" fingerprint "sha256:8cf214054e3ad1f49ca7091e040092971fe7dec32ccfd59554fdef160e889c2a"
    acsim.type @acir_wake_queue_readable cpp "acir::generated::wake_queue_readable" kind "wake" fingerprint "sha256:6440dbe429f3db95b3a4530f2a7e2b4660295c97a8a1af79ba0a7dfe3c4a8a0b"
    acsim.type @acir_wake_queue_writable cpp "acir::generated::wake_queue_writable" kind "wake" fingerprint "sha256:9b3448c249d4e00eeb840b4c73e8cd5996334ea43d4ab8c37350c1bc2503a505"
    acsim.module @Top interface {ports = [], resources = [], results = []} static [] specialization "sha256:fa7449f45802aac3aeebfe30aca8dd3087a32c2eabbac397415834be7e5f7bc6" exports [] {
      %0 = acsim.instance @messages target @acir_queue_25d96b515101c39468cc7c64b72583e92f965f22f4c3ad7ad8ddabaf8d1574d1 args [1, 4] specialization "sha256:d6e2e3501b352f2afaba97140838d1793ca15df93b92ebaebcc90f1e334b33d7" : !acsim.owner<@acir_queue_25d96b515101c39468cc7c64b72583e92f965f22f4c3ad7ad8ddabaf8d1574d1>
      acsim.process @consumer captures(%0 : !acsim.owner<@acir_queue_25d96b515101c39468cc7c64b72583e92f965f22f4c3ad7ad8ddabaf8d1574d1>) names ["queue_messages"] entry @entry pcs [@entry, @pc00000001] live [] fairness 4 specialization "sha256:242b8ae745cb925851341093e40158f1359e7abfd8911a19eec5dfec5d253a1e" {
state @entry {
      ^bb0(%arg0: !acsim.owner<@acir_queue_25d96b515101c39468cc7c64b72583e92f965f22f4c3ad7ad8ddabaf8d1574d1>):
        %1:2 = acsim.invoke @acir_impl_queue_try_recv_0554c86ca00ced2dbb445d3a1be6d8475b87fe85b054fa2c2ac413e10293ddbb(%arg0) : (!acsim.owner<@acir_queue_25d96b515101c39468cc7c64b72583e92f965f22f4c3ad7ad8ddabaf8d1574d1>) -> (i32, i1)
        cf.cond_br %1#1, ^bb2, ^bb1
      ^bb1:  // pred: ^bb0
        %2 = acsim.invoke @acir_impl_wake_queue_readable_cc29d0a00ffca97e55ebe7219f44e30e0b9416d5ac2763157bc8e69059c3f96d(%arg0) : (!acsim.owner<@acir_queue_25d96b515101c39468cc7c64b72583e92f965f22f4c3ad7ad8ddabaf8d1574d1>) -> !acsim.wake<@acir_wake_queue_readable>
        acsim.suspend @pc00000001 on %2 : !acsim.wake<@acir_wake_queue_readable>
      ^bb2:  // pred: ^bb0
        %3 = acsim.invoke @acir_impl_wake_next_delta_27cb4376e0c3f696c7a3d65ba8612843ec70b21d944add7d0b26efb005a04d8c() : () -> !acsim.wake<@acir_wake_next_delta>
        acsim.suspend @entry on %3 : !acsim.wake<@acir_wake_next_delta>
      }
state @pc00000001 {
      ^bb0(%arg0: !acsim.owner<@acir_queue_25d96b515101c39468cc7c64b72583e92f965f22f4c3ad7ad8ddabaf8d1574d1>):
        %1 = acsim.invoke @acir_impl_wake_next_delta_27cb4376e0c3f696c7a3d65ba8612843ec70b21d944add7d0b26efb005a04d8c() : () -> !acsim.wake<@acir_wake_next_delta>
        acsim.suspend @entry on %1 : !acsim.wake<@acir_wake_next_delta>
      }
}
      acsim.process @producer captures(%0 : !acsim.owner<@acir_queue_25d96b515101c39468cc7c64b72583e92f965f22f4c3ad7ad8ddabaf8d1574d1>) names ["queue_messages"] entry @entry pcs [@entry, @pc00000001] live [] fairness 5 specialization "sha256:b4bf8f767a2e0a26e9633f9d4bfdabfc207a591a0e681bb50383027c76ba381f" {
state @entry {
      ^bb0(%arg0: !acsim.owner<@acir_queue_25d96b515101c39468cc7c64b72583e92f965f22f4c3ad7ad8ddabaf8d1574d1>):
        %c10_i32 = arith.constant 10 : i32
        %1 = acsim.invoke @acir_impl_queue_try_send_28a3546b0024ef4bb526e4dec38fb22d62da86f57ff9eb5d5326e382a7c835c2(%arg0, %c10_i32) : (!acsim.owner<@acir_queue_25d96b515101c39468cc7c64b72583e92f965f22f4c3ad7ad8ddabaf8d1574d1>, i32) -> i1
        cf.cond_br %1, ^bb2, ^bb1
      ^bb1:  // pred: ^bb0
        %2 = acsim.invoke @acir_impl_wake_queue_writable_f16092a6c77e82bbbef505d2e0d679ae325b702a7d202514218c75dca65875b8(%arg0) : (!acsim.owner<@acir_queue_25d96b515101c39468cc7c64b72583e92f965f22f4c3ad7ad8ddabaf8d1574d1>) -> !acsim.wake<@acir_wake_queue_writable>
        acsim.suspend @pc00000001 on %2 : !acsim.wake<@acir_wake_queue_writable>
      ^bb2:  // pred: ^bb0
        %3 = acsim.invoke @acir_impl_wake_next_delta_27cb4376e0c3f696c7a3d65ba8612843ec70b21d944add7d0b26efb005a04d8c() : () -> !acsim.wake<@acir_wake_next_delta>
        acsim.suspend @entry on %3 : !acsim.wake<@acir_wake_next_delta>
      }
state @pc00000001 {
      ^bb0(%arg0: !acsim.owner<@acir_queue_25d96b515101c39468cc7c64b72583e92f965f22f4c3ad7ad8ddabaf8d1574d1>):
        %1 = acsim.invoke @acir_impl_wake_next_delta_27cb4376e0c3f696c7a3d65ba8612843ec70b21d944add7d0b26efb005a04d8c() : () -> !acsim.wake<@acir_wake_next_delta>
        acsim.suspend @entry on %1 : !acsim.wake<@acir_wake_next_delta>
      }
}
      acsim.return
    }
    %object, %activation = acsim.dispatch @Top::@messages path "root.messages" indices [] object 0 activation 0 work "gfsim::QueueRuntime::work" xfer "gfsim::QueueRuntime::xfer" reset "gfsim::QueueRuntime::reset" validate "gfsim::QueueRuntime::validate" : !acsim.object_id, !acsim.activation_id
    %object_0, %activation_1 = acsim.dispatch @Top::@consumer path "root.consumer" indices [] object 1 activation 1 work "acsim_generated::Top::sfa7449f45802aac3aeebfe30aca8dd3087a32c2eabbac397415834be7e5f7bc6::consumer::p242b8ae745cb925851341093e40158f1359e7abfd8911a19eec5dfec5d253a1e::work" xfer "acsim_generated::Top::sfa7449f45802aac3aeebfe30aca8dd3087a32c2eabbac397415834be7e5f7bc6::consumer::p242b8ae745cb925851341093e40158f1359e7abfd8911a19eec5dfec5d253a1e::xfer" reset "acsim_generated::Top::sfa7449f45802aac3aeebfe30aca8dd3087a32c2eabbac397415834be7e5f7bc6::consumer::p242b8ae745cb925851341093e40158f1359e7abfd8911a19eec5dfec5d253a1e::reset" validate "acsim_generated::Top::sfa7449f45802aac3aeebfe30aca8dd3087a32c2eabbac397415834be7e5f7bc6::consumer::p242b8ae745cb925851341093e40158f1359e7abfd8911a19eec5dfec5d253a1e::validate" : !acsim.object_id, !acsim.activation_id
    %object_2, %activation_3 = acsim.dispatch @Top::@producer path "root.producer" indices [] object 2 activation 2 work "acsim_generated::Top::sfa7449f45802aac3aeebfe30aca8dd3087a32c2eabbac397415834be7e5f7bc6::producer::pb4bf8f767a2e0a26e9633f9d4bfdabfc207a591a0e681bb50383027c76ba381f::work" xfer "acsim_generated::Top::sfa7449f45802aac3aeebfe30aca8dd3087a32c2eabbac397415834be7e5f7bc6::producer::pb4bf8f767a2e0a26e9633f9d4bfdabfc207a591a0e681bb50383027c76ba381f::xfer" reset "acsim_generated::Top::sfa7449f45802aac3aeebfe30aca8dd3087a32c2eabbac397415834be7e5f7bc6::producer::pb4bf8f767a2e0a26e9633f9d4bfdabfc207a591a0e681bb50383027c76ba381f::reset" validate "acsim_generated::Top::sfa7449f45802aac3aeebfe30aca8dd3087a32c2eabbac397415834be7e5f7bc6::producer::pb4bf8f767a2e0a26e9633f9d4bfdabfc207a591a0e681bb50383027c76ba381f::validate" : !acsim.object_id, !acsim.activation_id
    acsim.activate %activation to %object : !acsim.activation_id to !acsim.object_id
    acsim.activate %activation to %object_0 : !acsim.activation_id to !acsim.object_id
    acsim.activate %activation to %object_2 : !acsim.activation_id to !acsim.object_id
    acsim.activate %activation_1 to %object_0 : !acsim.activation_id to !acsim.object_id
    acsim.activate %activation_3 to %object_2 : !acsim.activation_id to !acsim.object_id
  }
}

