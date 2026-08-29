#include "memory_array.generated.cpp"

#include <array>
#include <cstddef>
#include <cstdint>
#include <iostream>

int main() {
  ac_generated::MemoryArray model;
  const std::array<ac_generated::Request, 6> requests{{
      {0x03, 10, true, 41},
      {0x13, 11, true, 52},
      {0x23, 12, true, 63},
      {0x03, 20, false, 0},
      {0x13, 21, false, 0},
      {0x23, 22, false, 0},
  }};
  auto rows = model.dispatch_rows();
  std::size_t nextRequest = 0;
  for (std::size_t tick = 0; tick < 96; ++tick) {
    if (nextRequest < requests.size()) {
      if (!model.requests().proposePush(requests[nextRequest]))
        return 1;
      ++nextRequest;
    }
    const gfsim::Epoch epoch{tick, 0};
    for (auto &row : rows)
      row.work(row.object, epoch);
    for (auto &row : rows)
      row.xfer(row.object, epoch, gfsim::XferPhase::Arbitrate);
    for (auto &row : rows)
      row.xfer(row.object, epoch, gfsim::XferPhase::Commit);
    if (model.sink_0_values().size() == requests.size())
      break;
  }

  std::array<std::uint16_t, 256> oldDataById{};
  const auto &responses = model.sink_0_values();
  if (responses.size() != requests.size())
    return 2;
  for (const auto &response : responses)
    oldDataById[response.id] = response.data;
  if (oldDataById[10] != 0 || oldDataById[11] != 0 || oldDataById[12] != 0 ||
      oldDataById[20] != 41 || oldDataById[21] != 52 || oldDataById[22] != 63)
    return 3;

  std::cout << "responses=" << responses.size() << " bank00=" << oldDataById[20]
            << " bank01=" << oldDataById[21] << " bank10=" << oldDataById[22]
            << '\n';
  return 0;
}
