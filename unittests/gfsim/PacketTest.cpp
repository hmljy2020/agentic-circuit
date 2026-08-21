#include "gfsim/packet.h"
#include "gfsim/host.h"
#include "gfsim/queue.h"

#include <gtest/gtest.h>

#include <cstdint>
#include <type_traits>

namespace {

using Request = gfsim::AtomicPacket<8, 1, 2, 3, 4>;
using EqualSizedReply = gfsim::AtomicPacket<8, 5, 6, 7, 8>;

static_assert(!std::is_same_v<Request, EqualSizedReply>);

TEST(PacketTest, FieldAccessAndSerializationPreserveAtomicBytes) {
  Request packet{};
  packet = gfsim::packetFieldWith<0, false>(packet, std::int8_t{3});
  packet = gfsim::packetFieldWith<4, false>(packet, std::int32_t{0x12345678});

  EXPECT_EQ((gfsim::packetFieldGet<std::int8_t, 0, false>(packet)), 3);
  EXPECT_EQ((gfsim::packetFieldGet<std::int32_t, 4, false>(packet)),
            0x12345678);

  auto bytes = gfsim::packetSerializeBytes(packet);
  Request copy = gfsim::packetDeserializeBytes<Request>(bytes);
  EXPECT_EQ(copy, packet);
}

TEST(PacketTest, HostEgressRetainsCommittedAtomicPacketUntilTaken) {
  gfsim::Queue<Request> queue("queue", 1, nullptr, 2);
  gfsim::HostEgress<Request> egress("egress", 2, nullptr, queue);
  Request packet{};
  packet = gfsim::packetFieldWith<4, false>(packet, std::int32_t{42});
  ASSERT_TRUE(queue.proposePush(packet));
  queue.doXfer({0, 0});

  egress.doWork({1, 0});
  queue.doXfer({1, 0});
  egress.doXfer({1, 0});
  ASSERT_TRUE(egress.ready());
  auto value = egress.take();
  ASSERT_TRUE(value.has_value());
  EXPECT_EQ(*value, packet);
  EXPECT_FALSE(egress.ready());
}

} // namespace
