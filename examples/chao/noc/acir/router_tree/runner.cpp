#include "generated/model.h"

#include <array>
#include <cstdint>
#include <iostream>
#include <map>
#include <string>

int main() {
  acsim_generated::Model model;
  gfsim::RuntimeLimits limits;
  limits.maxTicks = 32;
  model.configure(limits);

  const gfsim::TerminationResult result = model.run();
  std::map<std::string, std::uint64_t> stats;
  for (const gfsim::StatSnapshot &stat : model.statistics()) {
    const std::string key = stat.objectPath + "." + stat.name;
    stats.emplace(key, stat.value);
    std::cout << "stat " << key << '=' << stat.value << '\n';
  }

  const std::string prefix = "/generated/root-model/";
  const std::array<std::string, 7> queues = {
      "ingress", "trunk_left", "trunk_right", "leaf0",
      "leaf1",   "leaf2",      "leaf3"};
  bool passed = result.classification == gfsim::TerminationClass::Incomplete &&
                result.finalEpoch == gfsim::Epoch{32, 0};
  for (const std::string &queue : queues)
    passed = passed &&
             stats[prefix + queue + ".queue_occupancy_peak"] == 1;
  for (const std::string &leaf : {"leaf0", "leaf1", "leaf2", "leaf3"})
    passed = passed &&
             stats[prefix + leaf + ".accepted_transactions"] >= 2 &&
             stats[prefix + leaf + ".completed_transactions"] >= 2;

  std::cout << "classification="
            << (result.classification == gfsim::TerminationClass::Incomplete
                    ? "incomplete"
                    : "unexpected")
            << '\n'
            << "final_tick=" << result.finalEpoch.time << '\n'
            << "router_tree_passed=" << (passed ? "true" : "false") << '\n';
  return passed ? 0 : 1;
}
