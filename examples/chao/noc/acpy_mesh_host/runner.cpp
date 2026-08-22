#include "generated/model.h"

#include <cstdint>
#include <iostream>
#include <string_view>

int main() {
  acsim_generated::Model model;
  model.configure({});
  if (model.hostInputCount() != 4)
    return 1;
  for (std::size_t index = 0; index < model.hostInputCount(); ++index)
    if (model.hostInputName(index) !=
        std::string_view(index == 0   ? "node0"
                         : index == 1 ? "node1"
                         : index == 2 ? "node2"
                                      : "node3"))
      return 2;

  // Low bits are X then Y. This is node0 -> node3 (East, then North).
  if (!model.offer(0, static_cast<int32_t>(0x103)) || model.offer(0, 0x203))
    return 3;
  for (int tick = 0; tick < 12; ++tick)
    if (!model.stepTick()) {
      std::cerr << "step failed tick=" << tick << " code="
                << model.terminationResult().diagnosticCode << '\n';
      return 4;
    }

  uint64_t delivered = 0;
  for (const gfsim::StatSnapshot &stat : model.statistics())
    if (stat.name == "completed_transactions" &&
        stat.objectPath.ends_with("/rx11"))
      delivered = stat.value;
  if (delivered != 1)
    return 5;

  std::cout << "ticks=" << model.currentEpoch().time
            << " delivered_node3=" << delivered << '\n';
  return 0;
}
