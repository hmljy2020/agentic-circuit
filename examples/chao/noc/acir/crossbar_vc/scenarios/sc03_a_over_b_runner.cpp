#include "generated/model.h"

#include <cstdint>
#include <iostream>
#include <map>
#include <string>

int main() {
  acsim_generated::Model model;
  gfsim::RuntimeLimits limits;
  limits.maxTicks = 6;
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

  // sc03 (test 3): strict A > B priority on the same input and destination.
  //
  // The assertion is the contention, not B's absence: in the first competing
  // cycle (epoch 1) exactly ONE transfer commits -- the in-model per-input
  // rule plus the A-first phase keep A and B from both leaving input 0 -- and
  // that transfer is A's, as the sink's in-model assert verifies out0_A only
  // ever carries A flits and out0_A's first arrival is epoch 1 (out0_B's is
  // epoch 2). A then dominates the bandwidth (3 completions to B's 1); B moves
  // exactly once, in the cycle right after an A grant, when the depth-1
  // destination out0_A is still full -- the bandwidth-reuse window of test 5,
  // not a priority failure. In-model asserts already passed (clean completion).
  const bool passed =
      result.classification == gfsim::TerminationClass::Incomplete &&
      result.finalEpoch == gfsim::Epoch{6, 0} &&
      conservation("in0_A", 2) && conservation("in0_B", 2) &&
      conservation("out0_A", 1) && conservation("out0_B", 1) &&
      completedPerEpoch[1] == 1 &&
      completedPerEpoch[2] == 2 &&
      stat("in0_A", "completed_transactions") == 3 &&
      stat("in0_B", "completed_transactions") == 1 &&
      stat("in0_A", "completed_transactions") >
          stat("in0_B", "completed_transactions") &&
      stat("out0_A", "accepted_transactions") == 3 &&
      stat("out0_B", "accepted_transactions") == 1;
  std::cout << "sc03_passed=" << (passed ? "true" : "false") << '\n';
  return passed ? 0 : 1;
}
