#include "generated/model.h"

#include <cstdint>
#include <iostream>
#include <map>
#include <string>

int main() {
  acsim_generated::Model model;
  gfsim::RuntimeLimits limits;
  limits.maxTicks = 10;
  model.configure(limits);

  const gfsim::TerminationResult result = model.run();
  std::map<std::string, std::uint64_t> stats;
  for (const gfsim::StatSnapshot &stat : model.statistics()) {
    const std::string key = stat.objectPath + "." + stat.name;
    stats.emplace(key, stat.value);
    std::cout << "stat " << key << '=' << stat.value << '\n';
  }
  std::cout << "classification="
            << (result.classification == gfsim::TerminationClass::Incomplete
                    ? "incomplete"
                    : "unexpected")
            << '\n'
            << "final_tick=" << result.finalEpoch.time << '\n'
            << "observations=" << model.observations().size() << '\n';

  const std::string prefix = "/generated/root-model/";
  auto stat = [&](const char *object, const char *name) {
    return stats[prefix + object + "." + name];
  };
  auto conservation = [&](const char *object, std::uint64_t entries) {
    return stat(object, "accepted_transactions") ==
               stat(object, "completed_transactions") +
                   stat(object, "queue_occupancy") &&
           stat(object, "queue_occupancy_peak") <= entries;
  };

  // sc09 (test 9): the four-flit burst drains in FIFO order -- the sink's
  // in-model assert (seq == prev + 1) already fails the run on any reorder, so
  // a clean completion here plus conservation is the whole check.
  const bool passed =
      result.classification == gfsim::TerminationClass::Incomplete &&
      result.finalEpoch == gfsim::Epoch{10, 0} &&
      conservation("in0_A", 4) && conservation("out0_A", 1) &&
      conservation("gate", 1) && conservation("prev", 2) &&
      stat("in0_A", "completed_transactions") == 4 &&
      stat("in0_A", "queue_occupancy_peak") == 4 &&
      stat("out0_A", "completed_transactions") == 4 &&
      stat("gate", "accepted_transactions") == 1;
  std::cout << "sc09_passed=" << (passed ? "true" : "false") << '\n';
  return passed ? 0 : 1;
}
