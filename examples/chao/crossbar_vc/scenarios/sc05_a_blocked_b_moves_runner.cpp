#include "generated/model.h"

#include <cstdint>
#include <iostream>
#include <map>
#include <string>

int main() {
  acsim_generated::Model model;
  gfsim::RuntimeLimits limits;
  limits.maxTicks = 8;
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

  std::map<std::uint64_t, std::uint64_t> completedPerEpoch;
  for (const gfsim::CommittedEvent &ev : model.observations()) {
    if (ev.category == "transaction" && ev.name == "completed")
      ++completedPerEpoch[ev.epoch.time];
  }
  for (const auto &[epoch, count] : completedPerEpoch)
    std::cout << "epoch " << epoch << " completed=" << count << '\n';

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

  // sc05 (test 5): out0_A is filled by A seq0 on epoch 1 and stays full, so A
  // seq1 is blocked; B moves to out1_B on epoch 2 (the tick after A is stuck).
  const bool passed =
      result.classification == gfsim::TerminationClass::Incomplete &&
      result.finalEpoch == gfsim::Epoch{8, 0} &&
      conservation("in0_A", 2) && conservation("in0_B", 2) &&
      conservation("out0_A", 1) && conservation("out1_B", 1) &&
      stat("in0_A", "completed_transactions") == 1 &&
      stat("in0_B", "completed_transactions") == 1 &&
      stat("out0_A", "accepted_transactions") == 1 &&
      stat("out1_B", "accepted_transactions") == 1 &&
      completedPerEpoch[1] == 1 && completedPerEpoch[2] == 1;
  std::cout << "sc05_passed=" << (passed ? "true" : "false") << '\n';
  return passed ? 0 : 1;
}
