#include "generated/model.h"

#include <cstdint>
#include <iostream>
#include <map>
#include <string>

int main() {
  acsim_generated::Model model;
  gfsim::RuntimeLimits limits;
  limits.maxTicks = 5;
  model.configure(limits);

  const gfsim::TerminationResult result = model.run();
  std::map<std::string, std::uint64_t> queueStats;
  for (const gfsim::StatSnapshot &stat : model.statistics()) {
    std::cout << "stat " << stat.objectPath << '.' << stat.name << '='
              << stat.value << '\n';
    queueStats.emplace(stat.objectPath + "." + stat.name, stat.value);
  }

  std::cout << "classification=incomplete\n"
            << "final_tick=" << result.finalEpoch.time << '\n';

  const std::string prefix = "/generated/root-model/";
  const bool passed =
      result.classification == gfsim::TerminationClass::Incomplete &&
      result.finalEpoch == gfsim::Epoch{5, 0} &&
      queueStats[prefix + "op_a.accepted_transactions"] == 3 &&
      queueStats[prefix + "op_a.completed_transactions"] == 2 &&
      queueStats[prefix + "op_a.queue_occupancy_peak"] == 1 &&
      queueStats[prefix + "op_b.accepted_transactions"] == 3 &&
      queueStats[prefix + "op_b.completed_transactions"] == 2 &&
      queueStats[prefix + "op_b.queue_occupancy_peak"] == 1 &&
      queueStats[prefix + "result.accepted_transactions"] == 2 &&
      queueStats[prefix + "result.completed_transactions"] == 2 &&
      queueStats[prefix + "result.queue_occupancy"] == 0 &&
      queueStats[prefix + "result.queue_occupancy_peak"] == 1;
  return passed ? 0 : 1;
}
