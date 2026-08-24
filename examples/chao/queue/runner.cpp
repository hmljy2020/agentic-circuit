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
  std::map<std::string, std::uint64_t> queueStats;
  for (const gfsim::StatSnapshot &stat : model.statistics()) {
    std::cout << "stat " << stat.objectPath << '.' << stat.name << '='
              << stat.value << '\n';
    if (stat.name == "queue_occupancy" ||
        stat.name == "queue_occupancy_peak" ||
        stat.name == "accepted_transactions" ||
        stat.name == "completed_transactions")
      queueStats.emplace(stat.name, stat.value);
  }

  std::cout << "classification=incomplete\n"
            << "final_tick=" << result.finalEpoch.time << '\n'
            << "queue_occupancy=" << queueStats["queue_occupancy"] << '\n'
            << "queue_occupancy_peak="
            << queueStats["queue_occupancy_peak"] << '\n'
            << "accepted_transactions="
            << queueStats["accepted_transactions"] << '\n'
            << "completed_transactions="
            << queueStats["completed_transactions"] << '\n'
            << "observations=" << model.observations().size() << '\n';

  const bool passed =
      result.classification == gfsim::TerminationClass::Incomplete &&
      result.finalEpoch == gfsim::Epoch{6, 0} &&
      queueStats["queue_occupancy"] == 0 &&
      queueStats["queue_occupancy_peak"] == 1 &&
      queueStats["accepted_transactions"] == 3 &&
      queueStats["completed_transactions"] == 3;
  return passed ? 0 : 1;
}
